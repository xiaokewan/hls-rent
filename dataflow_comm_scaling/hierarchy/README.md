# Hierarchical Rent Features

This folder exports multi-level communication-scaling features.

The motivation is that early routability prediction should not depend on one
arbitrary partition tree. A kernel may look easy at a coarse level and hard at
an inner loop/body level, or the reverse. We therefore keep several views:

```text
source / CDFG / DFG level:
  recursive topological partitions
  recursive min-cut-like partitions
  multiple stop sizes, for example 1, 4, 16 nodes

physical labels:
  Vivado/VPR labels are attached later and used only as targets.
```

## Build Multi-Level Features

```bash
python3 dataflow_comm_scaling/hierarchy/multilevel_rent_features.py \
  dataflow_comm_scaling/real_examples/hlsyn/aes.json \
  --partitions topological \
  --min-nodes 1,4,16 \
  --out dataflow_comm_scaling/hierarchy_out/aes.multilevel.json
```

Use `--partitions topological,mincut` only for small graphs for now. The
current `mincut` is a local Python heuristic and should be replaced with
hMetis/Metis before large benchmark sweeps.

The output contains:

```text
graph_features:
  global alpha/k/aggregate features for each partition and stop size

nodes[].features:
  per-node path alpha/max/mean features over the regions containing that node

analyses[].depth_summary:
  coarse-to-fine region pressure by hierarchy level
```

This lets us test the paper question directly:

```text
At what earliest representation level do dataflow Rent features become
predictive of future routing congestion?
```
