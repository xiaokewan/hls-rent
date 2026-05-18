# Dataflow Communication Scaling

This folder is a standalone development area for the dataflow communication scaling project.

The goal is not to apply classical Rent's rule directly to DFGs. The goal is to generalize Rentian analysis into a communication scaling framework for directed, weighted, streaming, temporal, and semantic dataflow systems.

## What The Alpha Values Mean

Each `alpha_*` is a scaling exponent. It answers:

```text
When a computational region gets larger, how fast does one type of boundary
communication demand grow?
```

Classical Rent uses:

```text
T = k * B^p
```

This project generalizes that into:

```text
C_x = k_x * B^alpha_x
```

where:

- `B` is compute size, currently `B_node = number of nodes`.
- `C_x` is a communication observable.
- `alpha_x` is the log-log slope of `C_x` versus `B`.

Current exponents:

```text
alpha_plain   crossing edge count scaling
alpha_bit     crossing bit count scaling
alpha_bw      crossing bandwidth scaling
alpha_mem     memory/address/load/store communication scaling
alpha_tensor  tensor/activation/weight communication scaling
alpha_ctrl    control/predicate communication scaling
alpha_reduce  reduction/broadcast/all-to-all communication scaling
```

Intuition:

- Higher `alpha_*`: communication grows faster as compute regions grow.
- Higher `k_*`: the whole curve starts higher even if the slope is similar.
- `alpha_plain` is the classical baseline.
- `alpha_bit` is the first dataflow-aware extension.
- `alpha_bw` is the real target when rates are available.

Example:

```text
scalar chain:        alpha_plain may look similar to wide stream
wide stream:         alpha_bit and alpha_bw become much larger in magnitude
broadcast/all-to-all: semantic exponents expose communication patterns plain Rent hides
```

## Files

```text
dataflow_comm_scaling.py   main analysis script
gnn_feature_fusion.py      builds GNN-ready feature-fusion graphs
gnn/                       PyG wrapper and toy ablation scripts
hierarchy/                 multilevel Rent feature export
labels/                    Vivado/VPR routability label extraction
examples/                  synthetic normalized dataflow graphs
out/                       generated outputs, ignored by convention
gnn_out/                   generated GNN feature graphs, ignored by convention
labels_out/                generated physical labels, ignored by convention
labeled_gnn_out/           generated labeled GNN graphs, ignored by convention
```

## Input Schema

Minimum:

```json
{
  "nodes": [
    {"id": "n0"}
  ],
  "edges": [
    {"src": "n0", "dst": "n1", "width": 32}
  ]
}
```

Preferred:

```json
{
  "nodes": [
    {"id": "mul_0", "op": "mul", "kind": "compute", "area": 3}
  ],
  "edges": [
    {
      "src": "mul_0",
      "dst": "add_0",
      "width": 32,
      "rate": 1.0,
      "kind": "data",
      "semantic": "tensor",
      "fanout": 1,
      "fifo_depth": 0
    }
  ]
}
```

## Run

Analyze one example:

```bash
python3 dataflow_comm_scaling/dataflow_comm_scaling.py \
  dataflow_comm_scaling/examples/wide_stream_pipeline.json \
  --json-out dataflow_comm_scaling/out/wide_stream_pipeline.summary.json \
  --csv-out dataflow_comm_scaling/out/wide_stream_pipeline.regions.csv
```

Analyze all bundled examples:

```bash
for f in dataflow_comm_scaling/examples/*.json; do
  name=$(basename "$f" .json)
  python3 dataflow_comm_scaling/dataflow_comm_scaling.py "$f" \
    --json-out "dataflow_comm_scaling/out/${name}.summary.json" \
    --csv-out "dataflow_comm_scaling/out/${name}.regions.csv"
done
```

## Partition Strategies

The script currently supports three recursive bisection strategies:

```text
topological   split each region in dataflow/topological order
mincut        greedy balanced split that reduces internal cut bandwidth
random        balanced random split, controlled by --seed
```

Run with a selected strategy:

```bash
python3 dataflow_comm_scaling/dataflow_comm_scaling.py \
  dataflow_comm_scaling/examples/memory_stencil.json \
  --partition topological

python3 dataflow_comm_scaling/dataflow_comm_scaling.py \
  dataflow_comm_scaling/examples/memory_stencil.json \
  --partition mincut

python3 dataflow_comm_scaling/dataflow_comm_scaling.py \
  dataflow_comm_scaling/examples/memory_stencil.json \
  --partition random \
  --seed 7
```

Interpretation:

- `topological` asks how communication scales when the design is cut along the producer-to-consumer dataflow direction.
- `mincut` asks how much communication remains even when locality is optimized by a graph partitioner.
- `random` is a baseline for whether the metric is only an artifact of balanced splitting.

The current `mincut` implementation is a lightweight greedy heuristic, not hMetis. It is useful for early experiments but should be replaced or complemented by hMetis/Metis for serious large-graph evaluation.

## Example Graphs

The bundled JSON files are not complete real HLS DFG benchmarks. They are synthetic **communication motifs** designed to test whether the metric reacts correctly to important dataflow patterns:

```text
scalar_chain              narrow scalar dependency path
wide_stream_pipeline      same topology as scalar_chain, but 512-bit tensor streams
broadcast_fanout          one producer feeding many consumers
reduction_tree            tree-shaped reduction traffic
memory_stencil            memory-dominated stencil-like local communication
attention_all_to_all      dense attention-like all-to-all communication
```

They are representative of communication patterns, not representative of full kernels.

Why this matters:

```text
scalar_chain and wide_stream_pipeline can have the same T_plain structure,
but very different C_bit and C_bw demand.
```

That is the first conceptual test: classical edge-count Rent can hide dataflow communication difficulty.

## GNN Feature-Level Fusion

The first GNN integration path is feature-level fusion:

```text
initial GNN node embedding =
  normal IR/node features
+ local dataflow communication scaling features
+ partition-context communication features
```

Build one GNN-ready JSON:

```bash
python3 dataflow_comm_scaling/gnn_feature_fusion.py \
  dataflow_comm_scaling/examples/wide_stream_pipeline.json \
  --out dataflow_comm_scaling/gnn_out/wide_stream_pipeline.gnn.json \
  --partition topological \
  --max-radius 3
```

Build all examples:

```bash
for f in dataflow_comm_scaling/examples/*.json; do
  name=$(basename "$f" .json)
  python3 dataflow_comm_scaling/gnn_feature_fusion.py "$f" \
    --out "dataflow_comm_scaling/gnn_out/${name}.gnn.json" \
    --partition topological \
    --max-radius 3
done
```

## Hierarchical Features

The routability study should test communication pressure at multiple
representations and partition granularities, not only one global alpha.

Build hierarchical Rent features:

```bash
python3 dataflow_comm_scaling/hierarchy/multilevel_rent_features.py \
  dataflow_comm_scaling/real_examples/hlsyn/aes.json \
  --partitions topological \
  --min-nodes 1,4,16 \
  --out dataflow_comm_scaling/hierarchy_out/aes.multilevel.json
```

The output records graph-level and node-level features for several recursive
partition trees. This is the bridge to a hierarchical GNN or an ablation that
asks how early each level becomes predictive.

For large real CDFGs, start with `topological`. The current `mincut` is a
simple Python heuristic and is intended for small graphs until hMetis/Metis is
connected.

## Physical Routability Labels

Parse VPR labels:

```bash
python3 dataflow_comm_scaling/labels/extract_routability_labels.py \
  --tool vpr \
  --design aes \
  --reports runs/vpr/aes/vpr.log \
  --out dataflow_comm_scaling/labels_out/aes.vpr.labels.json
```

Parse Vivado labels:

```bash
python3 dataflow_comm_scaling/labels/extract_routability_labels.py \
  --tool vivado \
  --design aes \
  --reports runs/vivado/aes/route.log runs/vivado/aes/congestion.rpt \
  --out dataflow_comm_scaling/labels_out/aes.vivado.labels.json
```

Attach labels to GNN features:

```bash
python3 dataflow_comm_scaling/labels/attach_labels.py \
  --features dataflow_comm_scaling/gnn_out/aes.hlsyn.topological.gnn.json \
  --labels dataflow_comm_scaling/labels_out/aes.vpr.labels.json \
  --out dataflow_comm_scaling/labeled_gnn_out/aes.vpr.gnn.json
```

Then train against a real physical target:

```bash
conda run -n dataflow-gnn python dataflow_comm_scaling/gnn/train_pyg_regression.py \
  dataflow_comm_scaling/labeled_gnn_out \
  --target route_channel_width \
  --feature-group rent \
  --no-log-target
```

The output contains:

```text
node_feature_names
edge_feature_names
graph_feature_names
nodes[].x
edges[].edge_attr
graph_feature_vector
nodes[].provenance
edges[].provenance
```

Per-node fused features include:

```text
base IR features:        op group, kind, area, in/out degree
local traffic features:  in/out bit, in/out bandwidth, semantic traffic
local scaling features:  ego_alpha_plain, ego_alpha_bit, ego_alpha_bw, ...
partition context:       region_mean_C_bw, region_max_C_bw, region memory pressure
```

This is the first concrete version of:

```text
Rentian/dataflow communication scaling features as GNN physical priors.
```

For future source-level root-cause analysis, the builder preserves optional provenance fields when the extractor provides them:

```text
source_file
line
column
function
loop_id
basic_block
pragma_ids
producer_line
consumer_line
```

This is the bridge from a GNN-important node/subgraph back to a C loop, array, or pragma.

## Roadmap

Later versions can add:

- hMetis partitioning.
- MLIR/Dynamatic Handshake extraction.
- XLS IR extraction.
- schedule-aware and binding-aware communication graphs.
