#!/usr/bin/env python3
"""Build hierarchical Rent/dataflow communication features.

This script complements gnn_feature_fusion.py. Instead of producing one fixed
node embedding, it records how communication pressure changes along each
node's containment path through recursive partitions.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence, Tuple


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from dataflow_comm_scaling import (  # noqa: E402
    Edge,
    Node,
    build_regions,
    fit_power_law,
    load_graph,
    score_region,
    summarize,
)


PATH_METRICS = [
    "T_plain",
    "C_bit",
    "C_bw",
    "C_mem",
    "C_tensor",
    "C_ctrl",
    "C_reduce",
    "flow_balance",
    "memory_fraction",
    "fanout_weighted_cut",
]


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


def parse_csv_list(value: str, cast) -> List[Any]:
    return [cast(item.strip()) for item in value.split(",") if item.strip()]


def analysis_id(partition: str, min_nodes: int) -> str:
    return f"{partition}_min{min_nodes}"


def prefix_for(partition: str, min_nodes: int) -> str:
    return f"{partition}_m{min_nodes}"


def row_without_nodes(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in row.items() if key != "node_ids"}


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def depth_summary(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_depth: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_depth[int(row["level"])].append(row)

    summaries = []
    for level in sorted(by_depth):
        level_rows = by_depth[level]
        summaries.append(
            {
                "level": level,
                "n_regions": len(level_rows),
                "mean_B_node": mean([safe_number(row["B_node"]) for row in level_rows]),
                "mean_C_bw": mean([safe_number(row["C_bw"]) for row in level_rows]),
                "max_C_bw": max((safe_number(row["C_bw"]) for row in level_rows), default=0.0),
                "mean_C_mem": mean([safe_number(row["C_mem"]) for row in level_rows]),
                "mean_flow_balance": mean([safe_number(row["flow_balance"]) for row in level_rows]),
                "mean_memory_fraction": mean([safe_number(row["memory_fraction"]) for row in level_rows]),
            }
        )
    return summaries


def node_paths(rows: Sequence[Dict[str, Any]], node_ids: Iterable[str]) -> Dict[str, List[Dict[str, Any]]]:
    paths: Dict[str, List[Dict[str, Any]]] = {node_id: [] for node_id in node_ids}
    for row in rows:
        for node_id in row["node_ids"]:
            paths[node_id].append(row)
    for node_id in paths:
        paths[node_id].sort(key=lambda row: (int(row["level"]), -int(row["B_node"]), str(row["region_id"])))
    return paths


def path_alpha(path_rows: Sequence[Dict[str, Any]], metric: str) -> float:
    fit = fit_power_law(path_rows, "B_node", metric)
    return safe_number(fit["alpha"])


def node_feature_dict(path_rows: Sequence[Dict[str, Any]], prefix: str) -> Dict[str, float]:
    features: Dict[str, float] = {}
    non_root = [row for row in path_rows if row["region_id"] != "r"]
    usable = non_root if non_root else list(path_rows)

    for metric in ("T_plain", "C_bit", "C_bw", "C_mem", "C_tensor", "C_ctrl", "C_reduce"):
        features[f"{prefix}_path_alpha_{metric}"] = path_alpha(usable, metric)
        features[f"{prefix}_path_max_{metric}"] = max((safe_number(row[metric]) for row in usable), default=0.0)
        features[f"{prefix}_path_mean_{metric}"] = mean([safe_number(row[metric]) for row in usable])

    features[f"{prefix}_path_mean_flow_balance"] = mean([safe_number(row["flow_balance"]) for row in usable])
    features[f"{prefix}_path_max_flow_balance"] = max((safe_number(row["flow_balance"]) for row in usable), default=0.0)
    features[f"{prefix}_path_mean_memory_fraction"] = mean([safe_number(row["memory_fraction"]) for row in usable])
    features[f"{prefix}_path_max_memory_fraction"] = max(
        (safe_number(row["memory_fraction"]) for row in usable), default=0.0
    )
    features[f"{prefix}_path_depth"] = float(max((int(row["level"]) for row in path_rows), default=0))
    return features


def graph_feature_dict(summary: Dict[str, Any], prefix: str) -> Dict[str, float]:
    features: Dict[str, float] = {}
    for name, fit in summary["fits"].items():
        features[f"{prefix}_{name}"] = safe_number(fit.get("alpha"))
        features[f"{prefix}_{name.replace('alpha_', 'k_')}"] = safe_number(fit.get("k"))
    for key, value in summary["aggregate"].items():
        features[f"{prefix}_{key}"] = safe_number(value)
    return features


def vectorize(names: Sequence[str], features: Dict[str, float]) -> List[float]:
    return [safe_number(features.get(name, 0.0)) for name in names]


def build_multilevel_features(
    path: str,
    partitions: Sequence[str],
    min_nodes_values: Sequence[int],
    include_region_rows: bool = False,
) -> Dict[str, Any]:
    nodes, edges, meta = load_graph(path)
    node_by_id = {node.id: node for node in nodes}

    analyses = []
    graph_features: Dict[str, float] = {}
    per_node_features: Dict[str, Dict[str, float]] = {node.id: {} for node in nodes}

    for partition in partitions:
        for min_nodes in min_nodes_values:
            prefix = prefix_for(partition, min_nodes)
            regions = build_regions(nodes, edges, min_nodes=min_nodes, partition=partition)
            rows = [score_region(region, node_by_id, edges) for region in regions]
            summary = summarize(rows, nodes, edges, meta, partition=partition, seed=0)
            graph_features.update(graph_feature_dict(summary, prefix))

            paths = node_paths(rows, per_node_features)
            for node_id, path_rows in paths.items():
                per_node_features[node_id].update(node_feature_dict(path_rows, prefix))

            analysis = {
                "id": analysis_id(partition, min_nodes),
                "partition": partition,
                "min_nodes": min_nodes,
                "summary": summary,
                "depth_summary": depth_summary(rows),
            }
            if include_region_rows:
                analysis["regions"] = [row_without_nodes(row) for row in rows]
            analyses.append(analysis)

    node_feature_names = sorted({name for features in per_node_features.values() for name in features})
    graph_feature_names = sorted(graph_features)
    out_nodes = [
        {
            "id": node.id,
            "op": node.op,
            "kind": node.kind,
            "features": per_node_features[node.id],
            "x": vectorize(node_feature_names, per_node_features[node.id]),
        }
        for node in nodes
    ]

    return {
        "format": "dataflow_multilevel_rent_v1",
        "name": meta["name"],
        "description": meta["description"],
        "source": meta["source"],
        "partitions": list(partitions),
        "min_nodes_values": list(min_nodes_values),
        "node_feature_names": node_feature_names,
        "graph_feature_names": graph_feature_names,
        "graph_features": graph_features,
        "graph_feature_vector": vectorize(graph_feature_names, graph_features),
        "nodes": out_nodes,
        "analyses": analyses,
    }


def write_json(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
        fp.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build hierarchical Rent/dataflow communication features.")
    parser.add_argument("graph_json", help="input normalized dataflow graph JSON")
    parser.add_argument("--out", required=True, help="output multilevel feature JSON")
    parser.add_argument(
        "--partitions",
        default="topological",
        help="comma-separated partition strategies: topological,mincut,random",
    )
    parser.add_argument("--min-nodes", default="1,4,16", help="comma-separated recursive stop sizes")
    parser.add_argument("--include-region-rows", action="store_true", help="store all region rows in output JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_multilevel_features(
        args.graph_json,
        partitions=parse_csv_list(args.partitions, str),
        min_nodes_values=parse_csv_list(args.min_nodes, int),
        include_region_rows=args.include_region_rows,
    )
    write_json(args.out, payload)
    print(
        f"wrote {args.out}: {len(payload['nodes'])} nodes, "
        f"{len(payload['node_feature_names'])} node features, "
        f"{len(payload['analyses'])} hierarchy analyses"
    )


if __name__ == "__main__":
    main()
