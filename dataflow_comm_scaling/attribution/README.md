# Pragma Attribution

This folder contains the deterministic baseline for mapping Rent-aware
communication pressure back to source-level design objects.

The intended path is:

```text
DFG/CDFG + source/pragma provenance
  -> GNN feature graph
  -> optional hierarchical Rent features
  -> optional backend labels or GNN explainer scores
  -> ranked pragma/source attribution table
```

## Run

Build the feature inputs first:

```bash
python3 dataflow_comm_scaling/gnn_feature_fusion.py \
  dataflow_comm_scaling/examples/pragma_parallel_memory.json \
  --out dataflow_comm_scaling/gnn_out/pragma_parallel_memory.gnn.json \
  --partition topological

python3 dataflow_comm_scaling/hierarchy/multilevel_rent_features.py \
  dataflow_comm_scaling/examples/pragma_parallel_memory.json \
  --out dataflow_comm_scaling/hierarchy_out/pragma_parallel_memory.multilevel.json \
  --partitions topological \
  --min-nodes 1,4
```

Then run attribution:

```bash
python3 dataflow_comm_scaling/attribution/pragma_attribution.py \
  --features dataflow_comm_scaling/gnn_out/pragma_parallel_memory.gnn.json \
  --hierarchy dataflow_comm_scaling/hierarchy_out/pragma_parallel_memory.multilevel.json \
  --graph-json dataflow_comm_scaling/examples/pragma_parallel_memory.json \
  --out dataflow_comm_scaling/attribution_out/pragma_parallel_memory.attribution.json \
  --csv-out dataflow_comm_scaling/attribution_out/pragma_parallel_memory.attribution.csv
```

`--graph-json` is optional, but useful. It lets the script reconstruct recursive
partition regions with node membership, which is needed for direct
region-to-pragma attribution.

## Interpretation

The output rows are ranked by a deterministic pressure score with these
components:

```text
bit_bw       wide/high-rate boundary traffic
memory       load/store/address/banking communication
tensor       tensor/activation/weight movement
plain        classical edge-count/topological pressure
reduce       broadcast/reduction/fanout/all-to-all pressure
control      control/predicate pressure
hierarchy    high-pressure recursive partition path
gnn_explain  optional external GNN explanation importance
```

If `pragma_ids` are present in node or edge provenance, the primary rows are
`entity_type=pragma`. If they are not present, the script falls back to source
line, loop, function, or node-level attribution. This means the current
Dynamatic/HLSyn graphs can still be inspected before the extractor learns
full C pragma provenance.

## Research Use

This baseline is not the final explainable GNN. It is the control experiment:

```text
Can handcrafted Rent/dataflow pressure alone rank plausible HLS causes?
```

After GNN training, pass an explanation JSON with `node_scores` and
`edge_scores`. The same script will blend those scores into the attribution
table, giving:

```text
Rent pressure + learned GNN importance -> pragma-level explanation
```
