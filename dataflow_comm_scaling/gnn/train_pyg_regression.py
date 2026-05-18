#!/usr/bin/env python3
"""Small PyTorch Geometric graph-regression trainer.

This is the first real GNN training entrypoint for feature-level fusion. It is
kept intentionally small so the experiment can be replaced by stronger models
later without changing the data format.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
from typing import Any, Dict, List, Sequence, Set, Tuple


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


def require_pyg():
    try:
        import torch
        import torch.nn.functional as F
        from torch import nn
        from torch_geometric.data import Data
        from torch_geometric.loader import DataLoader
        from torch_geometric.nn import SAGEConv, global_mean_pool
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "train_pyg_regression.py requires torch and torch_geometric. "
            "Install dependencies from dataflow_comm_scaling/gnn/requirements-gnn.txt first."
        ) from exc
    return torch, F, nn, Data, DataLoader, SAGEConv, global_mean_pool


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


def discover(path: str) -> List[str]:
    if os.path.isdir(path):
        return sorted(glob.glob(os.path.join(path, "*.gnn.json")))
    return [path]


def node_feature_indices(names: Sequence[str], group: str) -> List[int]:
    indices = []
    for index, name in enumerate(names):
        if name in RAW_NODE_FEATURES:
            indices.append(index)
        elif group in {"edge", "rent"} and name in TRAFFIC_NODE_FEATURES:
            indices.append(index)
        elif group == "rent" and name.startswith(RENT_NODE_PREFIXES):
            indices.append(index)
    return indices


def graph_feature_indices(names: Sequence[str], group: str, target: str) -> List[int]:
    if group != "rent":
        return []
    indices = []
    for index, name in enumerate(names):
        if name == target or name.startswith("global_k_"):
            continue
        if name in RENT_GRAPH_FEATURES:
            indices.append(index)
    return indices


def target_value(payload: Dict[str, Any], target: str, log_target: bool) -> float:
    if target in payload.get("graph_features", {}):
        value = safe_number(payload["graph_features"][target])
    elif target in payload.get("labels", {}):
        value = safe_number(payload["labels"][target])
    else:
        raise KeyError(f"target {target!r} not found in graph_features or labels for {payload.get('source')}")
    return math.log2(max(value, 1e-9)) if log_target else value


def payload_to_data(payload: Dict[str, Any], group: str, target: str, log_target: bool):
    torch, _, _, Data, _, _, _ = require_pyg()
    x_indices = node_feature_indices(payload["node_feature_names"], group)
    graph_indices = graph_feature_indices(payload["graph_feature_names"], group, target)

    x = torch.tensor([[node["x"][idx] for idx in x_indices] for node in payload["nodes"]], dtype=torch.float32)
    edge_pairs = [[edge["src_index"], edge["dst_index"]] for edge in payload["edges"]]
    edge_index = torch.tensor(edge_pairs, dtype=torch.long).t().contiguous()
    graph_x = torch.tensor(
        [payload["graph_feature_vector"][idx] for idx in graph_indices],
        dtype=torch.float32,
    ).view(1, -1)
    y = torch.tensor([target_value(payload, target, log_target)], dtype=torch.float32)

    data = Data(x=x, edge_index=edge_index, y=y)
    data.graph_x = graph_x
    data.name = payload["name"]
    return data


def make_model(input_dim: int, graph_dim: int, hidden_dim: int):
    torch, F, nn, _, _, SAGEConv, global_mean_pool = require_pyg()

    class GraphRegressor(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv1 = SAGEConv(input_dim, hidden_dim)
            self.conv2 = SAGEConv(hidden_dim, hidden_dim)
            self.head = nn.Sequential(
                nn.Linear(hidden_dim + graph_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, 1),
            )

        def forward(self, data):
            x = F.relu(self.conv1(data.x, data.edge_index))
            x = F.relu(self.conv2(x, data.edge_index))
            pooled = global_mean_pool(x, data.batch)
            graph_x = data.graph_x
            if graph_x.numel() == 0:
                graph_x = graph_x.new_zeros((pooled.size(0), 0))
            elif graph_x.size(0) != pooled.size(0):
                graph_x = graph_x.view(pooled.size(0), -1)
            return self.head(torch.cat([pooled, graph_x], dim=1)).view(-1)

    return GraphRegressor()


def split_dataset(data_list: List[Any], test_fraction: float, seed: int) -> Tuple[List[Any], List[Any]]:
    shuffled = list(data_list)
    rng = random.Random(seed)
    rng.shuffle(shuffled)
    n_test = max(1, int(round(len(shuffled) * test_fraction)))
    return shuffled[n_test:], shuffled[:n_test]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a small PyG graph regressor on feature-fusion JSON files.")
    parser.add_argument("path", help="feature JSON file or directory containing *.gnn.json")
    parser.add_argument("--target", default="global_k_bw", help="graph feature to predict")
    parser.add_argument("--feature-group", choices=("raw", "edge", "rent"), default="rent")
    parser.add_argument("--no-log-target", action="store_true", help="do not log2-transform the target")
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--test-fraction", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    torch, F, _, _, DataLoader, _, _ = require_pyg()
    torch.manual_seed(args.seed)

    payloads = [load_payload(path) for path in discover(args.path)]
    data_list = [
        payload_to_data(payload, args.feature_group, args.target, not args.no_log_target)
        for payload in payloads
    ]
    if len(data_list) < 3:
        raise SystemExit("need at least three graphs for train/test split")

    train_data, test_data = split_dataset(data_list, args.test_fraction, args.seed)
    train_loader = DataLoader(train_data, batch_size=args.batch_size, shuffle=True)
    test_loader = DataLoader(test_data, batch_size=args.batch_size, shuffle=False)

    input_dim = data_list[0].x.size(1)
    graph_dim = data_list[0].graph_x.size(1)
    model = make_model(input_dim, graph_dim, args.hidden_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        for batch in train_loader:
            optimizer.zero_grad()
            pred = model(batch)
            loss = F.mse_loss(pred, batch.y.view(-1))
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * batch.num_graphs
        if epoch == 1 or epoch % 25 == 0 or epoch == args.epochs:
            print(f"epoch={epoch:04d} train_mse={total_loss / len(train_data):.6f}")

    model.eval()
    preds = []
    labels = []
    with torch.no_grad():
        for batch in test_loader:
            pred = model(batch)
            preds.extend(pred.cpu().tolist())
            labels.extend(batch.y.view(-1).cpu().tolist())

    errors = [abs(p - y) for p, y in zip(preds, labels)]
    rmse = math.sqrt(sum((p - y) ** 2 for p, y in zip(preds, labels)) / len(labels))
    print(f"test_graphs={len(labels)} MAE={sum(errors) / len(errors):.6f} RMSE={rmse:.6f}")


if __name__ == "__main__":
    main()
