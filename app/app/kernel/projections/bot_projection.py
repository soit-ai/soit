"""bot_projection

Build bot projections from bot.v1 spec.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.kernel.projections.chat_projection import build_chat_refs


def build_bot_refs(spec_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract external references from bot spec."""
    refs: List[Dict[str, Any]] = []
    chat_spec = spec_json.get("chat") or {}
    if isinstance(chat_spec, dict):
        refs.extend(build_chat_refs(chat_spec, base_path="$.chat"))

    triggers = spec_json.get("triggers") or {}
    refs.extend(_extract_inline_refs(triggers, "$.triggers"))

    channels = spec_json.get("channels") or {}
    refs.extend(_extract_inline_refs(channels, "$.channels"))
    return [item for item in refs if item]


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


def _build_ref_entry(ref_type: str, raw_value: Any, path: str) -> Dict[str, Any] | None:
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
