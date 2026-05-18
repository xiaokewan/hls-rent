#!/usr/bin/env python3
"""Lightweight ablation for GNN feature-fusion JSON files.

This is not a replacement for a real GNN. It is a fast smoke test that asks
whether dataflow/Rentian features add signal beyond raw graph/operator features.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge


RAW_NODE_FEATURES = {
    "node_area",
    "kind_compute",
    "kind_memory",
    "kind_io",
    "kind_control",
    "kind_other",
    "op_arith",
    "op_memory",
    "op_io",
    "op_control",
    "op_dataflow",
    "op_other",
    "in_degree",
    "out_degree",
    "total_degree",
}

TRAFFIC_NODE_FEATURES = {
    "in_bit",
    "out_bit",
    "in_bw",
    "out_bw",
    "total_bw",
    "memory_in_bw",
    "memory_out_bw",
    "tensor_in_bw",
    "tensor_out_bw",
    "control_in_bw",
    "control_out_bw",
    "reduce_in_bw",
    "reduce_out_bw",
    "fanout_weighted_out_bw",
    "node_flow_balance",
}

RENT_NODE_PREFIXES = ("ego_", "region_")

EDGE_FEATURES = {
    "width",
    "rate",
    "bit_demand",
    "bw_demand",
    "buffer_demand",
    "fanout",
    "is_memory",
    "is_tensor",
    "is_control",
    "is_reduce",
}

RENT_GRAPH_FEATURES = {
    "global_alpha_plain",
    "global_alpha_bit",
    "global_alpha_bw",
    "global_alpha_mem",
    "global_alpha_tensor",
    "global_alpha_ctrl",
    "global_alpha_reduce",
    "global_mean_flow_balance",
    "global_memory_fraction",
    "global_tensor_fraction",
    "global_control_fraction",
    "global_reduce_fraction",
}


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


def load_payload(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fp:
        payload = json.load(fp)
    if payload.get("format") != "dataflow_gnn_feature_fusion_v1":
        raise ValueError(f"{path} is not a feature-fusion graph")
    return payload


def discover(path: str, pattern: str) -> List[str]:
    if os.path.isdir(path):
        return sorted(glob.glob(os.path.join(path, pattern)))
    return [path]


def aggregate_feature(values: Sequence[float], name: str, output: Dict[str, float]) -> None:
    if not values:
        output[f"{name}:sum"] = 0.0
        output[f"{name}:mean"] = 0.0
        output[f"{name}:max"] = 0.0
        return
    output[f"{name}:sum"] = float(np.sum(values))
    output[f"{name}:mean"] = float(np.mean(values))
    output[f"{name}:max"] = float(np.max(values))


def selected_node_names(payload: Dict[str, Any], group: str) -> List[str]:
    names = payload["node_feature_names"]
    if group == "raw":
        return [name for name in names if name in RAW_NODE_FEATURES]
    if group == "edge":
        return [name for name in names if name in RAW_NODE_FEATURES or name in TRAFFIC_NODE_FEATURES]
    if group == "rent":
        return [
            name
            for name in names
            if name in RAW_NODE_FEATURES
            or name in TRAFFIC_NODE_FEATURES
            or name.startswith(RENT_NODE_PREFIXES)
        ]
    raise ValueError(f"unknown feature group: {group}")


def selected_edge_names(payload: Dict[str, Any], group: str) -> List[str]:
    if group == "raw":
        return []
    return [name for name in payload["edge_feature_names"] if name in EDGE_FEATURES]


def selected_graph_names(payload: Dict[str, Any], group: str, target: str) -> List[str]:
    if group != "rent":
        return []
    names = []
    for name in payload["graph_feature_names"]:
        if name == target:
            continue
        if name.startswith("global_k_"):
            continue
        if name in RENT_GRAPH_FEATURES:
            names.append(name)
    return names


def graph_to_tabular_features(payload: Dict[str, Any], group: str, target: str) -> Dict[str, float]:
    features: Dict[str, float] = {
        "n_nodes": safe_number(len(payload["nodes"])),
        "n_edges": safe_number(len(payload["edges"])),
    }

    for name in selected_node_names(payload, group):
        aggregate_feature([safe_number(node["features"].get(name)) for node in payload["nodes"]], f"node.{name}", features)

    for name in selected_edge_names(payload, group):
        aggregate_feature([safe_number(edge["features"].get(name)) for edge in payload["edges"]], f"edge.{name}", features)

    graph_features = payload["graph_features"]
    for name in selected_graph_names(payload, group, target):
        features[f"graph.{name}"] = safe_number(graph_features.get(name))
    return features


def target_value(payload: Dict[str, Any], target: str, log_target: bool) -> float:
    if target not in payload["graph_features"]:
        raise KeyError(f"target {target!r} not found in graph_features for {payload['source']}")
    value = safe_number(payload["graph_features"][target])
    if log_target:
        return math.log2(max(value, 1e-9))
    return value


def vectorize(dicts: Sequence[Dict[str, float]]) -> Tuple[np.ndarray, List[str]]:
    names = sorted({name for item in dicts for name in item})
    matrix = np.array([[item.get(name, 0.0) for name in names] for item in dicts], dtype=float)
    return matrix, names


def evaluate_group(payloads: Sequence[Dict[str, Any]], group: str, target: str, log_target: bool) -> Dict[str, Any]:
    feature_dicts = [graph_to_tabular_features(payload, group, target) for payload in payloads]
    x, names = vectorize(feature_dicts)
    y = np.array([target_value(payload, target, log_target) for payload in payloads], dtype=float)

    if len(payloads) < 3:
        raise ValueError("need at least three feature graphs for cross-validation")

    # Ridge is intentionally simple and stable for small toy datasets.
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    predictions = cross_val_predict(model, x, y, cv=LeaveOneOut())
    rmse = float(math.sqrt(mean_squared_error(y, predictions)))
    mae = float(mean_absolute_error(y, predictions))
    r2 = float(r2_score(y, predictions)) if len(set(y.tolist())) > 1 else 0.0
    return {
        "group": group,
        "n_graphs": len(payloads),
        "n_features": len(names),
        "target": target,
        "log_target": log_target,
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a toy ablation over feature-fusion graph JSON files.")
    parser.add_argument("path", help="feature JSON file or directory containing *.gnn.json")
    parser.add_argument("--pattern", default="*.gnn.json", help="glob pattern used when path is a directory")
    parser.add_argument("--target", default="global_k_bw", help="graph feature to predict")
    parser.add_argument("--no-log-target", action="store_true", help="do not log2-transform the target")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = discover(args.path, args.pattern)
    payloads = [load_payload(path) for path in paths]
    if not payloads:
        raise SystemExit(f"no *.gnn.json files found under {args.path}")

    print(f"loaded {len(payloads)} feature graphs")
    print(f"target: {args.target} ({'raw' if args.no_log_target else 'log2'})")
    for group in ("raw", "edge", "rent"):
        result = evaluate_group(payloads, group, args.target, not args.no_log_target)
        print(
            f"{group:>4}: "
            f"features={result['n_features']:3d}, "
            f"MAE={result['mae']:.4f}, "
            f"RMSE={result['rmse']:.4f}, "
            f"R2={result['r2']:.4f}"
        )


if __name__ == "__main__":
    main()
