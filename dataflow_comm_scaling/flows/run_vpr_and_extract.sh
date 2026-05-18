#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Run VPR and extract routability labels.

Usage:
  run_vpr_and_extract.sh --design NAME --arch ARCH.xml --circuit CIRCUIT.blif --out-dir DIR [--vpr /path/to/vpr] [-- EXTRA_VPR_ARGS...]

Example:
  bash dataflow_comm_scaling/flows/run_vpr_and_extract.sh \
    --design aes \
    --arch /path/to/k6_frac_N10.xml \
    --circuit runs/aes/aes.blif \
    --out-dir runs/vpr/aes \
    --vpr /home/xiaokewan/Software/vtr-verilog-to-routing-master/build/vpr/vpr \
    -- --route_chan_width 120
USAGE
}

design=""
arch=""
circuit=""
out_dir=""
vpr_bin="${VPR_BIN:-vpr}"
extra_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --design)
      design="$2"
      shift 2
      ;;
    --arch)
      arch="$2"
      shift 2
      ;;
    --circuit)
      circuit="$2"
      shift 2
      ;;
    --out-dir)
      out_dir="$2"
      shift 2
      ;;
    --vpr)
      vpr_bin="$2"
      shift 2
      ;;
    --)
      shift
      extra_args=("$@")
      break
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

if [[ -z "$design" || -z "$arch" || -z "$circuit" || -z "$out_dir" ]]; then
  usage >&2
  exit 2
fi

mkdir -p "$out_dir"
log="$out_dir/vpr.log"
labels="$out_dir/${design}.vpr.labels.json"

"$vpr_bin" "$arch" "$circuit" "${extra_args[@]}" 2>&1 | tee "$log"

python3 dataflow_comm_scaling/labels/extract_routability_labels.py \
  --tool vpr \
  --design "$design" \
  --reports "$log" \
  --out "$labels"

echo "labels: $labels"
