"""chat_projection

Build chat projections from chat.v1 spec.
"""

from __future__ import annotations

from typing import Any


def build_chat_refs(spec_json: dict[str, Any], *, base_path: str = "$") -> list[dict[str, Any]]:
    """Extract external references from chat spec."""
    refs: list[dict[str, Any]] = []

    model_ref = spec_json.get("model_ref")
    if model_ref:
        refs.append(_build_ref_entry("model", model_ref, f"{base_path}.model_ref"))

    if isinstance(spec_json.get("tool_refs"), list):
        tools = spec_json.get("tool_refs") or []
        for idx, tool in enumerate(tools):
            entry = _build_ref_entry("tool", tool, f"{base_path}.tool_refs[{idx}]")
            if entry:
                refs.append(entry)

    rag = spec_json.get("rag") or {}
    if isinstance(rag, dict):
        knowledge_refs = rag.get("knowledge_refs") or []
        if isinstance(knowledge_refs, list):
            for idx, knowledge in enumerate(knowledge_refs):
                entry = _build_ref_entry("knowledge", knowledge, f"{base_path}.rag.knowledge_refs[{idx}]")
                if entry:
                    refs.append(entry)
        reranker_ref = rag.get("reranker_ref")
        if reranker_ref:
            entry = _build_ref_entry("model", reranker_ref, f"{base_path}.rag.reranker_ref")
            if entry:
                refs.append(entry)

    tool_configs = (spec_json.get("tools") or {}).get("configs") or {}
    refs.extend(_extract_inline_refs(tool_configs, f"{base_path}.tools.configs"))
    return [item for item in refs if item]

def _extract_inline_refs(value: Any, base_path: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, val in value.items():
            path = f"{base_path}.{key}"
            if key in {"tool_ref", "knowledge_ref", "model_ref", "plugin_ref", "secret_id"}:
                ref_type = (
                    "secret"
                    if key == "secret_id"
                    else "knowledge"
                    if key == "knowledge_ref"
                    else key.replace("_ref", "")
                )
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


def _build_ref_entry(ref_type: str, raw_value: Any, path: str) -> dict[str, Any] | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, dict | list):
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
    return ":" in value
