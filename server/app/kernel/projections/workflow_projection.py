"""workflow_projection

Build workflow projections from canonical workflow spec.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def build_workflow_components(spec_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build component projections from workflow spec."""
    graph = spec_json.get("graph") or {}
    nodes = graph.get("nodes") or []
    components: List[Dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        components.append(
            {
                "component_id": str(node.get("id") or ""),
                "component_type": str(node.get("type") or ""),
                "name": node.get("name"),
                "spec_json": node.get("params") or {},
                "ui_json": node.get("ui"),
            }
        )
    return components


def build_workflow_edges(spec_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build edge projections from workflow spec."""
    graph = spec_json.get("graph") or {}
    edges = graph.get("edges") or []
    out: List[Dict[str, Any]] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        edge_id = str(edge.get("id") or "")
        from_id = str(edge.get("from") or "")
        to_id = str(edge.get("to") or "")
        edge_spec = {k: v for k, v in edge.items() if k not in ("id", "from", "to")}
        out.append(
            {
                "edge_id": edge_id,
                "from_component_id": from_id,
                "to_component_id": to_id,
                "edge_spec_json": edge_spec,
            }
        )
    return out


def build_workflow_refs(spec_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract external references from workflow spec."""
    graph = spec_json.get("graph") or {}
    nodes = graph.get("nodes") or []
    refs: List[Dict[str, Any]] = []
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        params = node.get("params") or {}
        if not isinstance(params, (dict, list)):
            continue
        node_path = f"$.graph.nodes[{idx}].params"
        refs.extend(_extract_refs(params, node_path))
    return refs


def _extract_refs(value: Any, base_path: str) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    if isinstance(value, dict):
        for key, val in value.items():
            path = f"{base_path}.{key}"
            if key in {"tool_ref", "knowledge_ref", "model_ref", "plugin_ref", "secret_ref"}:
                ref_type = "knowledge" if key == "knowledge_ref" else key.replace("_ref", "")
                ref_entry = _build_ref_entry(ref_type, val, path)
                if ref_entry:
                    refs.append(ref_entry)
                continue
            refs.extend(_extract_refs(val, path))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            path = f"{base_path}[{idx}]"
            refs.extend(_extract_refs(item, path))
    return refs


def _build_ref_entry(ref_type: str, raw_value: Any, path: str) -> Optional[Dict[str, Any]]:
    if raw_value is None:
        return None
    if isinstance(raw_value, (dict, list)):
        return None
    ref_key = None
    ref_id = None
    if isinstance(raw_value, str):
        if _looks_like_ref_key(raw_value):
            ref_key = raw_value
        else:
            ref_id = raw_value
    else:
        ref_id = str(raw_value)
    return {
        "ref_type": ref_type,
        "ref_id": ref_id,
        "ref_key": ref_key,
        "spec_path": path,
    }


def _looks_like_ref_key(value: str) -> bool:
    prefixes = ("tool:", "knowledge:", "model:", "plugin:", "secret:")
    if value.startswith(prefixes):
        return True
    # treat composite refs with ':' as key
    return ":" in value
