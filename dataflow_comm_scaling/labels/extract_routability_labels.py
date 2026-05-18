#!/usr/bin/env python3
"""Extract routability labels from physical-design logs and reports.

The parser is intentionally conservative. It does not try to understand every
vendor-specific table; it extracts stable scalar signals that are useful as
early-prediction targets and keeps the raw source paths for traceability.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        return fp.read()


def safe_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def first_float(patterns: Sequence[str], text: str, flags: int = re.IGNORECASE) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return safe_float(match.group(1).replace(",", ""))
    return None


def first_int(patterns: Sequence[str], text: str, flags: int = re.IGNORECASE) -> Optional[int]:
    value = first_float(patterns, text, flags)
    return int(value) if value is not None else None


def first_string(patterns: Sequence[str], text: str, flags: int = re.IGNORECASE) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return " ".join(match.group(1).strip().split())
    return None


def any_match(patterns: Sequence[str], text: str, flags: int = re.IGNORECASE) -> bool:
    return any(re.search(pattern, text, flags) for pattern in patterns)


def merge_text(paths: Sequence[str]) -> str:
    return "\n".join(read_text(path) for path in paths)


def congestion_score(labels: Dict[str, Any]) -> Optional[float]:
    """Build a monotonic scalar score from sparse tool outputs.

    The score is not a physical truth by itself. It is a fallback target when a
    flow gives partial labels instead of a single congestion metric.
    """

    terms: List[float] = []
    if labels.get("routed") == 0.0:
        terms.append(10.0)
    if labels.get("route_channel_width") is not None:
        terms.append(float(labels["route_channel_width"]) / 100.0)
    if labels.get("routing_area_total_wirelength") is not None:
        terms.append(math.log2(max(float(labels["routing_area_total_wirelength"]), 1.0)) / 10.0)
    if labels.get("overused_nodes") is not None:
        terms.append(math.log2(max(float(labels["overused_nodes"]), 1.0)) / 4.0)
    if labels.get("max_overuse") is not None:
        terms.append(float(labels["max_overuse"]))
    if labels.get("nets_with_routing_errors") is not None:
        terms.append(math.log2(max(float(labels["nets_with_routing_errors"]), 1.0)))
    if labels.get("nets_with_congestion") is not None:
        terms.append(math.log2(max(float(labels["nets_with_congestion"]), 1.0)) / 2.0)
    if labels.get("global_congestion_level") is not None:
        terms.append(float(labels["global_congestion_level"]))
    if labels.get("route_time_sec") is not None:
        terms.append(math.log2(max(float(labels["route_time_sec"]), 1.0)) / 8.0)
    return sum(terms) if terms else None


def parse_vpr(paths: Sequence[str]) -> Dict[str, Any]:
    text = merge_text(paths)
    routed = None
    if any_match(
        [
            r"circuit successfully routed",
            r"successfully routed with a channel width",
            r"routing completed successfully",
        ],
        text,
    ):
        routed = 1.0
    if any_match(
        [
            r"routing failed",
            r"failed to route",
            r"routing was unsuccessful",
            r"overused routing resources remain",
        ],
        text,
    ):
        routed = 0.0

    labels: Dict[str, Any] = {
        "tool": "vpr",
        "routed": routed,
        "route_status": first_string(
            [
                r"(Circuit successfully routed[^\n.]*)",
                r"(Routing failed[^\n.]*)",
                r"(Failed to route[^\n.]*)",
            ],
            text,
        ),
        "route_channel_width": first_float(
            [
                rf"channel width(?: factor)?(?: of| is|:)?\s*({NUMBER})",
                rf"best routing used a channel width(?: factor)?(?: of|:)?\s*({NUMBER})",
                rf"minimum channel width(?: factor)?(?: of|:)?\s*({NUMBER})",
            ],
            text,
        ),
        "routing_area_total_wirelength": first_float(
            [
                rf"total wirelength(?: is|:)?\s*({NUMBER})",
                rf"total routing area(?: is|:)?\s*({NUMBER})",
            ],
            text,
        ),
        "critical_path_ns": first_float(
            [
                rf"final critical path(?: delay)?(?: is|:)?\s*({NUMBER})\s*ns",
                rf"critical path(?: delay)?(?: is|:)?\s*({NUMBER})\s*ns",
            ],
            text,
        ),
        "route_time_sec": first_float(
            [
                rf"routing took\s*({NUMBER})\s*seconds",
                rf"route(?:r|ing)? time(?: is|:)?\s*({NUMBER})\s*s",
            ],
            text,
        ),
        "overused_nodes": first_int(
            [
                rf"overused(?: routing)? resources(?: remaining|:)?\s*({NUMBER})",
                rf"number of overused nodes(?: is|:)?\s*({NUMBER})",
            ],
            text,
        ),
        "max_overuse": first_float(
            [
                rf"max(?:imum)? overuse(?: is|:)?\s*({NUMBER})",
                rf"maximum routing resource overuse(?: is|:)?\s*({NUMBER})",
            ],
            text,
        ),
    }
    labels["congestion_score"] = congestion_score(labels)
    return labels


def parse_vivado(paths: Sequence[str]) -> Dict[str, Any]:
    text = merge_text(paths)
    routed = None
    if any_match(
        [
            r"design is fully routed",
            r"routing is complete",
            r"route_design completed successfully",
            r"no unrouted nets",
            r"design state\s*:\s*routed",
            r"routing is done",
        ],
        text,
    ):
        routed = 1.0
    if any_match(
        [
            r"routing failed",
            r"partially routed",
        ],
        text,
    ):
        routed = 0.0

    labels: Dict[str, Any] = {
        "tool": "vivado",
        "routed": routed,
        "route_status": first_string(
            [
                r"Routing status\s*[:=]\s*([^\n]+)",
                r"Route status\s*[:=]\s*([^\n]+)",
                r"(Design is fully routed[^\n.]*)",
                r"(Routing is complete[^\n.]*)",
            ],
            text,
        ),
        "global_congestion_level": first_float(
            [
                rf"global congestion level\s*[:=]\s*({NUMBER})",
                rf"congestion level\s*[:=]\s*({NUMBER})",
            ],
            text,
        ),
        "nets_with_congestion": first_int(
            [
                rf"nets with (?:routing )?congestion\s*[:=]\s*({NUMBER})",
                rf"number of congested nets\s*[:=]\s*({NUMBER})",
            ],
            text,
        ),
        "nets_with_routing_errors": first_int(
            [
                rf"nets with routing errors\s*[:=]\s*({NUMBER})",
                rf"# of nets with routing errors[.\s:]*({NUMBER})\s*:",
                rf"number of unrouted nets\s*[:=]\s*({NUMBER})",
                rf"unrouted nets\s*[:=]\s*({NUMBER})",
            ],
            text,
        ),
        "route_time_sec": first_float(
            [
                rf"route_design.*?elapsed.*?({NUMBER})\s*sec",
                rf"routing.*?elapsed.*?({NUMBER})\s*sec",
                rf"route(?:r|ing)? time(?: is|:)?\s*({NUMBER})\s*s",
            ],
            text,
        ),
        "fully_routed_nets": first_int(
            [rf"# of fully routed nets[.\s:]*({NUMBER})\s*:"],
            text,
        ),
        "routable_nets": first_int(
            [rf"# of routable nets[.\s:]*({NUMBER})\s*:"],
            text,
        ),
        "wns_ns": first_float(
            [
                rf"WNS\(ns\).*?\n\s*-+.*?\n\s*({NUMBER})\s+{NUMBER}",
                rf"\bWNS(?:\(ns\))?\s*[:|]?\s*({NUMBER})",
            ],
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ),
        "tns_ns": first_float(
            [
                rf"WNS\(ns\).*?\n\s*-+.*?\n\s*{NUMBER}\s+({NUMBER})",
                rf"\bTNS(?:\(ns\))?\s*[:|]?\s*({NUMBER})",
            ],
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ),
        "lut_utilization": first_float(
            [
                rf"\bCLB LUTs\b[^\n|]*\|\s*{NUMBER}\s*\|\s*{NUMBER}\s*\|\s*({NUMBER})\s*\|",
                rf"\|\s*Slice LUTs\s*\|\s*{NUMBER}\s*\|\s*{NUMBER}\s*\|\s*{NUMBER}\s*\|\s*{NUMBER}\s*\|\s*({NUMBER})\s*\|",
                rf"lut utilization\s*[:=]\s*({NUMBER})\s*%?",
            ],
            text,
        ),
        "dsp_utilization": first_float(
            [
                rf"\|\s*DSPs\s*\|\s*{NUMBER}\s*\|\s*{NUMBER}\s*\|\s*{NUMBER}\s*\|\s*{NUMBER}\s*\|\s*({NUMBER})\s*\|",
                rf"dsp utilization\s*[:=]\s*({NUMBER})\s*%?",
            ],
            text,
        ),
    }
    if labels["nets_with_routing_errors"] is not None:
        if float(labels["nets_with_routing_errors"]) > 0:
            labels["routed"] = 0.0
        elif labels["routed"] is None:
            labels["routed"] = 1.0
    if labels["fully_routed_nets"] is not None and labels["routable_nets"] is not None:
        labels["routed_net_fraction"] = (
            float(labels["fully_routed_nets"]) / float(labels["routable_nets"])
            if float(labels["routable_nets"]) > 0
            else None
        )
        if labels["routed_net_fraction"] == 1.0 and labels["routed"] is None:
            labels["routed"] = 1.0
    if labels["global_congestion_level"] is None and any_match(
        [
            r"no congestion windows are found",
            r"no initial estimated congestion windows are found",
        ],
        text,
    ):
        labels["global_congestion_level"] = 0.0
    if isinstance(labels.get("route_status"), str) and labels["route_status"].startswith("# nets"):
        labels["route_status"] = "routed" if labels.get("routed") == 1.0 else None
    labels["congestion_score"] = congestion_score(labels)
    return labels


def normalize_labels(labels: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for key, value in labels.items():
        if value is None:
            clean[key] = None
        elif isinstance(value, (int, float)):
            clean[key] = float(value)
        else:
            clean[key] = value
    return clean


def build_payload(design: str, tool: str, reports: Sequence[str]) -> Dict[str, Any]:
    if tool == "vpr":
        labels = parse_vpr(reports)
    elif tool == "vivado":
        labels = parse_vivado(reports)
    else:
        raise ValueError(f"unsupported tool: {tool}")
    labels = normalize_labels(labels)
    return {
        "format": "dataflow_routability_label_v1",
        "design": design,
        "tool": tool,
        "source_reports": [os.path.abspath(path) for path in reports],
        "labels": labels,
        "label_names": sorted(labels),
    }


def write_json(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
        fp.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract routability labels from Vivado or VPR logs/reports.")
    parser.add_argument("--tool", choices=("vivado", "vpr"), required=True)
    parser.add_argument("--design", required=True, help="stable design/kernel id")
    parser.add_argument("--reports", nargs="+", required=True, help="log/report files to parse")
    parser.add_argument("--out", required=True, help="output label JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args.design, args.tool, args.reports)
    write_json(args.out, payload)
    print(f"wrote {args.out}: {args.tool} labels for {args.design}")


if __name__ == "__main__":
    main()
