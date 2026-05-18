#!/usr/bin/env python3
"""Attribute Rent-aware routability risk to pragmas and source objects.

This is a deterministic baseline for explainability before a trained GNN
explainer is available. It consumes the feature-fusion JSON emitted by
gnn_feature_fusion.py, optionally augments it with hierarchical Rent features,
and ranks source pragmas or fallback source objects by communication pressure.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Sequence, Tuple


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from dataflow_comm_scaling import analyze  # noqa: E402


COMPONENT_WEIGHTS = {
    "bit_bw": 0.32,
    "memory": 0.24,
    "tensor": 0.12,
    "plain": 0.10,
    "reduce": 0.08,
    "control": 0.05,
    "hierarchy": 0.06,
    "gnn_explain": 0.03,
}

NODE_EXACT_FEATURES = {
    "plain": [
        "in_degree",
        "out_degree",
        "total_degree",
        "node_flow_balance",
        "ego_alpha_plain",
        "region_mean_flow_balance",
    ],
    "bit_bw": [
        "in_bit",
        "out_bit",
        "in_bw",
        "out_bw",
        "total_bw",
        "fanout_weighted_out_bw",
        "ego_alpha_bit",
        "ego_alpha_bw",
        "ego_max_C_bit",
        "ego_max_C_bw",
        "region_mean_C_bit",
        "region_mean_C_bw",
        "region_max_C_bw",
    ],
    "memory": [
        "kind_memory",
        "op_memory",
        "memory_in_bw",
        "memory_out_bw",
        "ego_alpha_mem",
        "ego_max_C_mem",
        "region_max_memory_fraction",
    ],
    "tensor": [
        "tensor_in_bw",
        "tensor_out_bw",
        "ego_alpha_tensor",
        "ego_max_C_tensor",
    ],
    "control": [
        "kind_control",
        "op_control",
        "control_in_bw",
        "control_out_bw",
        "ego_alpha_ctrl",
        "ego_max_C_ctrl",
    ],
    "reduce": [
        "reduce_in_bw",
        "reduce_out_bw",
        "ego_alpha_reduce",
        "ego_max_C_reduce",
    ],
}

NODE_SUBSTRING_FEATURES = {
    "plain": ["path_alpha_T_plain", "path_max_T_plain", "path_mean_T_plain"],
    "bit_bw": [
        "path_alpha_C_bit",
        "path_alpha_C_bw",
        "path_max_C_bit",
        "path_max_C_bw",
        "path_mean_C_bit",
        "path_mean_C_bw",
    ],
    "memory": [
        "path_alpha_C_mem",
        "path_max_C_mem",
        "path_mean_C_mem",
        "path_mean_memory_fraction",
        "path_max_memory_fraction",
    ],
    "tensor": ["path_alpha_C_tensor", "path_max_C_tensor", "path_mean_C_tensor"],
    "control": ["path_alpha_C_ctrl", "path_max_C_ctrl", "path_mean_C_ctrl"],
    "reduce": ["path_alpha_C_reduce", "path_max_C_reduce", "path_mean_C_reduce"],
    "hierarchy": [
        "path_depth",
        "path_mean_flow_balance",
        "path_max_flow_balance",
        "path_mean_memory_fraction",
        "path_max_memory_fraction",
    ],
}

EDGE_EXACT_FEATURES = {
    "bit_bw": ["width", "rate", "bit_demand", "bw_demand", "buffer_demand", "fanout"],
    "memory": ["is_memory"],
    "tensor": ["is_tensor"],
    "control": ["is_control"],
    "reduce": ["is_reduce"],
}

REGION_FEATURES = {
    "plain": ["T_plain", "flow_balance", "source_skew", "sink_skew"],
    "bit_bw": ["C_bit", "C_bw", "fanout_weighted_cut"],
    "memory": ["C_mem", "memory_fraction"],
    "tensor": ["C_tensor"],
    "control": ["C_ctrl"],
    "reduce": ["C_reduce"],
}

REASON_TEXT = {
    "bit_bw": "wide or high-rate boundary traffic dominates the local communication pressure",
    "memory": "memory/address/load-store communication dominates the risky region",
    "tensor": "tensor or activation movement scales faster than local compute",
    "plain": "many boundary dependencies make the region topologically Rent-heavy",
    "reduce": "broadcast, reduction, fanout, or all-to-all traffic is a dominant signal",
    "control": "control or predicate traffic contributes to boundary pressure",
    "hierarchy": "the node sits on a high-pressure recursive partition path",
    "gnn_explain": "external GNN explanation scores mark this object as important",
}


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


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return [value]


def stable_string(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("id", "name", "pragma", "text"):
            if key in value:
                return str(value[key])
        return json.dumps(value, sort_keys=True)
    return str(value)


def clean_id(value: Any) -> str:
    return stable_string(value).strip()


def source_location(provenance: Dict[str, Any], line_key: str = "line") -> str | None:
    source = provenance.get("source_file")
    line = provenance.get(line_key)
    if source and line is not None:
        return f"{source}:{line}"
    if line is not None:
        return f"line:{line}"
    return None


def display_for(entity_type: str, key: str) -> str:
    if entity_type == "pragma":
        return f"pragma:{key}"
    if entity_type == "source_line":
        return key
    return f"{entity_type}:{key}"


def provenance_entities(provenance: Dict[str, Any], fallback_id: str, fallback_type: str) -> List[Tuple[str, str]]:
    pragmas = [clean_id(item) for item in as_list(provenance.get("pragma_ids")) if clean_id(item)]
    if pragmas:
        return [("pragma", item) for item in pragmas]

    loop_id = provenance.get("loop_id")
    if loop_id not in (None, ""):
        function = provenance.get("function")
        key = f"{function}:{loop_id}" if function not in (None, "") else str(loop_id)
        return [("loop", str(key))]

    locations = []
    line_location = source_location(provenance)
    producer_location = source_location(provenance, "producer_line")
    consumer_location = source_location(provenance, "consumer_line")
    for item in (line_location, producer_location, consumer_location):
        if item and item not in locations:
            locations.append(item)
    if locations:
        return [("source_line", item) for item in locations]

    function = provenance.get("function")
    if function not in (None, ""):
        return [("function", str(function))]

    basic_block = provenance.get("basic_block")
    if basic_block not in (None, ""):
        return [("basic_block", str(basic_block))]

    return [(fallback_type, fallback_id)]


def record_source_metadata(
    record: Dict[str, Any],
    provenance: Dict[str, Any],
    entity: Tuple[str, str] | None = None,
) -> None:
    for key in ("line", "producer_line", "consumer_line"):
        location = source_location(provenance, key)
        if location:
            record["source_locations"].add(location)
    if provenance.get("function") not in (None, ""):
        record["functions"].add(str(provenance["function"]))
    if provenance.get("loop_id") not in (None, ""):
        record["loops"].add(str(provenance["loop_id"]))
    pragma_ids = [clean_id(item) for item in as_list(provenance.get("pragma_ids")) if clean_id(item)]
    pragma_kinds = [clean_id(item) for item in as_list(provenance.get("pragma_kinds")) if clean_id(item)]
    pragma_texts = [clean_id(item) for item in as_list(provenance.get("pragma_texts")) if clean_id(item)]
    if entity and entity[0] == "pragma":
        for index, pragma_id in enumerate(pragma_ids):
            if pragma_id != entity[1]:
                continue
            record["pragma_ids"].add(pragma_id)
            if index < len(pragma_kinds):
                record["pragma_kinds"].add(pragma_kinds[index])
            if index < len(pragma_texts):
                record["pragma_texts"].add(pragma_texts[index])
    else:
        record["pragma_ids"].update(pragma_ids)
        record["pragma_kinds"].update(pragma_kinds)
        record["pragma_texts"].update(pragma_texts)


def edge_key(edge: Dict[str, Any], index: int) -> str:
    return f"{edge.get('src')}->{edge.get('dst')}#{index}"


def load_explanation_scores(path: str | None) -> Tuple[Dict[str, float], Dict[str, float]]:
    if not path:
        return {}, {}
    payload = read_json(path)

    def parse_scores(value: Any, id_keys: Sequence[str]) -> Dict[str, float]:
        if isinstance(value, dict):
            return {str(key): safe_number(score) for key, score in value.items()}
        scores = {}
        for item in as_list(value):
            if not isinstance(item, dict):
                continue
            item_id = None
            for key in id_keys:
                if key in item:
                    item_id = item[key]
                    break
            if item_id is None:
                continue
            scores[str(item_id)] = safe_number(item.get("score", item.get("importance", 0.0)))
        return scores

    return (
        parse_scores(payload.get("node_scores", payload.get("nodes", {})), ("id", "node_id")),
        parse_scores(payload.get("edge_scores", payload.get("edges", {})), ("id", "edge_id")),
    )


def merge_hierarchy_features(
    nodes: Sequence[Dict[str, Any]],
    hierarchy_payload: Dict[str, Any] | None,
) -> Dict[str, Dict[str, float]]:
    merged = {str(node["id"]): dict(node.get("features", {})) for node in nodes}
    if not hierarchy_payload:
        return merged

    if hierarchy_payload.get("format") != "dataflow_multilevel_rent_v1":
        raise ValueError("hierarchy input is not dataflow_multilevel_rent_v1")
    for node in hierarchy_payload.get("nodes", []):
        node_id = str(node.get("id"))
        merged.setdefault(node_id, {}).update(node.get("features", {}))
    return merged


def feature_names_for_component(features: Dict[str, Any], component: str) -> List[str]:
    names = []
    for name in NODE_EXACT_FEATURES.get(component, []):
        if name in features:
            names.append(name)
    for name in features:
        if any(token in name for token in NODE_SUBSTRING_FEATURES.get(component, [])):
            names.append(name)
    return sorted(set(names))


def all_feature_maxima(
    feature_dicts: Sequence[Dict[str, Any]],
    component_map: Dict[str, Sequence[str]],
    substring_map: Dict[str, Sequence[str]] | None = None,
) -> Dict[str, float]:
    maxima: Dict[str, float] = defaultdict(float)
    for features in feature_dicts:
        for names in component_map.values():
            for name in names:
                maxima[name] = max(maxima[name], max(safe_number(features.get(name)), 0.0))
        if substring_map:
            for tokens in substring_map.values():
                for feature_name, value in features.items():
                    if any(token in feature_name for token in tokens):
                        maxima[feature_name] = max(maxima[feature_name], max(safe_number(value), 0.0))
    return dict(maxima)


def normalized_mean(features: Dict[str, Any], names: Sequence[str], maxima: Dict[str, float]) -> float:
    values = []
    for name in names:
        value = max(safe_number(features.get(name)), 0.0)
        max_value = maxima.get(name, 0.0)
        if max_value > 0:
            values.append(min(value / max_value, 1.0))
        elif value > 0:
            values.append(1.0)
    return sum(values) / len(values) if values else 0.0


def component_total(components: Dict[str, float]) -> float:
    return sum(COMPONENT_WEIGHTS.get(name, 0.0) * value for name, value in components.items())


def node_components(
    features: Dict[str, Any],
    maxima: Dict[str, float],
    explain_score: float = 0.0,
    explain_max: float = 0.0,
) -> Dict[str, float]:
    components = {}
    for component in NODE_EXACT_FEATURES:
        names = feature_names_for_component(features, component)
        components[component] = normalized_mean(features, names, maxima)

    hierarchy_names = feature_names_for_component(features, "hierarchy")
    components["hierarchy"] = normalized_mean(features, hierarchy_names, maxima)
    components["gnn_explain"] = min(max(explain_score, 0.0) / explain_max, 1.0) if explain_max > 0 else 0.0
    return components


def edge_components(
    features: Dict[str, Any],
    maxima: Dict[str, float],
    explain_score: float = 0.0,
    explain_max: float = 0.0,
) -> Dict[str, float]:
    components = {}
    for component, names in EDGE_EXACT_FEATURES.items():
        components[component] = normalized_mean(features, names, maxima)
    components["plain"] = 0.0
    components["hierarchy"] = 0.0
    components["gnn_explain"] = min(max(explain_score, 0.0) / explain_max, 1.0) if explain_max > 0 else 0.0
    return components


def region_components(row: Dict[str, Any], maxima: Dict[str, float]) -> Dict[str, float]:
    return {
        component: normalized_mean(row, names, maxima)
        for component, names in REGION_FEATURES.items()
    } | {"hierarchy": 0.0, "gnn_explain": 0.0}


def empty_record(entity_type: str, key: str) -> Dict[str, Any]:
    return {
        "entity_type": entity_type,
        "key": key,
        "display_name": display_for(entity_type, key),
        "score": 0.0,
        "components": defaultdict(float),
        "node_ids": set(),
        "edge_ids": set(),
        "region_ids": set(),
        "source_locations": set(),
        "functions": set(),
        "loops": set(),
        "pragma_ids": set(),
        "pragma_kinds": set(),
        "pragma_texts": set(),
        "ops": Counter(),
        "kinds": Counter(),
        "evidence": [],
    }


def add_contribution(
    records: Dict[Tuple[str, str], Dict[str, Any]],
    entity: Tuple[str, str],
    score: float,
    components: Dict[str, float],
    evidence: Dict[str, Any],
    provenance: Dict[str, Any],
) -> None:
    record = records.setdefault(entity, empty_record(*entity))
    record["score"] += score
    for component, value in components.items():
        record["components"][component] += COMPONENT_WEIGHTS.get(component, 0.0) * value
    record_source_metadata(record, provenance, entity)
    if evidence.get("node_id"):
        record["node_ids"].add(str(evidence["node_id"]))
    if evidence.get("edge_id"):
        record["edge_ids"].add(str(evidence["edge_id"]))
    if evidence.get("region_id"):
        record["region_ids"].add(str(evidence["region_id"]))
    if evidence.get("op"):
        record["ops"][str(evidence["op"])] += 1
    if evidence.get("node_kind"):
        record["kinds"][str(evidence["node_kind"])] += 1
    elif evidence.get("edge_kind"):
        record["kinds"][str(evidence["edge_kind"])] += 1
    item = dict(evidence)
    item["score"] = score
    item["components"] = {
        key: COMPONENT_WEIGHTS.get(key, 0.0) * value
        for key, value in components.items()
        if COMPONENT_WEIGHTS.get(key, 0.0) * value > 0
    }
    record["evidence"].append(item)


def top_items(counter: Counter, limit: int = 6) -> List[str]:
    return [item for item, _ in counter.most_common(limit)]


def finalize_records(records: Dict[Tuple[str, str], Dict[str, Any]], top_k_evidence: int) -> List[Dict[str, Any]]:
    if not records:
        return []
    max_score = max(record["score"] for record in records.values()) or 1.0
    finalized = []
    for record in records.values():
        components = {key: safe_number(value) for key, value in record["components"].items() if value > 0}
        dominant = sorted(components.items(), key=lambda item: item[1], reverse=True)
        reasons = [REASON_TEXT[name] for name, _ in dominant[:3] if name in REASON_TEXT]
        evidence = sorted(record["evidence"], key=lambda item: item["score"], reverse=True)[:top_k_evidence]
        finalized.append(
            {
                "entity_type": record["entity_type"],
                "key": record["key"],
                "display_name": record["display_name"],
                "score": record["score"],
                "normalized_score": record["score"] / max_score,
                "components": components,
                "dominant_components": [name for name, _ in dominant[:5]],
                "reasons": reasons,
                "n_nodes": len(record["node_ids"]),
                "n_edges": len(record["edge_ids"]),
                "n_regions": len(record["region_ids"]),
                "node_ids": sorted(record["node_ids"]),
                "edge_ids": sorted(record["edge_ids"]),
                "region_ids": sorted(record["region_ids"]),
                "source_locations": sorted(record["source_locations"]),
                "functions": sorted(record["functions"]),
                "loops": sorted(record["loops"]),
                "pragma_ids": sorted(record["pragma_ids"]),
                "pragma_kinds": sorted(record["pragma_kinds"]),
                "pragma_texts": sorted(record["pragma_texts"]),
                "top_ops": top_items(record["ops"]),
                "top_kinds": top_items(record["kinds"]),
                "top_evidence": evidence,
            }
        )
    finalized.sort(key=lambda item: item["score"], reverse=True)
    for rank, item in enumerate(finalized, start=1):
        item["rank"] = rank
    return finalized


def region_rows_from_graph(
    graph_json: str | None,
    partition: str,
    min_nodes: int,
    seed: int,
) -> List[Dict[str, Any]]:
    if not graph_json:
        return []
    _, rows = analyze(graph_json, min_nodes=min_nodes, partition=partition, seed=seed)
    return [row for row in rows if row.get("region_id") != "r" and safe_number(row.get("B_node")) > 1]


def infer_partition_args(
    gnn_payload: Dict[str, Any],
    hierarchy_payload: Dict[str, Any] | None,
    partition: str | None,
    min_nodes: int | None,
) -> Tuple[str, int]:
    if partition:
        inferred_partition = partition
    elif gnn_payload.get("partition"):
        inferred_partition = str(gnn_payload["partition"])
    elif hierarchy_payload and hierarchy_payload.get("partitions"):
        inferred_partition = str(hierarchy_payload["partitions"][0])
    else:
        inferred_partition = "topological"

    if min_nodes is not None:
        inferred_min_nodes = min_nodes
    elif hierarchy_payload and hierarchy_payload.get("min_nodes_values"):
        inferred_min_nodes = int(hierarchy_payload["min_nodes_values"][0])
    else:
        inferred_min_nodes = 1
    return inferred_partition, inferred_min_nodes


def build_attribution(
    feature_payload: Dict[str, Any],
    hierarchy_payload: Dict[str, Any] | None,
    graph_json: str | None,
    explanation_json: str | None,
    partition: str | None,
    min_nodes: int | None,
    seed: int,
    top_k_evidence: int,
) -> Dict[str, Any]:
    if feature_payload.get("format") != "dataflow_gnn_feature_fusion_v1":
        raise ValueError("features input is not dataflow_gnn_feature_fusion_v1")

    nodes = feature_payload.get("nodes", [])
    edges = feature_payload.get("edges", [])
    node_features = merge_hierarchy_features(nodes, hierarchy_payload)
    node_by_id = {str(node["id"]): node for node in nodes}
    node_scores, edge_scores = load_explanation_scores(explanation_json)

    node_maxima = all_feature_maxima(list(node_features.values()), NODE_EXACT_FEATURES, NODE_SUBSTRING_FEATURES)
    edge_maxima = all_feature_maxima(
        [edge.get("features", {}) for edge in edges],
        EDGE_EXACT_FEATURES,
        None,
    )
    node_explain_max = max((safe_number(value) for value in node_scores.values()), default=0.0)
    edge_explain_max = max((safe_number(value) for value in edge_scores.values()), default=0.0)

    records: Dict[Tuple[str, str], Dict[str, Any]] = {}
    fallback_counts = Counter()

    for node in nodes:
        node_id = str(node["id"])
        provenance = node.get("provenance", {})
        entities = provenance_entities(provenance, node_id, "node")
        for entity_type, _ in entities:
            fallback_counts[entity_type] += 1
        components = node_components(
            node_features.get(node_id, {}),
            node_maxima,
            explain_score=safe_number(node_scores.get(node_id)),
            explain_max=node_explain_max,
        )
        score = component_total(components)
        evidence = {
            "evidence_type": "node",
            "node_id": node_id,
            "op": node.get("op"),
            "node_kind": node.get("kind"),
            "component_total": score,
        }
        for entity in entities:
            add_contribution(records, entity, score, components, evidence, provenance)

    for index, edge in enumerate(edges):
        edge_id = edge_key(edge, index)
        provenance = edge.get("provenance", {})
        entities = provenance_entities(provenance, edge_id, "edge")
        for entity_type, _ in entities:
            fallback_counts[entity_type] += 1
        components = edge_components(
            edge.get("features", {}),
            edge_maxima,
            explain_score=safe_number(edge_scores.get(edge_id)),
            explain_max=edge_explain_max,
        )
        score = component_total(components)
        evidence = {
            "evidence_type": "edge",
            "edge_id": edge_id,
            "src": edge.get("src"),
            "dst": edge.get("dst"),
            "edge_kind": edge.get("kind"),
            "semantic": edge.get("semantic"),
            "component_total": score,
        }
        for entity in entities:
            add_contribution(records, entity, score, components, evidence, provenance)

    inferred_partition, inferred_min_nodes = infer_partition_args(
        feature_payload,
        hierarchy_payload,
        partition,
        min_nodes,
    )
    region_rows = region_rows_from_graph(graph_json, inferred_partition, inferred_min_nodes, seed)
    region_maxima = all_feature_maxima(region_rows, REGION_FEATURES, None)
    for row in region_rows:
        node_ids = [str(node_id) for node_id in row.get("node_ids", [])]
        if not node_ids:
            continue
        components = region_components(row, region_maxima)
        score = component_total(components)
        if score <= 0:
            continue
        entity_hits: Dict[Tuple[str, str], int] = defaultdict(int)
        provenance_by_entity: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for node_id in node_ids:
            node = node_by_id.get(node_id)
            if not node:
                continue
            provenance = node.get("provenance", {})
            for entity in provenance_entities(provenance, node_id, "node"):
                entity_hits[entity] += 1
                provenance_by_entity.setdefault(entity, provenance)

        for entity, hits in entity_hits.items():
            share = hits / len(node_ids)
            evidence = {
                "evidence_type": "region",
                "region_id": row.get("region_id"),
                "level": row.get("level"),
                "B_node": row.get("B_node"),
                "T_plain": row.get("T_plain"),
                "C_bit": row.get("C_bit"),
                "C_bw": row.get("C_bw"),
                "C_mem": row.get("C_mem"),
                "C_tensor": row.get("C_tensor"),
                "C_ctrl": row.get("C_ctrl"),
                "C_reduce": row.get("C_reduce"),
                "memory_fraction": row.get("memory_fraction"),
                "component_total": score,
                "entity_node_share": share,
            }
            add_contribution(records, entity, score * share, components, evidence, provenance_by_entity[entity])

    attributions = finalize_records(records, top_k_evidence)
    graph_features = feature_payload.get("graph_features", {})
    labels = feature_payload.get("labels", {})

    return {
        "format": "dataflow_pragma_attribution_v1",
        "name": feature_payload.get("name"),
        "source": feature_payload.get("source"),
        "feature_source": feature_payload.get("source"),
        "hierarchy_source": hierarchy_payload.get("source") if hierarchy_payload else None,
        "graph_json": graph_json,
        "partition": inferred_partition,
        "min_nodes": inferred_min_nodes,
        "seed": seed,
        "score_config": {
            "component_weights": COMPONENT_WEIGHTS,
            "node_exact_features": NODE_EXACT_FEATURES,
            "node_substring_features": NODE_SUBSTRING_FEATURES,
            "edge_exact_features": EDGE_EXACT_FEATURES,
            "region_features": REGION_FEATURES,
        },
        "summary": {
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "n_regions_used": len(region_rows),
            "n_attributions": len(attributions),
            "entity_type_counts": dict(Counter(item["entity_type"] for item in attributions)),
            "fallback_input_counts": dict(fallback_counts),
            "has_labels": bool(labels),
            "has_hierarchy": hierarchy_payload is not None,
            "has_region_reconstruction": bool(region_rows),
            "has_gnn_explanation": explanation_json is not None,
        },
        "graph_features": graph_features,
        "labels": labels,
        "attributions": attributions,
    }


def write_csv(path: str, rows: Sequence[Dict[str, Any]]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    fieldnames = [
        "rank",
        "entity_type",
        "key",
        "display_name",
        "score",
        "normalized_score",
        "dominant_components",
        "reasons",
        "n_nodes",
        "n_edges",
        "n_regions",
        "source_locations",
        "functions",
        "loops",
        "pragma_ids",
        "pragma_kinds",
        "pragma_texts",
        "top_ops",
        "top_kinds",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            serializable = {}
            for key in fieldnames:
                value = row.get(key, "")
                if isinstance(value, list):
                    serializable[key] = ";".join(str(item) for item in value)
                else:
                    serializable[key] = value
            writer.writerow(serializable)


def print_summary(payload: Dict[str, Any], limit: int) -> None:
    summary = payload["summary"]
    print(
        f"design: {payload.get('name')} | "
        f"attributions: {summary['n_attributions']} | "
        f"regions used: {summary['n_regions_used']} | "
        f"entity types: {summary['entity_type_counts']}"
    )
    for item in payload["attributions"][:limit]:
        components = ",".join(item["dominant_components"][:3])
        locations = ",".join(item["source_locations"][:2])
        print(
            f"{item['rank']:>3}. {item['display_name']} "
            f"score={item['score']:.4f} norm={item['normalized_score']:.3f} "
            f"components={components} locations={locations}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attribute Rent-aware communication risk to pragmas/source objects.")
    parser.add_argument("--features", required=True, help="input dataflow_gnn_feature_fusion_v1 JSON")
    parser.add_argument("--hierarchy", help="optional dataflow_multilevel_rent_v1 JSON")
    parser.add_argument("--graph-json", help="optional normalized graph JSON for region reconstruction")
    parser.add_argument("--explanation", help="optional external GNN explanation JSON with node_scores/edge_scores")
    parser.add_argument("--partition", choices=("topological", "mincut", "random"), help="region partition strategy")
    parser.add_argument("--min-nodes", type=int, help="minimum nodes for reconstructed regions")
    parser.add_argument("--seed", type=int, default=0, help="seed for random partition reconstruction")
    parser.add_argument("--out", required=True, help="output attribution JSON")
    parser.add_argument("--csv-out", help="optional output attribution CSV")
    parser.add_argument("--top-k-evidence", type=int, default=8, help="number of evidence items per attribution")
    parser.add_argument("--print-top", type=int, default=10, help="print top-K attribution rows")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_attribution(
        feature_payload=read_json(args.features),
        hierarchy_payload=read_json(args.hierarchy) if args.hierarchy else None,
        graph_json=args.graph_json,
        explanation_json=args.explanation,
        partition=args.partition,
        min_nodes=args.min_nodes,
        seed=args.seed,
        top_k_evidence=args.top_k_evidence,
    )
    write_json(args.out, payload)
    if args.csv_out:
        write_csv(args.csv_out, payload["attributions"])
    print_summary(payload, args.print_top)


if __name__ == "__main__":
    main()
