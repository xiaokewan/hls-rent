#!/usr/bin/env python3
"""PyTorch Geometric wrapper for feature-fusion graph JSON files."""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence


def require_pyg():
    try:
        import torch
        from torch_geometric.data import Data
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "PyTorch Geometric conversion requires torch and torch_geometric. "
            "Install them in the environment before running this wrapper."
        ) from exc
    return torch, Data


def load_feature_graph(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fp:
        payload = json.load(fp)
    if payload.get("format") != "dataflow_gnn_feature_fusion_v1":
        raise ValueError(f"{path} is not a dataflow_gnn_feature_fusion_v1 file")
    return payload


def safe_number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def target_from_payload(payload: Dict[str, Any], target_key: Optional[str]) -> Optional[float]:
    if not target_key:
        return None
    if target_key in payload.get("graph_features", {}):
        return safe_number(payload["graph_features"][target_key])
    if target_key in payload.get("labels", {}):
        return safe_number(payload["labels"][target_key])
    if target_key in payload:
        return safe_number(payload[target_key])
    raise KeyError(f"target key {target_key!r} not found in {payload['source']}")


def to_pyg_data(payload: Dict[str, Any], target_key: Optional[str] = None):
    torch, Data = require_pyg()

    x = torch.tensor([node["x"] for node in payload["nodes"]], dtype=torch.float32)
    edge_pairs = [[edge["src_index"], edge["dst_index"]] for edge in payload["edges"]]
    if edge_pairs:
        edge_index = torch.tensor(edge_pairs, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor([edge["edge_attr"] for edge in payload["edges"]], dtype=torch.float32)
    else:
        edge_index = torch.empty((2, 0), dtype=torch.long)
        edge_attr = torch.empty((0, len(payload["edge_feature_names"])), dtype=torch.float32)

    graph_x = torch.tensor(payload["graph_feature_vector"], dtype=torch.float32).view(1, -1)
    data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr)
    data.graph_x = graph_x
    data.name = payload["name"]
    data.source = payload["source"]
    data.node_feature_names = payload["node_feature_names"]
    data.edge_feature_names = payload["edge_feature_names"]
    data.graph_feature_names = payload["graph_feature_names"]

    target = target_from_payload(payload, target_key)
    if target is not None:
        data.y = torch.tensor([target], dtype=torch.float32)
    return data


def load_pyg_data_list(paths: Sequence[str], target_key: Optional[str] = None) -> List[Any]:
    return [to_pyg_data(load_feature_graph(path), target_key=target_key) for path in paths]


def discover_graphs(path: str) -> List[str]:
    if os.path.isdir(path):
        return sorted(glob.glob(os.path.join(path, "*.gnn.json")))
    return [path]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert feature-fusion JSON files to PyG Data objects.")
    parser.add_argument("path", help="feature JSON file or directory containing *.gnn.json")
    parser.add_argument("--target", help="graph feature key to use as data.y")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = discover_graphs(args.path)
    data_list = load_pyg_data_list(paths, target_key=args.target)
    print(f"loaded {len(data_list)} PyG Data objects")
    if data_list:
        first = data_list[0]
        print(f"first: name={first.name}, x={tuple(first.x.shape)}, edge_index={tuple(first.edge_index.shape)}")
        if hasattr(first, "edge_attr"):
            print(f"edge_attr={tuple(first.edge_attr.shape)}, graph_x={tuple(first.graph_x.shape)}")
        if hasattr(first, "y"):
            print(f"y={first.y.tolist()}")


if __name__ == "__main__":
    main()
