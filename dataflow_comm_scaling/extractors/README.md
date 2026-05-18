# Real HLS / DFG Extractors

This directory contains converters from open HLS graph formats into the normalized dataflow JSON schema used by this project.

## HLSyn ProGraML GEXF

HLSyn is currently the best open starting point because it includes:

- C source kernels.
- Pragma-augmented ProGraML `.gexf` graphs.
- Design-point labels for different HLS pragma settings.

Source: https://github.com/ZongyueQin/HLSyn

Convert one graph:

```bash
python3 dataflow_comm_scaling/extractors/hlsyn_gexf_to_dataflow.py \
  /path/to/HLSyn/data/graphs/aes_processed_result.gexf \
  --source-file /path/to/HLSyn/data/sources/aes_kernel.c \
  --out dataflow_comm_scaling/real_examples/aes.hlsyn.json
```

Then compute communication scaling:

```bash
python3 dataflow_comm_scaling/dataflow_comm_scaling.py \
  dataflow_comm_scaling/real_examples/aes.hlsyn.json \
  --partition topological
```

And build GNN features:

```bash
python3 dataflow_comm_scaling/gnn_feature_fusion.py \
  dataflow_comm_scaling/real_examples/aes.hlsyn.json \
  --out dataflow_comm_scaling/gnn_out/aes.hlsyn.topological.gnn.json \
  --partition topological
```

If the graph has C source line provenance but does not yet carry explicit
pragma IDs, annotate it before feature generation:

```bash
python3 dataflow_comm_scaling/extractors/annotate_pragmas.py \
  --graph-json dataflow_comm_scaling/real_examples/aes.hlsyn.json \
  --source-c /path/to/aes_kernel.c \
  --out dataflow_comm_scaling/real_examples/aes.hlsyn.pragmas.json
```

Build all extracted HLSyn graphs:

```bash
tar -xzf /path/to/HLSyn/data/HLSyn_data.tar.gz -C /tmp/HLSyn_data
conda run -n dataflow-gnn bash dataflow_comm_scaling/extractors/build_hlsyn_dataset.sh \
  /tmp/HLSyn_data/data \
  topological
```

## Current Limitations

The HLSyn graph is a source/IR-level ProGraML graph, not a post-schedule placed design. The converter therefore uses conservative heuristics:

- Bitwidth is inferred from LLVM-like type strings such as `i32`, `i8*`, or `[32 x i8]`.
- Edge kinds follow ProGraML `flow` values.
- Missing widths default to 32 bits for data/call edges and 1 bit for control/pragma edges.

This is sufficient for early feature-fusion experiments. For real congestion prediction, we still need physical labels from Vivado/Vitis/VPR implementation runs.

## Dynamatic MLIR / Handshake IR

Dynamatic is the open HLS/dataflow front-end we are wiring in next. After
running Dynamatic `compile`, inspect `out/comp/*.mlir` and convert the most
useful CF or Handshake file:

```bash
python3 dataflow_comm_scaling/extractors/dynamatic_mlir_to_dataflow.py \
  /media/xiaokewan/TOSHIBA/tools/dynamatic/out/comp/<kernel>.mlir \
  --out dataflow_comm_scaling/real_examples/<kernel>.dynamatic.json
```

The extractor is a conservative textual MLIR reader:

- operation lines become nodes;
- SSA use-def dependencies become directed edges;
- memory/control operations are tagged semantically;
- MLIR line, function, and basic-block provenance are retained;
- when textual MLIR has `loc("file":line:column)` metadata, original C
  source location is retained and the MLIR line is kept as `ir_line`.

This gives us the L2 dataflow/Handshake-level graph for the early-prediction
ablation. A future version should switch to a real MLIR parser or a Dynamatic
pass that exports JSON directly.

The flow wrapper can also run pragma annotation:

```bash
bash dataflow_comm_scaling/flows/run_dynamatic_compile_and_extract.sh \
  --source kernels/mm.c \
  --design mm \
  --out-dir dataflow_comm_scaling/real_examples/dynamatic \
  --annotate-pragmas \
  --attach-function-scope
```

`--attach-function-scope` is a coarse fallback for Dynamatic outputs that have
function names but no original C line locations. Prefer exact C line metadata
when available.

## C Pragma Annotation

`annotate_pragmas.py` parses source directives such as:

```text
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=4
#pragma HLS ARRAY_PARTITION variable=A complete dim=1
```

and attaches these fields to matched graph nodes and edges:

```text
pragma_ids
pragma_kinds
pragma_texts
```

This is the source-level provenance needed by the attribution stage:

```text
Rent-heavy region -> DFG nodes/edges -> pragma_ids -> ranked HLS cause
```

Run the bundled smoke test:

```bash
python3 dataflow_comm_scaling/extractors/annotate_pragmas.py \
  --graph-json dataflow_comm_scaling/examples/pragma_parallel_memory_raw.json \
  --source-c dataflow_comm_scaling/examples/kernels/mm.c \
  --out dataflow_comm_scaling/attribution_out/pragma_parallel_memory.annotated.json
```
