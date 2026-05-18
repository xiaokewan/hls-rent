#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 <HLSyn extracted data dir> [partition]" >&2
  echo "Example: $0 /tmp/HLSyn_data/data topological" >&2
  exit 1
fi

HLSYN_DATA_DIR="$1"
PARTITION="${2:-topological}"

GRAPH_DIR="$HLSYN_DATA_DIR/graphs"
SOURCE_DIR="$HLSYN_DATA_DIR/sources"
OUT_GRAPH_DIR="dataflow_comm_scaling/real_examples/hlsyn"
OUT_SUMMARY_DIR="dataflow_comm_scaling/out/hlsyn"
OUT_GNN_DIR="dataflow_comm_scaling/gnn_out/hlsyn"

mkdir -p "$OUT_GRAPH_DIR" "$OUT_SUMMARY_DIR" "$OUT_GNN_DIR"

for graph in "$GRAPH_DIR"/*_processed_result.gexf; do
  base=$(basename "$graph" _processed_result.gexf)
  source_file="$SOURCE_DIR/${base}_kernel.c"
  normalized="$OUT_GRAPH_DIR/${base}.json"

  if [ -f "$source_file" ]; then
    python3 dataflow_comm_scaling/extractors/hlsyn_gexf_to_dataflow.py \
      "$graph" \
      --source-file "$source_file" \
      --out "$normalized" >/dev/null
  else
    python3 dataflow_comm_scaling/extractors/hlsyn_gexf_to_dataflow.py \
      "$graph" \
      --out "$normalized" >/dev/null
  fi

  python3 dataflow_comm_scaling/dataflow_comm_scaling.py \
    "$normalized" \
    --partition "$PARTITION" \
    --json-out "$OUT_SUMMARY_DIR/${base}.${PARTITION}.summary.json" \
    --csv-out "$OUT_SUMMARY_DIR/${base}.${PARTITION}.regions.csv" \
    --quiet

  python3 dataflow_comm_scaling/gnn_feature_fusion.py \
    "$normalized" \
    --out "$OUT_GNN_DIR/${base}.${PARTITION}.gnn.json" \
    --partition "$PARTITION" \
    --max-radius 3 >/dev/null
done

echo "Built HLSyn normalized graphs, summaries, and GNN feature graphs with partition=$PARTITION"

