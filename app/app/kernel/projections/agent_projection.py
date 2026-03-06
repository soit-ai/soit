"""agent_projection

Build agent projections from agent.v1 spec.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_agent_refs(spec_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract external references from agent spec."""
    refs: List[Dict[str, Any]] = []
    model_ref = _resolve_model_ref(spec_json)
    if model_ref:
        refs.append(_build_ref_entry("model", model_ref, "$.model"))

    tools = (spec_json.get("tools") or {}).get("allowlist") or []
    if isinstance(tools, list):
        for idx, tool in enumerate(tools):
            entry = _build_ref_entry("tool", tool, f"$.tools.allowlist[{idx}]")
            if entry:
                refs.append(entry)

    rag = spec_json.get("rag") or {}
    if isinstance(rag, dict):
        dataset_ids = rag.get("dataset_ids") or rag.get("datasets") or []
        if isinstance(dataset_ids, list):
            for idx, dataset in enumerate(dataset_ids):
                entry = _build_ref_entry("dataset", dataset, f"$.rag.dataset_ids[{idx}]")
                if entry:
                    refs.append(entry)
        reranker_ref = rag.get("reranker_ref")
        if reranker_ref:
            entry = _build_ref_entry("model", reranker_ref, "$.rag.reranker_ref")
            if entry:
                refs.append(entry)

    tool_configs = (spec_json.get("tools") or {}).get("configs") or {}
    refs.extend(_extract_inline_refs(tool_configs, "$.tools.configs"))
    planner = spec_json.get("planner") or {}
    refs.extend(_extract_inline_refs(planner, "$.planner"))
    memory = spec_json.get("memory") or {}
    refs.extend(_extract_inline_refs(memory, "$.memory"))
    policies = spec_json.get("policies") or {}
    refs.extend(_extract_inline_refs(policies, "$.policies"))
    return [item for item in refs if item]


def _resolve_model_ref(spec_json: Dict[str, Any]) -> Optional[str]:
    model_ref = spec_json.get("model_ref")
    model = spec_json.get("model")
    if model_ref:
        return model_ref
    if isinstance(model, str):
        return model
    if isinstance(model, dict):
        if model.get("ref_key"):
            return model.get("ref_key")
        provider = model.get("provider")
        model_name = model.get("model")
        if provider and model_name:
            return f"model:{provider}:{model_name}"
    return None


def _extract_inline_refs(value: Any, base_path: str) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    if isinstance(value, dict):
        for key, val in value.items():
            path = f"{base_path}.{key}"
            if key in {"tool_ref", "dataset_ref", "model_ref", "plugin_ref", "secret_ref", "app_ref"}:
                ref_type = key.replace("_ref", "")
                entry = _build_ref_entry(ref_type, val, path)
                if entry:
                    refs.append(entry)
                continue
            refs.extend(_extract_inline_refs(val, path))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            path = f"{base_path}[{idx}]"
            refs.extend(_extract_inline_refs(item, path))
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
    prefixes = ("tool:", "dataset:", "ds:", "model:", "plugin:", "secret:", "app:")
    if value.startswith(prefixes):
        return True
    return ":" in value
