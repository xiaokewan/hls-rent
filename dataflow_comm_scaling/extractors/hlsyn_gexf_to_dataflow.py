#!/usr/bin/env python3
"""Convert HLSyn ProGraML GEXF graphs to normalized dataflow JSON.

HLSyn stores pragma-augmented ProGraML graphs as GEXF files. This converter
turns those real HLS program graphs into the normalized schema consumed by
dataflow_comm_scaling.py and gnn_feature_fusion.py.

The conversion is intentionally conservative:

- ProGraML flow=0 is treated as control.
- ProGraML flow=1 is treated as data.
- ProGraML flow=2 is treated as call/external data.
- Other flow values are kept as pragma/control-like edges.

Bitwidth is recovered heuristically from LLVM-like node text/full_text. When no
width can be inferred, data edges default to 32 bits and control edges to 1 bit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any, Dict, Iterable, Optional

import networkx as nx


PRAGMA_TEXT = {
    "PIPELINE",
    "UNROLL",
    "TILE",
    "PARALLEL",
    "INLINE",
    "ARRAY_PARTITION",
    "ARRAY_RESHAPE",
}

MEMORY_OPS = {"alloca", "load", "store", "getelementptr"}
CONTROL_OPS = {"br", "ret", "switch", "select", "phi"}
ARITH_OPS = {
    "add",
    "fadd",
    "sub",
    "fsub",
    "mul",
    "fmul",
    "div",
    "fdiv",
    "sdiv",
    "udiv",
    "icmp",
    "fcmp",
    "and",
    "or",
    "xor",
    "shl",
    "ashr",
    "lshr",
    "zext",
    "sext",
    "trunc",
}


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def node_text(attrs: Dict[str, Any]) -> str:
    return str(attrs.get("text", "")).strip()


def node_full_text(attrs: Dict[str, Any]) -> str:
    return str(attrs.get("full_text", attrs.get("text", ""))).strip()


def infer_width_from_text(text: str) -> Optional[int]:
    candidates = [int(match) for match in re.findall(r"\bi(\d+)\b", text)]
    if candidates:
        return max(candidates)

    array_match = re.search(r"\[(\d+)\s+x\s+i(\d+)\]", text)
    if array_match:
        return int(array_match.group(1)) * int(array_match.group(2))

    if "float" in text:
        return 32
    if "double" in text:
        return 64
    return None


def infer_node_width(attrs: Dict[str, Any]) -> int:
    return infer_width_from_text(node_full_text(attrs)) or infer_width_from_text(node_text(attrs)) or 32


def classify_node(attrs: Dict[str, Any]) -> Dict[str, str]:
    text = node_text(attrs)
    upper_text = text.upper()
    op = text if text else "unknown"

    if upper_text in PRAGMA_TEXT:
        return {"op": upper_text.lower(), "kind": "pragma"}
    if text in MEMORY_OPS or "*" in text:
        return {"op": op, "kind": "memory"}
    if text in CONTROL_OPS:
        return {"op": op, "kind": "control"}
    if text in ARITH_OPS:
        return {"op": op, "kind": "compute"}
    if text.startswith("i") or text.startswith("["):
        return {"op": "value", "kind": "value"}
    if text == "[external]":
        return {"op": "external", "kind": "io"}
    return {"op": op, "kind": "compute"}


def classify_edge(flow: int, src_kind: str, dst_kind: str) -> Dict[str, str]:
    if flow == 0:
        return {"kind": "control", "semantic": "control"}
    if flow == 1:
        if "memory" in {src_kind, dst_kind}:
            return {"kind": "memory", "semantic": "memory"}
        return {"kind": "data", "semantic": "scalar"}
    if flow == 2:
        return {"kind": "call", "semantic": "external"}
    return {"kind": "pragma", "semantic": "control"}


def edge_width(flow: int, src_attrs: Dict[str, Any], dst_attrs: Dict[str, Any]) -> int:
    if flow == 0:
        return 1
    if flow not in {1, 2}:
        return 1
    return max(infer_node_width(src_attrs), infer_node_width(dst_attrs))


def normalized_node_id(raw_id: Any) -> str:
    return f"n{raw_id}"


def convert_gexf(path: str, source_file: Optional[str] = None) -> Dict[str, Any]:
    graph = nx.read_gexf(path)
    node_attrs = dict(graph.nodes(data=True))

    nodes = []
    kind_by_raw_id = {}
    for raw_id, attrs in sorted(node_attrs.items(), key=lambda item: str(item[0])):
        classification = classify_node(attrs)
        kind_by_raw_id[raw_id] = classification["kind"]
        width = infer_node_width(attrs)
        node = {
            "id": normalized_node_id(raw_id),
            "op": classification["op"],
            "kind": classification["kind"],
            "area": 1,
            "hlsyn_node_id": str(raw_id),
            "programl_type": safe_int(attrs.get("type"), 0),
            "programl_block": safe_int(attrs.get("block"), 0),
            "programl_function": safe_int(attrs.get("function"), 0),
            "inferred_width": width,
            "text": node_text(attrs),
        }
        full_text = node_full_text(attrs)
        if full_text and full_text != node["text"]:
            node["full_text"] = full_text
        if source_file:
            node["source_file"] = source_file
        nodes.append(node)

    edges = []
    for raw_src, raw_dst, attrs in graph.edges(data=True):
        src_attrs = node_attrs[raw_src]
        dst_attrs = node_attrs[raw_dst]
        flow = safe_int(attrs.get("flow"), 1)
        classification = classify_edge(flow, kind_by_raw_id[raw_src], kind_by_raw_id[raw_dst])
        width = edge_width(flow, src_attrs, dst_attrs)
        edges.append(
            {
                "src": normalized_node_id(raw_src),
                "dst": normalized_node_id(raw_dst),
                "width": width,
                "rate": 1,
                "kind": classification["kind"],
                "semantic": classification["semantic"],
                "programl_flow": flow,
                "programl_position": safe_int(attrs.get("position"), 0),
            }
        )

    return {
        "name": os.path.basename(path).replace("_processed_result.gexf", ""),
        "description": "Converted from HLSyn pragma-augmented ProGraML GEXF.",
        "source_graph": path,
        "source_file": source_file or "",
        "nodes": nodes,
        "edges": edges,
    }


def write_json(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
        fp.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert an HLSyn ProGraML GEXF file to normalized dataflow JSON.")
    parser.add_argument("gexf", help="input HLSyn *_processed_result.gexf file")
    parser.add_argument("--source-file", help="optional source C file path")
    parser.add_argument("--out", required=True, help="output normalized dataflow JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = convert_gexf(args.gexf, source_file=args.source_file)
    write_json(args.out, payload)
    print(f"wrote {args.out}: {len(payload['nodes'])} nodes, {len(payload['edges'])} edges")


if __name__ == "__main__":
    main()
