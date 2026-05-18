#!/usr/bin/env python3
"""Dataflow communication scaling analysis.

This is a dependency-free prototype for the normalized JSON dataflow schema in
this folder. It recursively partitions a graph into computational regions and
fits log-log scaling exponents for several boundary communication observables.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import shutil
import subprocess
import tempfile
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple


MEMORY_TAGS = {"memory", "mem", "load", "store", "address", "dram", "hbm", "bram", "uram"}
TENSOR_TAGS = {"tensor", "activation", "weight", "feature", "matrix", "vector"}
CONTROL_TAGS = {"control", "ctrl", "predicate", "pred", "token", "enable"}
REDUCE_TAGS = {"reduce", "reduction", "broadcast", "fanout", "all_to_all", "all-to-all", "attention"}


@dataclass(frozen=True)
class Node:
    id: str
    op: str = "unknown"
    kind: str = "compute"
    area: float = 1.0
    text: str = ""
    full_text: str = ""
    basic_block: str = ""
    function: str = ""


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    width: float = 1.0
    rate: float = 1.0
    kind: str = "data"
    semantic: str = "scalar"
    fanout: float = 1.0
    fifo_depth: float = 0.0

    @property
    def bit_demand(self) -> float:
        return self.width

    @property
    def bw_demand(self) -> float:
        return self.width * self.rate

    @property
    def buffer_demand(self) -> float:
        return self.width * self.fifo_depth

    def has_any_tag(self, tags: Set[str]) -> bool:
        values = {self.kind.lower(), self.semantic.lower()}
        return bool(values & tags)


@dataclass(frozen=True)
class Region:
    id: str
    level: int
    nodes: Tuple[str, ...]


def _as_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_optional_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def load_graph(path: str) -> Tuple[List[Node], List[Edge], Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as fp:
        payload = json.load(fp)

    raw_nodes = payload.get("nodes", [])
    raw_edges = payload.get("edges", [])
    if not raw_nodes:
        raise ValueError("input graph must contain at least one node")

    nodes = [
        Node(
            id=str(item["id"]),
            op=str(item.get("op", "unknown")),
            kind=str(item.get("kind", "compute")),
            area=_as_float(item.get("area"), 1.0),
            text=_as_optional_str(item.get("text", item.get("label", item.get("op", "unknown")))),
            full_text=_as_optional_str(
                item.get("full_text", item.get("text", item.get("label", item.get("op", "unknown"))))
            ),
            basic_block=_as_optional_str(item.get("basic_block", item.get("programl_block"))),
            function=_as_optional_str(item.get("function", item.get("programl_function"))),
        )
        for item in raw_nodes
    ]
    node_ids = {node.id for node in nodes}
    if len(node_ids) != len(nodes):
        raise ValueError("node ids must be unique")

    edges = [
        Edge(
            src=str(item["src"]),
            dst=str(item["dst"]),
            width=max(_as_float(item.get("width"), 1.0), 0.0),
            rate=max(_as_float(item.get("rate"), 1.0), 0.0),
            kind=str(item.get("kind", "data")),
            semantic=str(item.get("semantic", "scalar")),
            fanout=max(_as_float(item.get("fanout"), 1.0), 1.0),
            fifo_depth=max(_as_float(item.get("fifo_depth"), 0.0), 0.0),
        )
        for item in raw_edges
    ]

    unknown_endpoints = sorted(
        {endpoint for edge in edges for endpoint in (edge.src, edge.dst) if endpoint not in node_ids}
    )
    if unknown_endpoints:
        raise ValueError(f"edges reference unknown nodes: {unknown_endpoints}")

    meta = {
        "name": payload.get("name", os.path.splitext(os.path.basename(path))[0]),
        "description": payload.get("description", ""),
        "source": path,
    }
    return nodes, edges, meta


def topological_order(nodes: Sequence[Node], edges: Sequence[Edge]) -> List[str]:
    node_ids = [node.id for node in nodes]
    indegree = {node_id: 0 for node_id in node_ids}
    outgoing: Dict[str, List[str]] = defaultdict(list)
    for edge in edges:
        outgoing[edge.src].append(edge.dst)
        indegree[edge.dst] += 1

    queue = deque([node_id for node_id in node_ids if indegree[node_id] == 0])
    order: List[str] = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for dst in outgoing[node_id]:
            indegree[dst] -= 1
            if indegree[dst] == 0:
                queue.append(dst)

    if len(order) != len(node_ids):
        # Dataflow systems may contain cycles. Keep deterministic input order.
        return node_ids
    return order


def _cut_weight(left: Set[str], right: Set[str], edges: Sequence[Edge]) -> float:
    return sum(edge.bw_demand for edge in edges if (edge.src in left and edge.dst in right) or (edge.src in right and edge.dst in left))


def _stable_region_seed(seed: int, region_id: str) -> int:
    return seed + sum((index + 1) * ord(char) for index, char in enumerate(region_id))


def split_topological(region_nodes: Sequence[str]) -> Tuple[List[str], List[str]]:
    split = len(region_nodes) // 2
    return list(region_nodes[:split]), list(region_nodes[split:])


def split_random(region_nodes: Sequence[str], region_id: str, seed: int) -> Tuple[List[str], List[str]]:
    shuffled = list(region_nodes)
    rng = random.Random(_stable_region_seed(seed, region_id))
    rng.shuffle(shuffled)
    left_set = set(shuffled[: len(shuffled) // 2])
    right_set = set(shuffled[len(shuffled) // 2 :])
    left = [node_id for node_id in region_nodes if node_id in left_set]
    right = [node_id for node_id in region_nodes if node_id in right_set]
    return left, right


def split_mincut(region_nodes: Sequence[str], edges: Sequence[Edge]) -> Tuple[List[str], List[str]]:
    left, right = split_topological(region_nodes)
    left_set = set(left)
    right_set = set(right)
    region_set = set(region_nodes)
    local_edges = [edge for edge in edges if edge.src in region_set and edge.dst in region_set]

    improved = True
    while improved:
        improved = False
        current = _cut_weight(left_set, right_set, local_edges)
        best_delta = 0.0
        best_swap: Tuple[str, str] | None = None

        for left_node in sorted(left_set):
            for right_node in sorted(right_set):
                trial_left = (left_set - {left_node}) | {right_node}
                trial_right = (right_set - {right_node}) | {left_node}
                delta = current - _cut_weight(trial_left, trial_right, local_edges)
                if delta > best_delta:
                    best_delta = delta
                    best_swap = (left_node, right_node)

        if best_swap is not None:
            left_node, right_node = best_swap
            left_set = (left_set - {left_node}) | {right_node}
            right_set = (right_set - {right_node}) | {left_node}
            improved = True

    left = [node_id for node_id in region_nodes if node_id in left_set]
    right = [node_id for node_id in region_nodes if node_id in right_set]
    return left, right


def default_hmetis_path() -> str:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local = os.path.join(repo_root, "hmetis-1.5-linux", "shmetis")
    return local if os.path.exists(local) else "shmetis"


def write_hmetis_hgraph(path: str, region_nodes: Sequence[str], edges: Sequence[Edge]) -> bool:
    local_index = {node_id: index + 1 for index, node_id in enumerate(region_nodes)}
    region_set = set(region_nodes)
    hyperedges = []
    seen = set()
    for edge in edges:
        if edge.src not in region_set or edge.dst not in region_set or edge.src == edge.dst:
            continue
        pins = tuple(sorted((local_index[edge.src], local_index[edge.dst])))
        if pins in seen:
            continue
        seen.add(pins)
        hyperedges.append(pins)

    if not hyperedges:
        return False

    with open(path, "w", encoding="utf-8") as fp:
        fp.write(f"{len(hyperedges)} {len(region_nodes)}\n")
        for pins in hyperedges:
            fp.write(" ".join(str(pin) for pin in pins))
            fp.write("\n")
    return True


def split_hmetis(
    region_nodes: Sequence[str],
    edges: Sequence[Edge],
    region_id: str,
    seed: int,
    hmetis_path: str | None = None,
    ubfactor: int = 5,
) -> Tuple[List[str], List[str]]:
    if len(region_nodes) < 4:
        return split_topological(region_nodes)

    executable = hmetis_path or os.environ.get("HMETIS_SHMETIS") or default_hmetis_path()
    executable = shutil.which(executable) or executable
    if os.path.exists(executable):
        executable = os.path.abspath(executable)
    if not os.path.exists(executable):
        return split_topological(region_nodes)

    with tempfile.TemporaryDirectory(prefix="dfg_rent_hmetis_") as tmpdir:
        hgraph_path = os.path.join(tmpdir, f"{region_id}.hgr")
        if not write_hmetis_hgraph(hgraph_path, region_nodes, edges):
            return split_topological(region_nodes)
        command = [executable, hgraph_path, "2", str(ubfactor)]
        try:
            subprocess.run(
                command,
                cwd=tmpdir,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return split_topological(region_nodes)

        part_path = hgraph_path + ".part.2"
        try:
            with open(part_path, "r", encoding="utf-8") as fp:
                assignments = [int(line.strip()) for line in fp if line.strip()]
        except (OSError, ValueError):
            return split_topological(region_nodes)

    if len(assignments) != len(region_nodes):
        return split_topological(region_nodes)

    left = [node_id for node_id, part in zip(region_nodes, assignments) if part == 0]
    right = [node_id for node_id, part in zip(region_nodes, assignments) if part != 0]
    if not left or not right:
        return split_topological(region_nodes)
    return left, right


def split_region(
    region_nodes: Sequence[str],
    edges: Sequence[Edge],
    region_id: str,
    partition: str,
    seed: int,
    hmetis_path: str | None = None,
    hmetis_ubfactor: int = 5,
) -> Tuple[List[str], List[str]]:
    if partition == "topological":
        return split_topological(region_nodes)
    if partition == "random":
        return split_random(region_nodes, region_id, seed)
    if partition == "mincut":
        return split_mincut(region_nodes, edges)
    if partition == "hmetis":
        return split_hmetis(region_nodes, edges, region_id, seed, hmetis_path, hmetis_ubfactor)
    raise ValueError(f"unknown partition strategy: {partition}")


def build_regions(
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    min_nodes: int = 1,
    partition: str = "topological",
    seed: int = 0,
    hmetis_path: str | None = None,
    hmetis_ubfactor: int = 5,
) -> List[Region]:
    order = topological_order(nodes, edges)
    regions: List[Region] = []

    def recurse(region_nodes: Sequence[str], level: int, region_id: str) -> None:
        regions.append(Region(region_id, level, tuple(region_nodes)))
        if len(region_nodes) <= max(min_nodes, 1):
            return
        left, right = split_region(region_nodes, edges, region_id, partition, seed, hmetis_path, hmetis_ubfactor)
        recurse(left, level + 1, region_id + "0")
        recurse(right, level + 1, region_id + "1")

    recurse(order, 0, "r")
    return regions


def _herfindahl(values: Iterable[float]) -> float:
    values = [value for value in values if value > 0]
    total = sum(values)
    if total <= 0:
        return 0.0
    return sum((value / total) ** 2 for value in values)


def _node_debug_label(node: Node) -> str:
    scope = []
    if node.function:
        scope.append(f"f{node.function}")
    if node.basic_block:
        scope.append(f"b{node.basic_block}")
    prefix = node.id if not scope else f"{node.id}@{'/'.join(scope)}"
    label = " ".join((node.text or node.op or node.kind or node.id).split())
    return f"{prefix}:{label.replace('|', '/')}"


def _preview_items(items: Sequence[str], limit: int = 32) -> List[str]:
    preview = list(items[:limit])
    if len(items) > limit:
        preview.append(f"...+{len(items) - limit} more")
    return preview


def score_region(region: Region, node_by_id: Dict[str, Node], edges: Sequence[Edge]) -> Dict[str, Any]:
    inside = set(region.nodes)
    crossing = [edge for edge in edges if (edge.src in inside) ^ (edge.dst in inside)]

    in_bw = sum(edge.bw_demand for edge in crossing if edge.dst in inside)
    out_bw = sum(edge.bw_demand for edge in crossing if edge.src in inside)
    total_bw = in_bw + out_bw

    outgoing_by_src: Dict[str, float] = defaultdict(float)
    incoming_by_dst: Dict[str, float] = defaultdict(float)
    for edge in crossing:
        if edge.src in inside:
            outgoing_by_src[edge.src] += edge.bw_demand
        if edge.dst in inside:
            incoming_by_dst[edge.dst] += edge.bw_demand

    c_bit = sum(edge.bit_demand for edge in crossing)
    c_bw = sum(edge.bw_demand for edge in crossing)
    c_buf = sum(edge.buffer_demand for edge in crossing)
    c_mem = sum(edge.bw_demand for edge in crossing if edge.has_any_tag(MEMORY_TAGS))
    c_tensor = sum(edge.bw_demand for edge in crossing if edge.has_any_tag(TENSOR_TAGS))
    c_ctrl = sum(edge.bw_demand for edge in crossing if edge.has_any_tag(CONTROL_TAGS))
    c_reduce = sum(edge.bw_demand for edge in crossing if edge.has_any_tag(REDUCE_TAGS))
    fanout_weighted_cut = sum(edge.bw_demand * edge.fanout for edge in crossing)

    b_area = sum(node_by_id[node_id].area for node_id in region.nodes)
    function_ids = sorted({node_by_id[node_id].function for node_id in region.nodes if node_by_id[node_id].function})
    block_ids = sorted({node_by_id[node_id].basic_block for node_id in region.nodes if node_by_id[node_id].basic_block})
    node_block_labels = _preview_items([_node_debug_label(node_by_id[node_id]) for node_id in region.nodes])
    return {
        "region_id": region.id,
        "level": region.level,
        "B_node": len(region.nodes),
        "B_area": b_area,
        "T_plain": len(crossing),
        "C_bit": c_bit,
        "C_bw": c_bw,
        "C_buf": c_buf,
        "C_mem": c_mem,
        "C_tensor": c_tensor,
        "C_ctrl": c_ctrl,
        "C_reduce": c_reduce,
        "in_bw": in_bw,
        "out_bw": out_bw,
        "flow_balance": abs(out_bw - in_bw) / total_bw if total_bw > 0 else 0.0,
        "source_skew": _herfindahl(outgoing_by_src.values()),
        "sink_skew": _herfindahl(incoming_by_dst.values()),
        "fanout_weighted_cut": fanout_weighted_cut,
        "memory_fraction": c_mem / c_bw if c_bw > 0 else 0.0,
        "function_ids": function_ids,
        "block_ids": block_ids,
        "node_block_labels": node_block_labels,
        "node_ids": list(region.nodes),
    }


def fit_power_law(rows: Sequence[Dict[str, Any]], x_key: str, y_key: str) -> Dict[str, Any]:
    points = [
        (math.log2(float(row[x_key])), math.log2(float(row[y_key])))
        for row in rows
        if float(row.get(x_key, 0.0)) > 1.0 and float(row.get(y_key, 0.0)) > 0.0
    ]
    if len(points) < 2:
        return {"alpha": None, "k": None, "r2": None, "n_points": len(points)}

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return {"alpha": None, "k": None, "r2": None, "n_points": len(points)}

    alpha = sum((x - mean_x) * (y - mean_y) for x, y in points) / var_x
    intercept = mean_y - alpha * mean_x
    predicted = [intercept + alpha * x for x in xs]
    ss_res = sum((y - y_hat) ** 2 for y, y_hat in zip(ys, predicted))
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {
        "alpha": alpha,
        "k": 2.0**intercept,
        "r2": r2,
        "n_points": len(points),
    }


def summarize(
    rows: Sequence[Dict[str, Any]],
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    meta: Dict[str, Any],
    partition: str,
    seed: int,
) -> Dict[str, Any]:
    fit_map = {
        "alpha_plain": "T_plain",
        "alpha_bit": "C_bit",
        "alpha_bw": "C_bw",
        "alpha_mem": "C_mem",
        "alpha_tensor": "C_tensor",
        "alpha_ctrl": "C_ctrl",
        "alpha_reduce": "C_reduce",
    }
    fits = {alpha_name: fit_power_law(rows, "B_node", metric) for alpha_name, metric in fit_map.items()}

    non_root = [row for row in rows if row["region_id"] != "r"]
    mean_flow_balance = (
        sum(float(row["flow_balance"]) for row in non_root) / len(non_root) if non_root else 0.0
    )
    max_flow_balance = max((float(row["flow_balance"]) for row in non_root), default=0.0)
    total_bw = sum(float(row["C_bw"]) for row in non_root)
    total_mem = sum(float(row["C_mem"]) for row in non_root)
    total_tensor = sum(float(row["C_tensor"]) for row in non_root)
    total_ctrl = sum(float(row["C_ctrl"]) for row in non_root)
    total_reduce = sum(float(row["C_reduce"]) for row in non_root)

    return {
        "name": meta["name"],
        "description": meta["description"],
        "source": meta["source"],
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "n_regions": len(rows),
        "partition": partition,
        "seed": seed,
        "fits": fits,
        "aggregate": {
            "mean_flow_balance": mean_flow_balance,
            "max_flow_balance": max_flow_balance,
            "memory_fraction": total_mem / total_bw if total_bw > 0 else 0.0,
            "tensor_fraction": total_tensor / total_bw if total_bw > 0 else 0.0,
            "control_fraction": total_ctrl / total_bw if total_bw > 0 else 0.0,
            "reduce_fraction": total_reduce / total_bw if total_bw > 0 else 0.0,
        },
    }


def analyze(
    path: str,
    min_nodes: int = 1,
    partition: str = "topological",
    seed: int = 0,
    hmetis_path: str | None = None,
    hmetis_ubfactor: int = 5,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    nodes, edges, meta = load_graph(path)
    node_by_id = {node.id: node for node in nodes}
    regions = build_regions(
        nodes,
        edges,
        min_nodes=min_nodes,
        partition=partition,
        seed=seed,
        hmetis_path=hmetis_path,
        hmetis_ubfactor=hmetis_ubfactor,
    )
    rows = [score_region(region, node_by_id, edges) for region in regions]
    summary = summarize(rows, nodes, edges, meta, partition, seed)
    return summary, rows


def write_json(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
        fp.write("\n")


def write_csv(path: str, rows: Sequence[Dict[str, Any]]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    fieldnames = [
        "region_id",
        "level",
        "B_node",
        "B_area",
        "T_plain",
        "C_bit",
        "C_bw",
        "C_buf",
        "C_mem",
        "C_tensor",
        "C_ctrl",
        "C_reduce",
        "in_bw",
        "out_bw",
        "flow_balance",
        "source_skew",
        "sink_skew",
        "fanout_weighted_cut",
        "memory_fraction",
        "function_ids",
        "block_ids",
        "node_block_labels",
        "node_ids",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            serializable = dict(row)
            serializable["function_ids"] = " ".join(serializable["function_ids"])
            serializable["block_ids"] = " ".join(serializable["block_ids"])
            serializable["node_block_labels"] = " | ".join(serializable["node_block_labels"])
            serializable["node_ids"] = " ".join(serializable["node_ids"])
            writer.writerow(serializable)


def print_compact_summary(summary: Dict[str, Any]) -> None:
    print(f"design: {summary['name']}")
    print(
        f"nodes: {summary['n_nodes']}, edges: {summary['n_edges']}, "
        f"regions: {summary['n_regions']}, partition: {summary['partition']}"
    )
    for key in ("alpha_plain", "alpha_bit", "alpha_bw", "alpha_mem", "alpha_tensor", "alpha_ctrl", "alpha_reduce"):
        fit = summary["fits"][key]
        alpha = fit["alpha"]
        k = fit["k"]
        if alpha is None:
            print(f"{key}: n/a")
        else:
            print(f"{key}: alpha={alpha:.4f}, k={k:.4f}, r2={fit['r2']:.4f}, n={fit['n_points']}")
    aggregate = summary["aggregate"]
    print(
        "aggregate: "
        f"mean_flow_balance={aggregate['mean_flow_balance']:.4f}, "
        f"memory_fraction={aggregate['memory_fraction']:.4f}, "
        f"tensor_fraction={aggregate['tensor_fraction']:.4f}, "
        f"control_fraction={aggregate['control_fraction']:.4f}, "
        f"reduce_fraction={aggregate['reduce_fraction']:.4f}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze dataflow communication scaling for a normalized JSON graph.")
    parser.add_argument("graph_json", help="input normalized dataflow graph JSON")
    parser.add_argument("--json-out", help="write design-level summary JSON")
    parser.add_argument("--csv-out", help="write per-region metrics CSV")
    parser.add_argument("--min-nodes", type=int, default=1, help="minimum nodes per recursive region")
    parser.add_argument(
        "--partition",
        choices=("topological", "mincut", "random", "hmetis"),
        default="topological",
        help="recursive bisection strategy",
    )
    parser.add_argument("--seed", type=int, default=0, help="seed for random partitioning")
    parser.add_argument("--hmetis-path", help="path to hMetis shmetis executable")
    parser.add_argument("--hmetis-ubfactor", type=int, default=5, help="hMetis balance tolerance, e.g. 5 for 45-55")
    parser.add_argument("--quiet", action="store_true", help="suppress compact stdout summary")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary, rows = analyze(
        args.graph_json,
        min_nodes=args.min_nodes,
        partition=args.partition,
        seed=args.seed,
        hmetis_path=args.hmetis_path,
        hmetis_ubfactor=args.hmetis_ubfactor,
    )

    if args.json_out:
        write_json(args.json_out, summary)
    if args.csv_out:
        write_csv(args.csv_out, rows)
    if not args.quiet:
        print_compact_summary(summary)


if __name__ == "__main__":
    main()
