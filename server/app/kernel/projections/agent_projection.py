"""agent_projection

Build agent projections from agent.v1 spec.
"""

from __future__ import annotations

from typing import Any


def build_agent_refs(spec_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract external references from agent spec."""
    refs: list[dict[str, Any]] = []
    bindings = spec_json.get("bindings") or {}
    if isinstance(bindings, dict):
        model_ref = bindings.get("model_ref")
        if model_ref:
            entry = _build_ref_entry("model", model_ref, "$.bindings.model_ref")
            if entry:
                refs.append(entry)
        binding_lists = [
            ("knowledge", bindings.get("knowledge_refs") or [], "$.bindings.knowledge_refs"),
            ("tool", bindings.get("tool_refs") or [], "$.bindings.tool_refs"),
            ("workflow", bindings.get("workflow_refs") or [], "$.bindings.workflow_refs"),
            ("skill", bindings.get("skill_refs") or [], "$.bindings.skill_refs"),
        ]
        for ref_type, values, base_path in binding_lists:
            if not isinstance(values, list):
                continue
            for idx, raw_value in enumerate(values):
                entry = _build_ref_entry(ref_type, raw_value, f"{base_path}[{idx}]")
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
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for item in refs:
        if not item:
            continue
        key = (item["ref_type"], item.get("ref_key"), item.get("ref_id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped

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
    prefixes = ("tool:", "knowledge:", "model:", "plugin:", "secret:", "wf:", "skill:")
    if value.startswith(prefixes):
        return True
    return ":" in value
