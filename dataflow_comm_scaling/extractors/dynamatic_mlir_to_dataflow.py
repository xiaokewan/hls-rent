#!/usr/bin/env python3
"""Convert Dynamatic MLIR/Handshake IR to normalized dataflow JSON.

This is a lightweight textual extractor for early experiments. It treats MLIR
operations as nodes and SSA use-def dependencies as directed edges. It is not a
full MLIR parser, but it works well enough for Dynamatic's CF/Handshake files
and keeps line/function/basic-block provenance for later root-cause analysis.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


RESULT_RE = re.compile(r"^\s*(?:(?P<results>%[\w\d_]+(?:\s*,\s*%[\w\d_]+)*)\s*=\s*)?(?P<op>[\w.]+)")
SSA_RE = re.compile(r"%[\w\d_]+")
FUNC_RE = re.compile(r"(?:func\.func|handshake\.func)\s+@([\w\d_.$-]+)")
BLOCK_RE = re.compile(r"^\s*\^([\w\d_.$-]+)")
HANDSHAKE_NAME_RE = re.compile(r'handshake\.name\s*=\s*"([^"]+)"')
HANDSHAKE_BB_RE = re.compile(r"handshake\.bb\s*=\s*(\d+)")
ARG_RE = re.compile(r"(%[\w\d_]+)\s*:\s*([^,\)]+)")


CONTROL_OPS = {
    "br",
    "cf.br",
    "cond_br",
    "cf.cond_br",
    "control_merge",
    "merge",
    "end",
    "return",
    "source",
}
MEMORY_OPS = {"load", "memref.load", "store", "memref.store", "mem_controller"}
DATAFLOW_OPS = {
    "fork",
    "lazy_fork",
    "join",
    "mux",
    "constant",
    "buffer",
    "oehb",
    "tehb",
    "ofifo",
    "tfifo",
    "sink",
}


def strip_comment(line: str) -> str:
    return line.split("//", 1)[0].rstrip()


def infer_width(text: str, default: int = 32) -> int:
    widths = [int(match) for match in re.findall(r"\bi(\d+)\b", text)]
    if "f64" in text or "double" in text:
        widths.append(64)
    if "f32" in text or "float" in text:
        widths.append(32)
    return max(widths) if widths else default


def classify_op(op: str, text: str) -> Tuple[str, str]:
    lower_op = op.lower()
    if lower_op in MEMORY_OPS or "memref<" in text:
        return "memory", "memory"
    if lower_op in CONTROL_OPS or "control<" in text:
        return "control", "control"
    if lower_op in DATAFLOW_OPS or lower_op.startswith("handshake."):
        return "dataflow", "scalar"
    if lower_op.startswith("arith."):
        return "compute", "scalar"
    return "compute", "scalar"


def classify_arg(type_text: str) -> Tuple[str, str, int]:
    if "memref<" in type_text:
        return "memory", "memory", infer_width(type_text)
    if "control<" in type_text:
        return "control", "control", 1
    return "io", "scalar", infer_width(type_text)


def edge_semantic(src_kind: str, dst_kind: str, dst_semantic: str) -> Tuple[str, str]:
    if "memory" in {src_kind, dst_kind} or dst_semantic == "memory":
        return "memory", "memory"
    if "control" in {src_kind, dst_kind} or dst_semantic == "control":
        return "control", "control"
    return "data", "scalar"


def stable_node_id(base: str, used: Dict[str, int]) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.$-]+", "_", base).strip("_") or "node"
    index = used.get(clean, 0)
    used[clean] = index + 1
    return clean if index == 0 else f"{clean}_{index}"


def operation_name(op: str, results: List[str], line: str, line_no: int) -> str:
    handshake_name = HANDSHAKE_NAME_RE.search(line)
    if handshake_name:
        return handshake_name.group(1)
    if results:
        return results[0].lstrip("%")
    return f"{op.replace('.', '_')}_{line_no}"


def parse_signature_args(signature: str) -> List[Tuple[str, str]]:
    return [(match.group(1), match.group(2).strip()) for match in ARG_RE.finditer(signature)]


def convert_mlir(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        raw_lines = fp.readlines()

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    producer: Dict[str, str] = {}
    producer_line: Dict[str, int] = {}
    node_kind: Dict[str, str] = {}
    used_ids: Dict[str, int] = {}
    current_function = ""
    current_block = ""
    collecting_signature = False
    signature_lines: List[str] = []

    def add_arg(var: str, type_text: str, line_no: int) -> None:
        if var in producer:
            return
        kind, semantic, width = classify_arg(type_text)
        node_id = stable_node_id(f"arg_{current_function}_{var.lstrip('%')}", used_ids)
        nodes.append(
            {
                "id": node_id,
                "op": "argument",
                "kind": kind,
                "area": 1,
                "inferred_width": width,
                "source_file": path,
                "line": line_no,
                "function": current_function,
                "basic_block": current_block,
            }
        )
        producer[var] = node_id
        producer_line[var] = line_no
        node_kind[node_id] = kind

    for line_no, raw_line in enumerate(raw_lines, start=1):
        line = strip_comment(raw_line)
        if not line.strip():
            continue

        func_match = FUNC_RE.search(line)
        if func_match:
            current_function = func_match.group(1)
            collecting_signature = "{" not in line
            signature_lines = [line]
            if "{" in line:
                for var, type_text in parse_signature_args(line):
                    add_arg(var, type_text, line_no)
            continue

        if collecting_signature:
            signature_lines.append(line)
            if "{" in line:
                signature = " ".join(signature_lines)
                for var, type_text in parse_signature_args(signature):
                    add_arg(var, type_text, line_no)
                collecting_signature = False
            continue

        block_match = BLOCK_RE.match(line)
        if block_match:
            current_block = block_match.group(1)
            for var, type_text in parse_signature_args(line):
                add_arg(var, type_text, line_no)
            continue

        stripped = line.strip()
        if stripped in {"module {", "}", "};"} or stripped.startswith(("module ", "func.func ", "handshake.func ")):
            continue
        if stripped.startswith(("//", "#", "attributes")):
            continue

        match = RESULT_RE.match(line)
        if not match:
            continue
        op = match.group("op")
        if op in {"module", "func.func", "handshake.func"}:
            continue

        results = [item.strip() for item in (match.group("results") or "").split(",") if item.strip()]
        operands = [ssa for ssa in SSA_RE.findall(line) if ssa not in results]
        kind, semantic = classify_op(op, line)
        width = infer_width(line, default=1 if kind == "control" else 32)
        bb_attr = HANDSHAKE_BB_RE.search(line)
        node_id = stable_node_id(operation_name(op, results, line, line_no), used_ids)

        nodes.append(
            {
                "id": node_id,
                "op": op,
                "kind": kind,
                "area": 1,
                "inferred_width": width,
                "source_file": path,
                "line": line_no,
                "function": current_function,
                "basic_block": bb_attr.group(1) if bb_attr else current_block,
                "text": stripped,
            }
        )
        node_kind[node_id] = kind

        for operand in operands:
            src = producer.get(operand)
            if not src:
                continue
            edge_kind, edge_sem = edge_semantic(node_kind.get(src, "compute"), kind, semantic)
            edges.append(
                {
                    "src": src,
                    "dst": node_id,
                    "width": width if edge_kind != "control" else 1,
                    "rate": 1,
                    "kind": edge_kind,
                    "semantic": edge_sem,
                    "source_file": path,
                    "producer_line": producer_line.get(operand),
                    "consumer_line": line_no,
                    "function": current_function,
                    "basic_block": bb_attr.group(1) if bb_attr else current_block,
                }
            )

        for result in results:
            producer[result] = node_id
            producer_line[result] = line_no

    return {
        "name": os.path.splitext(os.path.basename(path))[0],
        "description": "Converted from Dynamatic textual MLIR/Handshake IR.",
        "source_graph": path,
        "source_file": path,
        "nodes": nodes,
        "edges": edges,
    }


def write_json(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
        fp.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Dynamatic MLIR/Handshake IR to normalized dataflow JSON.")
    parser.add_argument("mlir", help="input .mlir file")
    parser.add_argument("--out", required=True, help="output normalized dataflow JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = convert_mlir(args.mlir)
    write_json(args.out, payload)
    print(f"wrote {args.out}: {len(payload['nodes'])} nodes, {len(payload['edges'])} edges")


if __name__ == "__main__":
    main()
