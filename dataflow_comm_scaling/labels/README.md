# Routability Labels

This folder contains the label side of the early routability-prediction flow.

The feature side answers:

```text
What does the source/DFG/dataflow communication scaling look like?
```

The label side answers:

```text
What happened after physical implementation?
```

## Label Schema

`extract_routability_labels.py` writes:

```json
{
  "format": "dataflow_routability_label_v1",
  "design": "kernel_or_design_id",
  "tool": "vpr",
  "source_reports": ["/abs/path/to/vpr.log"],
  "labels": {
    "routed": 1.0,
    "route_channel_width": 120.0,
    "route_time_sec": 15.3,
    "congestion_score": 1.87
  }
}
```

The most useful labels will differ by backend:

```text
VPR:
  routed
  route_channel_width
  routing_area_total_wirelength
  overused_nodes
  max_overuse
  route_time_sec
  congestion_score

Vivado:
  routed
  nets_with_congestion
  nets_with_routing_errors
  global_congestion_level
  route_time_sec
  wns_ns
  tns_ns
  lut_utilization
  congestion_score
```

`congestion_score` is only a fallback scalar built from whatever the report
contains. For a paper-quality target, prefer a direct backend quantity such as
VPR minimum routable channel width or a Vivado congestion metric extracted from
`report_design_analysis -congestion`.

## Parse Reports

VPR:

```bash
python3 dataflow_comm_scaling/labels/extract_routability_labels.py \
  --tool vpr \
  --design aes \
  --reports runs/vpr/aes/vpr.log \
  --out dataflow_comm_scaling/labels_out/aes.vpr.labels.json
```

Vivado:

```bash
python3 dataflow_comm_scaling/labels/extract_routability_labels.py \
  --tool vivado \
  --design aes \
  --reports runs/vivado/aes/route.log runs/vivado/aes/congestion.rpt runs/vivado/aes/timing.rpt \
  --out dataflow_comm_scaling/labels_out/aes.vivado.labels.json
```

## Attach Labels To GNN Features

```bash
python3 dataflow_comm_scaling/labels/attach_labels.py \
  --features dataflow_comm_scaling/gnn_out/aes.hlsyn.topological.gnn.json \
  --labels dataflow_comm_scaling/labels_out/aes.vpr.labels.json \
  --out dataflow_comm_scaling/labeled_gnn_out/aes.vpr.gnn.json
```

Then train with a physical target:

```bash
conda run -n dataflow-gnn python dataflow_comm_scaling/gnn/train_pyg_regression.py \
  dataflow_comm_scaling/labeled_gnn_out \
  --target route_channel_width \
  --feature-group rent \
  --no-log-target
```
