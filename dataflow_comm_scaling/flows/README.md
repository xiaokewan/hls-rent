# Backend Flow Hooks

These files generate the physical-design reports that become routability labels.

## Dynamatic Front-End

Compile a C kernel with Dynamatic and extract the Handshake-level graph:

```bash
bash dataflow_comm_scaling/flows/run_dynamatic_compile_and_extract.sh \
  --source /media/xiaokewan/TOSHIBA/tools/dynamatic/tutorials/Introduction/Ch1/loop_multiply.c \
  --design loop_multiply \
  --out-dir dataflow_comm_scaling/real_examples/dynamatic \
  --dynamatic-root /media/xiaokewan/TOSHIBA/tools/dynamatic
```

If the C kernel contains HLS pragmas, ask the flow to attach pragma provenance
before building Rent/GNN features:

```bash
bash dataflow_comm_scaling/flows/run_dynamatic_compile_and_extract.sh \
  --source kernels/mm.c \
  --design mm \
  --out-dir dataflow_comm_scaling/real_examples/dynamatic \
  --dynamatic-root /media/xiaokewan/TOSHIBA/tools/dynamatic \
  --annotate-pragmas \
  --attach-function-scope
```

Use `--attach-function-scope` only when the Dynamatic output lacks original C
line locations. It is intentionally coarse; exact `source_file`/`line`
provenance is better for root-cause attribution.

This produces:

```text
dataflow_comm_scaling/real_examples/dynamatic/<design>.dynamatic_handshake.json
dataflow_comm_scaling/out/<design>.dynamatic_handshake.summary.json
dataflow_comm_scaling/gnn_out/<design>.dynamatic_handshake.gnn.json
```

## Vivado

After synthesis/place/route, generate reports with:

```bash
/home/xiaokewan/Software/Xilinx/2025.2/Vivado/bin/vivado \
  -mode batch \
  -source dataflow_comm_scaling/flows/vivado_routability_reports.tcl \
  -tclargs runs/vivado/aes
```

Then parse:

```bash
python3 dataflow_comm_scaling/labels/extract_routability_labels.py \
  --tool vivado \
  --design aes \
  --reports runs/vivado/aes/route_status.rpt runs/vivado/aes/congestion.rpt runs/vivado/aes/timing_summary.rpt \
  --out dataflow_comm_scaling/labels_out/aes.vivado.labels.json
```

## VPR

Run VPR and extract labels:

```bash
bash dataflow_comm_scaling/flows/run_vpr_and_extract.sh \
  --design aes \
  --arch /path/to/arch.xml \
  --circuit /path/to/aes.blif \
  --out-dir runs/vpr/aes \
  --vpr /home/xiaokewan/Software/vtr-verilog-to-routing-master/build/vpr/vpr
```

For a stronger label, sweep `--route_chan_width` and use the minimum width that
routes successfully. That target is often cleaner than a single binary
`routed` label.
