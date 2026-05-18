# GNN Integration

This folder contains the first concrete path for integrating dataflow communication scaling features into graph learning models.

The current focus is **feature-level fusion**:

```text
GNN node embedding =
  normal IR features
+ local traffic features
+ local dataflow/Rentian scaling features
+ partition-context features
```

## Files

```text
pyg_dataset.py    Optional PyTorch Geometric conversion wrapper.
train_pyg_regression.py  Small PyG graph-regression trainer.
toy_ablation.py   Lightweight sklearn ablation over generated *.gnn.json files.
```

## Current Dependency Status

The local conda environment created for this project is:

```text
dataflow-gnn
```

It currently uses CPU PyTorch, which is sufficient for the small graphs in the first experiments.

Recreate it with:

```bash
conda create -n dataflow-gnn python=3.11 -y
conda run -n dataflow-gnn python -m pip install --upgrade pip
conda run -n dataflow-gnn python -m pip install \
  --index-url https://download.pytorch.org/whl/cpu \
  torch torchvision torchaudio
conda run -n dataflow-gnn python -m pip install \
  torch_geometric numpy scikit-learn pandas matplotlib networkx tqdm
```

## Build Feature Graphs

Generate feature-fusion graphs for all examples and partition strategies:

```bash
for p in topological mincut random; do
  for f in dataflow_comm_scaling/examples/*.json; do
    name=$(basename "$f" .json)
    python3 dataflow_comm_scaling/gnn_feature_fusion.py "$f" \
      --out "dataflow_comm_scaling/gnn_out/${name}.${p}.gnn.json" \
      --partition "$p" \
      --seed 7 \
      --max-radius 3
  done
done
```

## Toy Ablation

Run a regression ablation on generated feature graphs:

```bash
python3 dataflow_comm_scaling/gnn/toy_ablation.py \
  dataflow_comm_scaling/gnn_out \
  --pattern "*.*.gnn.json" \
  --target global_k_bw
```

Feature groups:

```text
raw   node op/kind/area/degree only
edge  raw + width/rate/traffic/semantic edge aggregates
rent  edge + local ego scaling + partition-context + global scaling features
```

This is not a final GNN experiment. It is a smoke test for the paper hypothesis:

```text
Dataflow/Rentian communication features should add signal beyond raw graph
topology and operation types.
```

## PyG Conversion

Once PyTorch and PyG are installed:

```bash
python3 dataflow_comm_scaling/gnn/pyg_dataset.py \
  dataflow_comm_scaling/gnn_out \
  --target global_k_bw
```

The wrapper converts each `*.gnn.json` into a `torch_geometric.data.Data` object with:

```text
data.x
data.edge_index
data.edge_attr
data.graph_x
data.y
```

Run the first PyG regression model:

```bash
python3 dataflow_comm_scaling/gnn/train_pyg_regression.py \
  dataflow_comm_scaling/gnn_out \
  --target global_k_bw \
  --feature-group rent
```

Compare ablations:

```bash
for g in raw edge rent; do
  python3 dataflow_comm_scaling/gnn/train_pyg_regression.py \
    dataflow_comm_scaling/gnn_out \
    --target global_k_bw \
    --feature-group "$g"
done
```
