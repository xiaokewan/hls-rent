#!/usr/bin/env python3
"""Attach routability labels to a GNN feature-fusion graph."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def write_json(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
        fp.write("\n")


def attach(feature_payload: Dict[str, Any], label_payload: Dict[str, Any]) -> Dict[str, Any]:
    if feature_payload.get("format") != "dataflow_gnn_feature_fusion_v1":
        raise ValueError("feature input is not dataflow_gnn_feature_fusion_v1")
    if label_payload.get("format") != "dataflow_routability_label_v1":
        raise ValueError("label input is not dataflow_routability_label_v1")

    merged = dict(feature_payload)
    merged["labels"] = label_payload.get("labels", {})
    merged["label_names"] = label_payload.get("label_names", sorted(merged["labels"]))
    merged["label_metadata"] = {
        "format": label_payload.get("format"),
        "design": label_payload.get("design"),
        "tool": label_payload.get("tool"),
        "source_reports": label_payload.get("source_reports", []),
    }
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attach routability labels to a feature-fusion graph JSON.")
    parser.add_argument("--features", required=True, help="input *.gnn.json")
    parser.add_argument("--labels", required=True, help="input routability label JSON")
    parser.add_argument("--out", required=True, help="output labeled *.gnn.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = attach(read_json(args.features), read_json(args.labels))
    write_json(args.out, payload)
    print(f"wrote {args.out}: {len(payload.get('labels', {}))} labels attached")


if __name__ == "__main__":
    main()
