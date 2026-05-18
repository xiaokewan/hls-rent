#!/usr/bin/env python3
"""Build GNN-ready feature-fusion graphs.

This script implements the first GNN integration path:

1. Load a normalized dataflow graph JSON.
2. Compute global dataflow communication scaling features.
3. Compute per-node local communication scaling features from ego subgraphs.
4. Export node, edge, and graph feature vectors in a dependency-free JSON format.

The output is intentionally framework-neutral. It can be converted to PyTorch
Geometric, DGL, TensorFlow GNN, or a custom training pipeline later.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict, deque
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

from dataflow_comm_scaling import (
    CONTROL_TAGS,
    MEMORY_TAGS,
    REDUCE_TAGS,
    TENSOR_TAGS,
    Edge,
    Node,
    Region,
    analyze,
    build_regions,
    fit_power_law,
    load_graph,
    score_region,
)


NODE_PROVENANCE_KEYS = [
    "source_file",
    "line",
    "column",
    "function",
    "loop_id",
    "basic_block",
    "ir_source_file",
    "ir_line",
    "pragma_ids",
    "pragma_kinds",
    "pragma_texts",
]

EDGE_PROVENANCE_KEYS = [
    "source_file",
    "line",
    "column",
    "producer_source_file",
    "consumer_source_file",
    "producer_line",
    "consumer_line",
    "loop_id",
    "pragma_ids",
    "pragma_kinds",
    "pragma_texts",
]

NODE_FEATURE_NAMES = [
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
    "ego_alpha_plain",
    "ego_alpha_bit",
    "ego_alpha_bw",
    "ego_alpha_mem",
    "ego_alpha_tensor",
    "ego_alpha_ctrl",
    "ego_alpha_reduce",
    "ego_max_C_bit",
    "ego_max_C_bw",
    "ego_max_C_mem",
    "ego_max_C_tensor",
    "ego_max_C_ctrl",
    "ego_max_C_reduce",
    "ego_max_flow_balance",
    "region_mean_C_bit",
    "region_mean_C_bw",
    "region_mean_flow_balance",
    "region_max_C_bw",
    "region_max_memory_fraction",
]

EDGE_FEATURE_NAMES = [
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
]

GRAPH_FEATURE_NAMES = [
    "n_nodes",
    "n_edges",
    "global_alpha_plain",
    "global_alpha_bit",
    "global_alpha_bw",
    "global_alpha_mem",
    "global_alpha_tensor",
    "global_alpha_ctrl",
    "global_alpha_reduce",
    "global_k_plain",
    "global_k_bit",
    "global_k_bw",
    "global_mean_flow_balance",
    "global_memory_fraction",
    "global_tensor_fraction",
    "global_control_fraction",
    "global_reduce_fraction",
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


def load_raw_maps(path: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[Tuple[str, str, int], Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as fp:
        payload = json.load(fp)
    node_map = {str(item["id"]): item for item in payload.get("nodes", [])}
    edge_map = {}
    for index, item in enumerate(payload.get("edges", [])):
        edge_map[(str(item["src"]), str(item["dst"]), index)] = item
    return node_map, edge_map


def extract_provenance(raw: Dict[str, Any], keys: Sequence[str]) -> Dict[str, Any]:
    return {key: raw[key] for key in keys if key in raw}


def lower(value: str) -> str:
    return value.lower().replace("-", "_")


def is_kind(node: Node, name: str) -> float:
    return 1.0 if lower(node.kind) == name else 0.0


def op_group(node: Node) -> str:
    op = lower(node.op)
    kind = lower(node.kind)
    if op in {"add", "sub", "mul", "div", "mac", "fma", "cmp", "and", "or", "xor", "shift"}:
        return "arith"
    if op in {"load", "store"} or kind == "memory":
        return "memory"
    if op in {"input", "output", "stream_in", "stream_out"} or kind == "io":
        return "io"
    if op in {"branch", "select", "phi", "mux"} or kind == "control":
        return "control"
    if op in {"stage", "stencil", "query", "key", "softmax", "reduce", "reduction"}:
        return "dataflow"
    return "other"


def tag_value(edge: Edge, tags: Set[str]) -> float:
    return 1.0 if edge.has_any_tag(tags) else 0.0


def build_undirected_neighbors(nodes: Sequence[Node], edges: Sequence[Edge]) -> Dict[str, Set[str]]:
    neighbors = {node.id: set() for node in nodes}
    for edge in edges:
        neighbors[edge.src].add(edge.dst)
        neighbors[edge.dst].add(edge.src)
    return neighbors


def ego_nodes(center: str, neighbors: Dict[str, Set[str]], radius: int) -> Set[str]:
    seen = {center}
    queue = deque([(center, 0)])
    while queue:
        node_id, depth = queue.popleft()
        if depth == radius:
            continue
        for next_id in sorted(neighbors[node_id]):
            if next_id not in seen:
                seen.add(next_id)
                queue.append((next_id, depth + 1))
    return seen


def region_row_for_nodes(
    region_id: str,
    node_ids: Iterable[str],
    node_by_id: Dict[str, Node],
    edges: Sequence[Edge],
) -> Dict[str, Any]:
    ordered = tuple(node_id for node_id in node_by_id if node_id in set(node_ids))
    return score_region(Region(region_id, 0, ordered), node_by_id, edges)


def alpha_or_zero(rows: Sequence[Dict[str, Any]], metric: str) -> float:
    return safe_number(fit_power_law(rows, "B_node", metric)["alpha"])


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def node_base_features(node: Node, incoming: Sequence[Edge], outgoing: Sequence[Edge]) -> Dict[str, float]:
    in_bit = sum(edge.bit_demand for edge in incoming)
    out_bit = sum(edge.bit_demand for edge in outgoing)
    in_bw = sum(edge.bw_demand for edge in incoming)
    out_bw = sum(edge.bw_demand for edge in outgoing)
    total_bw = in_bw + out_bw
    group = op_group(node)
    known_kind = lower(node.kind) in {"compute", "memory", "io", "control"}
    return {
        "node_area": node.area,
        "kind_compute": is_kind(node, "compute"),
        "kind_memory": is_kind(node, "memory"),
        "kind_io": is_kind(node, "io"),
        "kind_control": is_kind(node, "control"),
        "kind_other": 0.0 if known_kind else 1.0,
        "op_arith": 1.0 if group == "arith" else 0.0,
        "op_memory": 1.0 if group == "memory" else 0.0,
        "op_io": 1.0 if group == "io" else 0.0,
        "op_control": 1.0 if group == "control" else 0.0,
        "op_dataflow": 1.0 if group == "dataflow" else 0.0,
        "op_other": 1.0 if group == "other" else 0.0,
        "in_degree": float(len(incoming)),
        "out_degree": float(len(outgoing)),
        "total_degree": float(len(incoming) + len(outgoing)),
        "in_bit": in_bit,
        "out_bit": out_bit,
        "in_bw": in_bw,
        "out_bw": out_bw,
        "total_bw": total_bw,
        "memory_in_bw": sum(edge.bw_demand for edge in incoming if edge.has_any_tag(MEMORY_TAGS)),
        "memory_out_bw": sum(edge.bw_demand for edge in outgoing if edge.has_any_tag(MEMORY_TAGS)),
        "tensor_in_bw": sum(edge.bw_demand for edge in incoming if edge.has_any_tag(TENSOR_TAGS)),
        "tensor_out_bw": sum(edge.bw_demand for edge in outgoing if edge.has_any_tag(TENSOR_TAGS)),
        "control_in_bw": sum(edge.bw_demand for edge in incoming if edge.has_any_tag(CONTROL_TAGS)),
        "control_out_bw": sum(edge.bw_demand for edge in outgoing if edge.has_any_tag(CONTROL_TAGS)),
        "reduce_in_bw": sum(edge.bw_demand for edge in incoming if edge.has_any_tag(REDUCE_TAGS)),
        "reduce_out_bw": sum(edge.bw_demand for edge in outgoing if edge.has_any_tag(REDUCE_TAGS)),
        "fanout_weighted_out_bw": sum(edge.bw_demand * edge.fanout for edge in outgoing),
        "node_flow_balance": abs(out_bw - in_bw) / total_bw if total_bw > 0 else 0.0,
    }


def node_ego_features(
    node: Node,
    neighbors: Dict[str, Set[str]],
    node_by_id: Dict[str, Node],
    edges: Sequence[Edge],
    max_radius: int,
) -> Dict[str, float]:
    rows = []
    for radius in range(1, max_radius + 1):
        local_nodes = ego_nodes(node.id, neighbors, radius)
        row = region_row_for_nodes(f"ego_{node.id}_r{radius}", local_nodes, node_by_id, edges)
        rows.append(row)

    return {
        "ego_alpha_plain": alpha_or_zero(rows, "T_plain"),
        "ego_alpha_bit": alpha_or_zero(rows, "C_bit"),
        "ego_alpha_bw": alpha_or_zero(rows, "C_bw"),
        "ego_alpha_mem": alpha_or_zero(rows, "C_mem"),
        "ego_alpha_tensor": alpha_or_zero(rows, "C_tensor"),
        "ego_alpha_ctrl": alpha_or_zero(rows, "C_ctrl"),
        "ego_alpha_reduce": alpha_or_zero(rows, "C_reduce"),
        "ego_max_C_bit": max((safe_number(row["C_bit"]) for row in rows), default=0.0),
        "ego_max_C_bw": max((safe_number(row["C_bw"]) for row in rows), default=0.0),
        "ego_max_C_mem": max((safe_number(row["C_mem"]) for row in rows), default=0.0),
        "ego_max_C_tensor": max((safe_number(row["C_tensor"]) for row in rows), default=0.0),
        "ego_max_C_ctrl": max((safe_number(row["C_ctrl"]) for row in rows), default=0.0),
        "ego_max_C_reduce": max((safe_number(row["C_reduce"]) for row in rows), default=0.0),
        "ego_max_flow_balance": max((safe_number(row["flow_balance"]) for row in rows), default=0.0),
    }


def partition_context_by_node(
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    partition: str,
    seed: int,
) -> Dict[str, Dict[str, float]]:
    node_by_id = {node.id: node for node in nodes}
    regions = build_regions(nodes, edges, partition=partition, seed=seed)
    rows = [score_region(region, node_by_id, edges) for region in regions]
    by_node: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["region_id"] == "r" or row["B_node"] <= 1:
            continue
        for node_id in row["node_ids"]:
            by_node[node_id].append(row)

    context = {}
    for node in nodes:
        rows_for_node = by_node[node.id]
        context[node.id] = {
            "region_mean_C_bit": mean([safe_number(row["C_bit"]) for row in rows_for_node]),
            "region_mean_C_bw": mean([safe_number(row["C_bw"]) for row in rows_for_node]),
            "region_mean_flow_balance": mean([safe_number(row["flow_balance"]) for row in rows_for_node]),
            "region_max_C_bw": max((safe_number(row["C_bw"]) for row in rows_for_node), default=0.0),
            "region_max_memory_fraction": max((safe_number(row["memory_fraction"]) for row in rows_for_node), default=0.0),
        }
    return context


def edge_features(edge: Edge) -> Dict[str, float]:
    return {
        "width": edge.width,
        "rate": edge.rate,
        "bit_demand": edge.bit_demand,
        "bw_demand": edge.bw_demand,
        "buffer_demand": edge.buffer_demand,
        "fanout": edge.fanout,
        "is_memory": tag_value(edge, MEMORY_TAGS),
        "is_tensor": tag_value(edge, TENSOR_TAGS),
        "is_control": tag_value(edge, CONTROL_TAGS),
        "is_reduce": tag_value(edge, REDUCE_TAGS),
    }


def graph_features(summary: Dict[str, Any]) -> Dict[str, float]:
    fits = summary["fits"]
    aggregate = summary["aggregate"]
    return {
        "n_nodes": safe_number(summary["n_nodes"]),
        "n_edges": safe_number(summary["n_edges"]),
        "global_alpha_plain": safe_number(fits["alpha_plain"]["alpha"]),
        "global_alpha_bit": safe_number(fits["alpha_bit"]["alpha"]),
        "global_alpha_bw": safe_number(fits["alpha_bw"]["alpha"]),
        "global_alpha_mem": safe_number(fits["alpha_mem"]["alpha"]),
        "global_alpha_tensor": safe_number(fits["alpha_tensor"]["alpha"]),
        "global_alpha_ctrl": safe_number(fits["alpha_ctrl"]["alpha"]),
        "global_alpha_reduce": safe_number(fits["alpha_reduce"]["alpha"]),
        "global_k_plain": safe_number(fits["alpha_plain"]["k"]),
        "global_k_bit": safe_number(fits["alpha_bit"]["k"]),
        "global_k_bw": safe_number(fits["alpha_bw"]["k"]),
        "global_mean_flow_balance": safe_number(aggregate["mean_flow_balance"]),
        "global_memory_fraction": safe_number(aggregate["memory_fraction"]),
        "global_tensor_fraction": safe_number(aggregate["tensor_fraction"]),
        "global_control_fraction": safe_number(aggregate["control_fraction"]),
        "global_reduce_fraction": safe_number(aggregate["reduce_fraction"]),
    }


def vectorize(feature_names: Sequence[str], features: Dict[str, float]) -> List[float]:
    return [safe_number(features.get(name, 0.0)) for name in feature_names]


def build_feature_graph(
    path: str,
    partition: str = "topological",
    seed: int = 0,
    max_radius: int = 3,
) -> Dict[str, Any]:
    nodes, edges, meta = load_graph(path)
    raw_nodes, raw_edges = load_raw_maps(path)
    node_by_id = {node.id: node for node in nodes}
    node_index = {node.id: index for index, node in enumerate(nodes)}
    incoming: Dict[str, List[Edge]] = defaultdict(list)
    outgoing: Dict[str, List[Edge]] = defaultdict(list)
    for edge in edges:
        incoming[edge.dst].append(edge)
        outgoing[edge.src].append(edge)

    summary, _ = analyze(path, partition=partition, seed=seed)
    graph_feature_dict = graph_features(summary)
    neighbors = build_undirected_neighbors(nodes, edges)
    region_context = partition_context_by_node(nodes, edges, partition, seed)

    out_nodes = []
    for node in nodes:
        feature_dict = {}
        feature_dict.update(node_base_features(node, incoming[node.id], outgoing[node.id]))
        feature_dict.update(node_ego_features(node, neighbors, node_by_id, edges, max_radius))
        feature_dict.update(region_context[node.id])
        out_nodes.append(
            {
                "id": node.id,
                "index": node_index[node.id],
                "op": node.op,
                "kind": node.kind,
                "provenance": extract_provenance(raw_nodes.get(node.id, {}), NODE_PROVENANCE_KEYS),
                "features": feature_dict,
                "x": vectorize(NODE_FEATURE_NAMES, feature_dict),
            }
        )

    out_edges = []
    for edge_index, edge in enumerate(edges):
        feature_dict = edge_features(edge)
        raw_edge = raw_edges.get((edge.src, edge.dst, edge_index), {})
        out_edges.append(
            {
                "src": edge.src,
                "dst": edge.dst,
                "src_index": node_index[edge.src],
                "dst_index": node_index[edge.dst],
                "kind": edge.kind,
                "semantic": edge.semantic,
                "provenance": extract_provenance(raw_edge, EDGE_PROVENANCE_KEYS),
                "features": feature_dict,
                "edge_attr": vectorize(EDGE_FEATURE_NAMES, feature_dict),
            }
        )

    return {
        "name": meta["name"],
        "description": meta["description"],
        "source": meta["source"],
        "format": "dataflow_gnn_feature_fusion_v1",
        "partition": partition,
        "seed": seed,
        "max_radius": max_radius,
        "node_feature_names": NODE_FEATURE_NAMES,
        "edge_feature_names": EDGE_FEATURE_NAMES,
        "graph_feature_names": GRAPH_FEATURE_NAMES,
        "graph_features": graph_feature_dict,
        "graph_feature_vector": vectorize(GRAPH_FEATURE_NAMES, graph_feature_dict),
        "nodes": out_nodes,
        "edges": out_edges,
    }


def write_json(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
        fp.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GNN-ready feature-fusion graph.")
    parser.add_argument("graph_json", help="input normalized dataflow graph JSON")
    parser.add_argument("--out", required=True, help="output feature-fusion JSON")
    parser.add_argument(
        "--partition",
        choices=("topological", "mincut", "random", "hmetis"),
        default="topological",
        help="partition strategy used for global and partition-context features",
    )
    parser.add_argument("--seed", type=int, default=0, help="seed for random partitioning")
    parser.add_argument("--max-radius", type=int, default=3, help="maximum ego-subgraph radius for local features")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_feature_graph(
        args.graph_json,
        partition=args.partition,
        seed=args.seed,
        max_radius=args.max_radius,
    )
    write_json(args.out, payload)
    print(
        f"wrote {args.out}: "
        f"{len(payload['nodes'])} nodes, "
        f"{len(payload['edges'])} edges, "
        f"{len(payload['node_feature_names'])} node features"
    )


if __name__ == "__main__":
    main()
