#!/usr/bin/env python3
"""Compare Rent/dataflow scaling under different recursive partitions."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from typing import Any, Dict, List, Sequence


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from dataflow_comm_scaling import analyze, write_csv, write_json  # noqa: E402


ALPHA_KEYS = [
    "alpha_plain",
    "alpha_bit",
    "alpha_bw",
    "alpha_mem",
    "alpha_tensor",
    "alpha_ctrl",
    "alpha_reduce",
]


def safe_number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def parse_csv_list(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def compact_row(summary: Dict[str, Any]) -> Dict[str, Any]:
    row = {
        "design": summary["name"],
        "partition": summary["partition"],
        "n_nodes": summary["n_nodes"],
        "n_edges": summary["n_edges"],
        "n_regions": summary["n_regions"],
    }
    for key in ALPHA_KEYS:
        fit = summary["fits"].get(key, {})
        row[key] = fit.get("alpha")
        row[key.replace("alpha_", "k_")] = fit.get("k")
        row[f"{key}_r2"] = fit.get("r2")
    row.update({f"aggregate_{key}": safe_number(value) for key, value in summary["aggregate"].items()})
    return row


def attach_deltas(rows: Sequence[Dict[str, Any]], baseline: str = "topological") -> List[Dict[str, Any]]:
    by_partition = {row["partition"]: row for row in rows}
    base = by_partition.get(baseline)
    out = []
    for row in rows:
        enriched = dict(row)
        if base:
            for key in ALPHA_KEYS:
                if row.get(key) is None or base.get(key) is None:
                    enriched[f"delta_{key}_vs_{baseline}"] = None
                else:
                    enriched[f"delta_{key}_vs_{baseline}"] = safe_number(row.get(key)) - safe_number(base.get(key))
        out.append(enriched)
    return out


def log_points(rows: Sequence[Dict[str, Any]], metric: str) -> List[tuple[float, float]]:
    points = []
    for row in rows:
        b_node = safe_number(row.get("B_node"))
        value = safe_number(row.get(metric))
        if b_node > 1 and value > 0:
            points.append((math.log2(b_node), math.log2(value)))
    return points


def plot_loglog(
    partition_rows: Dict[str, Sequence[Dict[str, Any]]],
    summaries: Dict[str, Dict[str, Any]],
    metric: str,
    out_path: str,
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required for plotting") from exc

    directory = os.path.dirname(out_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    _, ax = plt.subplots(figsize=(7.2, 5.0))
    for partition, rows in partition_rows.items():
        points = log_points(rows, metric)
        if not points:
            continue
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        alpha_name = {
            "T_plain": "alpha_plain",
            "C_bit": "alpha_bit",
            "C_bw": "alpha_bw",
            "C_mem": "alpha_mem",
            "C_tensor": "alpha_tensor",
            "C_ctrl": "alpha_ctrl",
            "C_reduce": "alpha_reduce",
        }[metric]
        fit = summaries[partition]["fits"][alpha_name]
        alpha = fit.get("alpha")
        k_value = fit.get("k")
        label = partition
        if alpha is not None:
            label = f"{partition} alpha={float(alpha):.3f}"
        ax.scatter(xs, ys, s=22, alpha=0.65, label=label)
        if alpha is not None and k_value is not None and xs:
            x0, x1 = min(xs), max(xs)
            fit_x = [x0, x1]
            fit_y = [math.log2(float(k_value)) + float(alpha) * x for x in fit_x]
            ax.plot(fit_x, fit_y, linewidth=1.6)

    ax.set_title(f"Rent scatter: log2({metric}) vs log2(B_node)")
    ax.set_xlabel("log2(B_node)")
    ax.set_ylabel(f"log2({metric})")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.45)
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()


def print_table(rows: Sequence[Dict[str, Any]]) -> None:
    keys = ["partition", "alpha_plain", "alpha_bit", "alpha_bw", "alpha_mem", "alpha_tensor"]
    widths = {key: max(len(key), 12) for key in keys}

    def format_value(value: Any) -> str:
        if value is None:
            return "n/a"
        return f"{value:.4f}" if isinstance(value, float) else str(value)

    for row in rows:
        for key in keys:
            widths[key] = max(widths[key], len(format_value(row.get(key))))

    print("  ".join(key.ljust(widths[key]) for key in keys))
    print("  ".join("-" * widths[key] for key in keys))
    for row in rows:
        fields = []
        for key in keys:
            fields.append(format_value(row.get(key)).ljust(widths[key]))
        print("  ".join(fields))

    baseline = next((row for row in rows if row["partition"] == "topological"), None)
    hmetis = next((row for row in rows if row["partition"] == "hmetis"), None)
    if baseline and hmetis:
        print("\nhmetis - topological deltas:")
        for key in ("alpha_plain", "alpha_bit", "alpha_bw", "alpha_mem", "alpha_tensor"):
            if hmetis.get(key) is None or baseline.get(key) is None:
                print(f"  {key}: n/a")
            else:
                delta = safe_number(hmetis[key]) - safe_number(baseline[key])
                print(f"  {key}: {delta:+.4f}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Rent exponents across partition strategies.")
    parser.add_argument("graph_json", help="input normalized dataflow graph JSON")
    parser.add_argument(
        "--partitions",
        default="topological,hmetis",
        help="comma-separated strategies: topological,mincut,random,hmetis",
    )
    parser.add_argument("--metric", default="T_plain", help="scatter Y metric, e.g. T_plain,C_bw,C_mem")
    parser.add_argument("--min-nodes", type=int, default=1, help="minimum nodes per recursive region")
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    parser.add_argument("--hmetis-path", help="path to hMetis shmetis executable")
    parser.add_argument("--hmetis-ubfactor", type=int, default=5, help="hMetis balance tolerance")
    parser.add_argument("--out-dir", default="dataflow_comm_scaling/analysis_out", help="output directory")
    parser.add_argument("--prefix", help="output filename prefix")
    parser.add_argument("--no-plot", action="store_true", help="skip matplotlib scatter plot")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    partitions = parse_csv_list(args.partitions)
    prefix = args.prefix or os.path.splitext(os.path.basename(args.graph_json))[0]
    os.makedirs(args.out_dir, exist_ok=True)

    summaries: Dict[str, Dict[str, Any]] = {}
    partition_rows: Dict[str, Sequence[Dict[str, Any]]] = {}
    compact_rows = []
    for partition in partitions:
        summary, rows = analyze(
            args.graph_json,
            min_nodes=args.min_nodes,
            partition=partition,
            seed=args.seed,
            hmetis_path=args.hmetis_path,
            hmetis_ubfactor=args.hmetis_ubfactor,
        )
        summaries[partition] = summary
        partition_rows[partition] = rows
        compact_rows.append(compact_row(summary))

        write_csv(os.path.join(args.out_dir, f"{prefix}.{partition}.regions.csv"), rows)
        write_json(os.path.join(args.out_dir, f"{prefix}.{partition}.summary.json"), summary)

    comparison_rows = attach_deltas(compact_rows)
    comparison_csv = os.path.join(args.out_dir, f"{prefix}.partition_compare.csv")
    with open(comparison_csv, "w", newline="", encoding="utf-8") as fp:
        fieldnames = sorted({key for row in comparison_rows for key in row})
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comparison_rows)

    plot_path = None
    if not args.no_plot:
        plot_path = os.path.join(args.out_dir, f"{prefix}.{args.metric}.loglog_scatter.png")
        plot_loglog(partition_rows, summaries, args.metric, plot_path)

    print(f"graph: {args.graph_json}")
    print_table(comparison_rows)
    print(f"\nwrote: {comparison_csv}")
    if plot_path:
        print(f"plot:  {plot_path}")


if __name__ == "__main__":
    main()
