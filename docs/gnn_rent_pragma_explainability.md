# Rent-Aware GNN And Pragma Attribution

This note clarifies what the current GNN path produces, what the expected research output should be, and how Rent-like exponents can be made explainable at the C/kernel/pragma level.

## What Is After The GNN

The GNN should not only output one scalar called "congestion". The useful output is a set of routability-risk predictions at multiple levels:

```text
graph/kernel level:
  predicted routability score
  predicted routing congestion score
  predicted timing/routing slack risk

region/subgraph level:
  high-risk dataflow regions
  region-level alpha_plain / alpha_bit / alpha_bw / alpha_mem / alpha_tensor
  dominant communication type causing the risk

source/pragma level:
  ranked C source lines, loops, arrays, and pragmas that explain the risk
```

So the target is:

```text
CDFG/DFG + pragma metadata + Rent features
    -> GNN
    -> future routability prediction
    -> explanation: which region and which pragma likely caused it
```

The current implementation is the first part of this pipeline:

```text
normalized dataflow graph
    -> local/partition/hierarchical Rent features
    -> PyG-ready graph
    -> optional backend label attachment
```

It is not yet a complete explainable model. It is a feature and label pipeline that lets us run the first ablations.

## What We Should Expect Scientifically

The research expectation should be phrased as an ablation:

```text
raw CDFG/GNN features
raw + edge width/rate features
raw + edge width/rate + Rent scaling features
raw + edge width/rate + hierarchical Rent features
raw + edge width/rate + hierarchical Rent + pragma/source provenance
```

The claim is valid only if the Rent-aware versions improve early prediction of post-route labels such as:

```text
routed / unrouted
global congestion level
overused routing resources
routed net fraction
route channel width, for VPR
WNS/TNS or route-induced timing failure
```

The strongest paper result would be:

```text
At the same early HLS/DFG stage, Rent-aware communication scaling features
improve routability prediction and produce explanations that point back to
specific loops, arrays, and pragmas.
```

## How Rent Exponents Map Back To Pragmas

A Rent exponent is not directly a pragma. It becomes explainable only through provenance.

Every DFG/CDFG node and edge needs metadata like:

```text
function
source_file
line / column
loop_id
basic_block
array or variable name
pragma_ids
producer line
consumer line
```

Then each recursive partition region has:

```text
region nodes
region crossing edges
region alpha/k values
region dominant edges by bit traffic or bandwidth
```

Attribution is then:

```text
high-risk prediction
  -> important GNN nodes/edges or high-risk Rent regions
  -> crossing edges with high C_bit / C_bw / C_mem
  -> source lines and pragma_ids attached to those nodes/edges
  -> ranked pragma/loop/array causes
```

Example interpretation:

```text
alpha_plain high:
  many distinct boundary dependencies; could come from aggressive unroll,
  function inlining, or cross-loop dependence exposure.

alpha_bit or alpha_bw high:
  not just many edges, but wide/frequent traffic crossing region boundaries;
  likely linked to wide streams, vectorized datapaths, unroll factors, or
  array partition creating many parallel lanes.

alpha_mem high:
  communication pressure is memory/access dominated; likely linked to
  ARRAY_PARTITION, reshape, banking, load/store fanout, or stencil accesses.

alpha_tensor high:
  tensor/activation/weight movement scales faster than compute; useful for
  AI kernels, systolic-style data movement, attention, and HBM traffic.
```

## Why A Single Global Alpha Is Not Enough

For pragma attribution, one global exponent is too coarse. We need hierarchical and local features:

```text
global alpha:
  kernel-level communication scaling signature

partition-path alpha:
  which hierarchy levels become communication-heavy

node-local alpha:
  each operation inherits the Rent statistics of regions that contain it

edge-local traffic:
  which producer-consumer dependencies dominate crossing bandwidth
```

This is why the implementation has both:

```text
dataflow_comm_scaling.py
hierarchy/multilevel_rent_features.py
gnn_feature_fusion.py
```

The paper should emphasize that the exponent becomes explainable through the partition tree plus source/pragma provenance, not by the scalar alpha alone.

## Concrete Next Implementation Step

The next missing piece is a `pragma_attribution.py` pass:

```text
input:
  labeled GNN JSON
  hierarchical Rent JSON
  optional GNN explanation scores

output:
  ranked table:
    pragma_id
    source line
    loop/function
    associated region ids
    alpha contribution
    bit/bandwidth crossing contribution
    predicted congestion contribution
```

Before a trained GNN explainer exists, we can implement a deterministic baseline:

```text
score(pragma) =
  sum over regions touched by pragma:
    region_risk * normalized(alpha_bw, k_bw, C_bw, C_mem)
```

After the GNN is trained, replace or combine `region_risk` with:

```text
GNNExplainer / Integrated Gradients / edge mask importance
```

That gives a clear path from early CDFG communication scaling to a C-level design action.
