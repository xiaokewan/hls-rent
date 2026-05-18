# Early Routability Prediction Plan

The target question is:

```text
How early can we predict future routing congestion from source/DFG/dataflow
communication structure?
```

The working hypothesis is that classical Rent is too late and too weak for
HLS/dataflow systems, but dataflow-aware communication scaling features can act
as physical priors before RTL implementation.

## Levels

Use the same kernel/pragma/design point and extract features at progressively
later levels:

```text
L0 source / pragma:
  loop, array, pragma, function metadata

L1 CDFG / ProGraML:
  operation graph, data/control/call edges, bitwidth heuristics

L2 scheduled or handshake dataflow IR:
  dataflow operators, streams/FIFOs, memory controllers, rates if available

L3 RTL/netlist:
  modules, registers, memories, fanout, hierarchy

L4 placement/pre-route:
  utilization map, rough wirelength, placement density

Label:
  post-route congestion/routability from Vivado or VPR
```

The paper angle is not just "better prediction". It is an ablation over time:

```text
How much predictive signal appears at L1, L2, L3, and L4?
```

## Feature Families

Baseline features:

```text
node/op counts
edge counts
degree/fanout
memory/control/data edge counts
bitwidth totals
pragma settings
```

Dataflow Rent features:

```text
alpha_plain
alpha_bit
alpha_bw
alpha_mem
alpha_tensor
alpha_ctrl
alpha_reduce
k_plain/k_bit/k_bw
flow_balance
source_skew/sink_skew
fanout_weighted_cut
memory_fraction
```

Hierarchical features:

```text
global alpha/k per partition strategy
per-depth region communication summaries
per-node containment-path alpha/max/mean pressure
local ego-subgraph alpha values
```

## Labels

VPR labels:

```text
routed
minimum routable channel width
route time
total wirelength / routing area
overused nodes
max overuse
critical path
```

Vivado labels:

```text
routed
route status
congestion report metrics
number of congested/error nets
route time
WNS/TNS
utilization
```

Prefer continuous labels when possible:

```text
minimum VPR channel width > binary routed/not routed
Vivado congestion severity/count > binary routed/not routed
```

## Ablations

Train the same model with increasing information:

```text
A0 raw CDFG features only
A1 raw + bitwidth/traffic features
A2 raw + traffic + local Rent features
A3 raw + traffic + hierarchical Rent features
A4 later IR/netlist features
A5 placement/pre-route features
```

A good result would show:

```text
Rent/dataflow features improve prediction at L1/L2, before RTL placement exists.
```

An even stronger result would show:

```text
high-alpha regions can be mapped back to a C loop, array, or pragma.
```

## Current Implementation Hooks

```text
dataflow_comm_scaling/dataflow_comm_scaling.py
  computes global and region communication-scaling metrics

dataflow_comm_scaling/gnn_feature_fusion.py
  builds node/edge/graph GNN features with local Rent priors

dataflow_comm_scaling/hierarchy/multilevel_rent_features.py
  exports multi-level containment-path Rent features

dataflow_comm_scaling/labels/extract_routability_labels.py
  parses Vivado/VPR logs into a common label schema

dataflow_comm_scaling/labels/attach_labels.py
  attaches labels to GNN feature JSONs
```

## Near-Term Milestones

1. Build the open HLS/dataflow front-end and extract one real dataflow IR.
2. Run one small design through VPR or Vivado and attach a real label.
3. Generate a design-point matrix over kernels and pragmas.
4. Train raw-vs-Rent ablations using the same physical target.
5. Add source/pragma provenance so important graph regions can be attributed
   back to C-level design choices.
