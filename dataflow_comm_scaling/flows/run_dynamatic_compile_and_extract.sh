#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Compile a C kernel with Dynamatic and extract a normalized dataflow graph.

Usage:
  run_dynamatic_compile_and_extract.sh --source KERNEL.c --design NAME --out-dir DIR [--dynamatic-root DIR]

Example:
  bash dataflow_comm_scaling/flows/run_dynamatic_compile_and_extract.sh \
    --source /media/xiaokewan/TOSHIBA/tools/dynamatic/tutorials/Introduction/Ch1/loop_multiply.c \
    --design loop_multiply \
    --out-dir dataflow_comm_scaling/real_examples/dynamatic \
    --dynamatic-root /media/xiaokewan/TOSHIBA/tools/dynamatic
USAGE
}

source_file=""
design=""
out_dir=""
dynamatic_root="${DYNAMATIC_ROOT:-/media/xiaokewan/TOSHIBA/tools/dynamatic}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      source_file="$2"
      shift 2
      ;;
    --design)
      design="$2"
      shift 2
      ;;
    --out-dir)
      out_dir="$2"
      shift 2
      ;;
    --dynamatic-root)
      dynamatic_root="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$source_file" || -z "$design" || -z "$out_dir" ]]; then
  usage >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_abs="$(realpath "$source_file")"
source_dir="$(dirname "$source_abs")"
compile_script="$(mktemp)"
mkdir -p "$out_dir" dataflow_comm_scaling/out dataflow_comm_scaling/gnn_out

printf '%s\n' \
  "set-src $source_abs" \
  "compile" \
  "exit" \
  > "$compile_script"

(
  cd "$dynamatic_root"
  ./bin/dynamatic --exit-on-failure --run "$compile_script"
)

handshake_mlir="$source_dir/out/comp/handshake_export.mlir"
if [[ ! -f "$handshake_mlir" ]]; then
  echo "Expected Dynamatic output not found: $handshake_mlir" >&2
  exit 1
fi

json_out="$out_dir/${design}.dynamatic_handshake.json"
summary_out="dataflow_comm_scaling/out/${design}.dynamatic_handshake.summary.json"
regions_out="dataflow_comm_scaling/out/${design}.dynamatic_handshake.regions.csv"
gnn_out="dataflow_comm_scaling/gnn_out/${design}.dynamatic_handshake.gnn.json"

cd "$repo_root"
python3 dataflow_comm_scaling/extractors/dynamatic_mlir_to_dataflow.py \
  "$handshake_mlir" \
  --out "$json_out"

python3 dataflow_comm_scaling/dataflow_comm_scaling.py \
  "$json_out" \
  --partition topological \
  --json-out "$summary_out" \
  --csv-out "$regions_out" \
  --quiet

python3 dataflow_comm_scaling/gnn_feature_fusion.py \
  "$json_out" \
  --partition topological \
  --max-radius 3 \
  --out "$gnn_out"

echo "dataflow: $json_out"
echo "summary:  $summary_out"
echo "gnn:      $gnn_out"
