#!/usr/bin/env python3
"""Annotate normalized dataflow JSON with C/C++ HLS pragma provenance.

The script is intentionally source-level and tool-agnostic. It parses
`#pragma HLS ...` directives from C/C++ source, infers the source range they
apply to, and attaches stable `pragma_ids` to graph nodes/edges whose
provenance lines overlap those ranges.

This is the missing bridge between:

  C source pragma -> DFG/CDFG node/edge -> Rent/GNN feature -> attribution row

It works best when an extractor preserves original C `source_file` and `line`
metadata. If line metadata is unavailable, `--attach-function-scope` provides a
coarse fallback based on function names.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence, Tuple


PRAGMA_RE = re.compile(r"^\s*#\s*pragma\s+HLS\s+(?P<body>.*)$", re.IGNORECASE)
FUNC_RE = re.compile(
    r"^\s*(?!if\b|for\b|while\b|switch\b|return\b)"
    r"(?:[A-Za-z_][\w:\<\>\s\*&,\[\]]+\s+)+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;]*\)\s*(?:\{|$)"
)
LOOP_RE = re.compile(r"\b(for|while)\s*\(|^\s*do\b")
OPTION_RE = re.compile(r"(?P<key>[A-Za-z_]\w*)\s*=\s*(?P<value>[^,\s]+)")


LOOP_PRAGMAS = {
    "PIPELINE",
    "UNROLL",
    "LOOP_TRIPCOUNT",
    "LATENCY",
    "DEPENDENCE",
    "DATAFLOW",
}
FUNCTION_PRAGMAS = {"INLINE", "TOP", "INTERFACE"}
VARIABLE_PRAGMAS = {"ARRAY_PARTITION", "ARRAY_RESHAPE", "RESOURCE", "BIND_STORAGE", "STREAM"}


@dataclass
class SourceRange:
    source_file: str
    start_line: int
    end_line: int
    function: str = ""
    target_type: str = "statement"


@dataclass
class FunctionRange:
    source_file: str
    name: str
    start_line: int
    end_line: int


@dataclass
class HlsPragma:
    id: str
    kind: str
    text: str
    source_file: str
    line: int
    options: Dict[str, str] = field(default_factory=dict)
    function: str = ""
    target_type: str = "statement"
    target_variable: str = ""
    ranges: List[SourceRange] = field(default_factory=list)


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def write_json(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
        fp.write("\n")


def strip_line_comment(line: str) -> str:
    return line.split("//", 1)[0]


def brace_delta(line: str) -> int:
    stripped = strip_line_comment(line)
    return stripped.count("{") - stripped.count("}")


def next_code_line(lines: Sequence[str], start_line: int) -> int:
    for index in range(start_line, len(lines)):
        stripped = strip_line_comment(lines[index]).strip()
        if stripped and not stripped.startswith("#"):
            return index + 1
    return min(start_line + 1, len(lines))


def find_braced_range(lines: Sequence[str], start_line: int) -> Tuple[int, int]:
    """Return 1-based source range for a braced statement/function."""
    open_line = None
    balance = 0
    for index in range(max(start_line - 1, 0), len(lines)):
        line = strip_line_comment(lines[index])
        if open_line is None and "{" not in line:
            if ";" in line:
                return start_line, index + 1
            continue
        if "{" in line and open_line is None:
            open_line = index + 1
        if open_line is not None:
            balance += brace_delta(line)
            if balance <= 0:
                return start_line, index + 1
    return start_line, len(lines)


def find_statement_range(lines: Sequence[str], start_line: int) -> Tuple[int, int]:
    stripped = strip_line_comment(lines[start_line - 1]).strip() if 0 < start_line <= len(lines) else ""
    if "{" in stripped or LOOP_RE.search(stripped):
        return find_braced_range(lines, start_line)
    for index in range(start_line - 1, len(lines)):
        if ";" in strip_line_comment(lines[index]):
            return start_line, index + 1
    return start_line, start_line


def discover_functions(source_file: str, lines: Sequence[str]) -> List[FunctionRange]:
    functions: List[FunctionRange] = []
    pending_start = 0
    pending_text = ""

    for index, raw_line in enumerate(lines, start=1):
        line = strip_line_comment(raw_line).strip()
        if not line:
            continue

        if pending_start:
            pending_text += " " + line
            if "{" not in line and ";" not in line:
                continue
            candidate = pending_text
            start_line = pending_start
            pending_start = 0
            pending_text = ""
        else:
            candidate = line
            start_line = index

        match = FUNC_RE.match(candidate)
        if not match:
            if "(" in candidate and ";" not in candidate and "{" not in candidate:
                pending_start = start_line
                pending_text = candidate
            continue
        if ";" in candidate and "{" not in candidate:
            continue
        _, end_line = find_braced_range(lines, start_line)
        functions.append(FunctionRange(source_file, match.group("name"), start_line, end_line))

    return functions


def enclosing_function(functions: Sequence[FunctionRange], line: int) -> FunctionRange | None:
    candidates = [fn for fn in functions if fn.start_line <= line <= fn.end_line]
    if not candidates:
        return None
    return max(candidates, key=lambda fn: fn.start_line)


def enclosing_loop_range(lines: Sequence[str], line: int) -> Tuple[int, int] | None:
    best = None
    for index in range(1, line + 1):
        if LOOP_RE.search(strip_line_comment(lines[index - 1])):
            start, end = find_braced_range(lines, index)
            if start <= line <= end:
                best = (start, end)
    return best


def parse_options(body: str) -> Dict[str, str]:
    options = {match.group("key"): match.group("value").strip('"') for match in OPTION_RE.finditer(body)}
    tokens = body.replace(",", " ").split()
    for index, token in enumerate(tokens[:-1]):
        key = token.strip()
        if key in {"variable", "factor", "dim", "type", "II", "depth"} and key not in options:
            value = tokens[index + 1].strip().strip('"')
            if "=" not in value:
                options[key] = value
    return options


def sanitize_id(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return clean or "pragma"


def pragma_id(kind: str, options: Dict[str, str], line: int) -> str:
    variable = options.get("variable", "")
    suffix = f"_{sanitize_id(variable)}" if variable else ""
    return f"HLS_{sanitize_id(kind)}{suffix}_L{line}"


def infer_target(
    source_file: str,
    lines: Sequence[str],
    functions: Sequence[FunctionRange],
    line: int,
    kind: str,
    options: Dict[str, str],
) -> Tuple[str, str, List[SourceRange]]:
    function = enclosing_function(functions, line)
    function_name = function.name if function else ""
    next_line = next_code_line(lines, line)
    target_variable = options.get("variable", "")

    if kind in VARIABLE_PRAGMAS and target_variable:
        if function:
            return (
                "variable",
                target_variable,
                [SourceRange(source_file, function.start_line, function.end_line, function.name, "variable")],
            )
        return ("variable", target_variable, [SourceRange(source_file, next_line, next_line, "", "variable")])

    if kind in LOOP_PRAGMAS:
        if next_line <= len(lines) and LOOP_RE.search(strip_line_comment(lines[next_line - 1])):
            start, end = find_braced_range(lines, next_line)
        else:
            loop = enclosing_loop_range(lines, line)
            start, end = loop if loop else find_statement_range(lines, next_line)
        return ("loop", "", [SourceRange(source_file, start, end, function_name, "loop")])

    if kind in FUNCTION_PRAGMAS and function:
        return (
            "function",
            "",
            [SourceRange(source_file, function.start_line, function.end_line, function.name, "function")],
        )

    start, end = find_statement_range(lines, next_line)
    return ("statement", "", [SourceRange(source_file, start, end, function_name, "statement")])


def parse_source_pragmas(source_file: str) -> Tuple[List[HlsPragma], List[FunctionRange]]:
    with open(source_file, "r", encoding="utf-8", errors="ignore") as fp:
        lines = fp.readlines()
    source_abs = os.path.abspath(source_file)
    functions = discover_functions(source_abs, lines)
    pragmas: List[HlsPragma] = []

    for index, raw_line in enumerate(lines, start=1):
        match = PRAGMA_RE.match(raw_line)
        if not match:
            continue
        body = match.group("body").strip()
        if not body:
            continue
        kind = body.split()[0].upper()
        options = parse_options(body)
        target_type, target_variable, ranges = infer_target(source_abs, lines, functions, index, kind, options)
        function = enclosing_function(functions, index)
        pragmas.append(
            HlsPragma(
                id=pragma_id(kind, options, index),
                kind=kind,
                text=raw_line.strip(),
                source_file=source_abs,
                line=index,
                options=options,
                function=function.name if function else "",
                target_type=target_type,
                target_variable=target_variable,
                ranges=ranges,
            )
        )

    return pragmas, functions


def same_source(graph_source: Any, pragma_source: str) -> bool:
    if not graph_source:
        return False
    graph_source_str = str(graph_source)
    graph_abs = os.path.abspath(graph_source_str)
    pragma_abs = os.path.abspath(pragma_source)
    if graph_abs == pragma_abs:
        return True
    if os.path.basename(graph_source_str) == os.path.basename(pragma_source):
        return True
    return graph_source_str.endswith(os.path.basename(pragma_source))


def item_lines(item: Dict[str, Any]) -> List[int]:
    lines = []
    for key in ("line", "producer_line", "consumer_line"):
        try:
            value = int(item[key])
        except (KeyError, TypeError, ValueError):
            continue
        lines.append(value)
    return lines


def item_source_files(item: Dict[str, Any]) -> List[Any]:
    sources = []
    for key in ("source_file", "producer_source_file", "consumer_source_file"):
        value = item.get(key)
        if value and value not in sources:
            sources.append(value)
    return sources


def item_function(item: Dict[str, Any]) -> str:
    return str(item.get("function", "") or "")


def item_text(item: Dict[str, Any]) -> str:
    fields = [
        "id",
        "op",
        "kind",
        "text",
        "full_text",
        "src",
        "dst",
        "semantic",
        "source_file",
    ]
    return " ".join(str(item.get(field, "")) for field in fields if item.get(field) is not None)


def has_variable_reference(item: Dict[str, Any], variable: str) -> bool | None:
    if not variable:
        return True
    text = item_text(item)
    if not text.strip():
        return None
    return bool(re.search(rf"\b{re.escape(variable)}\b", text))


def pragma_matches_item(
    pragma: HlsPragma,
    item: Dict[str, Any],
    attach_function_scope: bool,
    line_window: int,
) -> bool:
    source_matches = any(same_source(source, pragma.source_file) for source in item_source_files(item))
    function_matches = bool(pragma.function and item_function(item) == pragma.function)
    variable_match = has_variable_reference(item, pragma.target_variable)
    if variable_match is False:
        return False

    for source_range in pragma.ranges:
        if source_matches:
            for line in item_lines(item):
                if source_range.start_line - line_window <= line <= source_range.end_line + line_window:
                    return True
        if attach_function_scope and function_matches:
            return True

    if pragma.target_type == "variable" and variable_match and attach_function_scope and function_matches:
        return True
    return False


def merge_unique(existing: Any, values: Iterable[str]) -> List[str]:
    merged = [str(item) for item in existing] if isinstance(existing, list) else ([] if existing is None else [str(existing)])
    for value in values:
        if value not in merged:
            merged.append(value)
    return merged


def pragma_summary(pragma: HlsPragma) -> Dict[str, Any]:
    return {
        "id": pragma.id,
        "kind": pragma.kind,
        "text": pragma.text,
        "source_file": pragma.source_file,
        "line": pragma.line,
        "function": pragma.function,
        "target_type": pragma.target_type,
        "target_variable": pragma.target_variable,
        "options": pragma.options,
        "ranges": [
            {
                "source_file": source_range.source_file,
                "start_line": source_range.start_line,
                "end_line": source_range.end_line,
                "function": source_range.function,
                "target_type": source_range.target_type,
            }
            for source_range in pragma.ranges
        ],
    }


def annotate_item(
    item: Dict[str, Any],
    pragmas: Sequence[HlsPragma],
    attach_function_scope: bool,
    line_window: int,
) -> int:
    matches = [
        pragma
        for pragma in pragmas
        if pragma_matches_item(pragma, item, attach_function_scope=attach_function_scope, line_window=line_window)
    ]
    if not matches:
        return 0

    item["pragma_ids"] = merge_unique(item.get("pragma_ids"), [pragma.id for pragma in matches])
    item["pragma_kinds"] = merge_unique(item.get("pragma_kinds"), [pragma.kind for pragma in matches])
    item["pragma_texts"] = merge_unique(item.get("pragma_texts"), [pragma.text for pragma in matches])
    return len(matches)


def annotate_graph(
    payload: Dict[str, Any],
    pragmas: Sequence[HlsPragma],
    functions: Sequence[FunctionRange],
    source_files: Sequence[str],
    attach_function_scope: bool,
    line_window: int,
) -> Dict[str, Any]:
    annotated = dict(payload)
    annotated["nodes"] = [dict(node) for node in payload.get("nodes", [])]
    annotated["edges"] = [dict(edge) for edge in payload.get("edges", [])]

    node_hits = sum(
        1
        for node in annotated["nodes"]
        if annotate_item(node, pragmas, attach_function_scope=attach_function_scope, line_window=line_window)
    )
    edge_hits = sum(
        1
        for edge in annotated["edges"]
        if annotate_item(edge, pragmas, attach_function_scope=attach_function_scope, line_window=line_window)
    )

    annotated["pragma_provenance"] = {
        "format": "dataflow_c_pragma_provenance_v1",
        "source_files": [os.path.abspath(path) for path in source_files],
        "n_pragmas": len(pragmas),
        "n_functions": len(functions),
        "n_annotated_nodes": node_hits,
        "n_annotated_edges": edge_hits,
        "attach_function_scope": attach_function_scope,
        "line_window": line_window,
        "pragmas": [pragma_summary(pragma) for pragma in pragmas],
        "functions": [
            {
                "source_file": function.source_file,
                "name": function.name,
                "start_line": function.start_line,
                "end_line": function.end_line,
            }
            for function in functions
        ],
    }
    return annotated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Annotate normalized dataflow JSON with C HLS pragmas.")
    parser.add_argument("--graph-json", required=True, help="input normalized dataflow JSON")
    parser.add_argument(
        "--source-c",
        action="append",
        required=True,
        help="C/C++ source file containing #pragma HLS directives; can be repeated",
    )
    parser.add_argument("--out", required=True, help="output annotated normalized dataflow JSON")
    parser.add_argument("--pragma-json-out", help="optional standalone parsed pragma metadata JSON")
    parser.add_argument(
        "--attach-function-scope",
        action="store_true",
        help="coarsely attach pragmas by function when exact C source lines are unavailable",
    )
    parser.add_argument(
        "--line-window",
        type=int,
        default=0,
        help="extra line tolerance around inferred pragma target ranges",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pragmas: List[HlsPragma] = []
    functions: List[FunctionRange] = []
    for source in args.source_c:
        source_pragmas, source_functions = parse_source_pragmas(source)
        pragmas.extend(source_pragmas)
        functions.extend(source_functions)

    payload = annotate_graph(
        read_json(args.graph_json),
        pragmas=pragmas,
        functions=functions,
        source_files=args.source_c,
        attach_function_scope=args.attach_function_scope,
        line_window=max(args.line_window, 0),
    )
    write_json(args.out, payload)
    if args.pragma_json_out:
        write_json(
            args.pragma_json_out,
            {
                "format": "dataflow_c_pragma_provenance_v1",
                "source_files": [os.path.abspath(path) for path in args.source_c],
                "pragmas": [pragma_summary(pragma) for pragma in pragmas],
                "functions": [
                    {
                        "source_file": function.source_file,
                        "name": function.name,
                        "start_line": function.start_line,
                        "end_line": function.end_line,
                    }
                    for function in functions
                ],
            },
        )

    meta = payload["pragma_provenance"]
    print(
        f"wrote {args.out}: {meta['n_pragmas']} pragmas, "
        f"{meta['n_annotated_nodes']} nodes annotated, "
        f"{meta['n_annotated_edges']} edges annotated"
    )


if __name__ == "__main__":
    main()
