"""Unit tests for chat projection builder."""

from app.kernel.projections.chat_projection import build_chat_refs


def test_build_chat_refs_extracts_supported_refs_only():
    spec = {
        "model_ref": "model:openai:gpt-4",
        "tool_refs": ["tool:http:demo"],
        "rag": {"knowledge_refs": ["knowledge:kb_1"]},
        "tools": {
            "configs": {
                "auth": {"secret_id": "sec_demo"},
                "legacy": {"app_ref": "app:legacy-entry"},
            }
        },
    }

    refs = build_chat_refs(spec)
    ref_types = {(ref["ref_type"], ref.get("ref_key") or ref.get("ref_id")) for ref in refs}

    assert ("model", "model:openai:gpt-4") in ref_types
    assert ("tool", "tool:http:demo") in ref_types
    assert ("knowledge", "knowledge:kb_1") in ref_types
    assert ("secret", "sec_demo") in ref_types
    assert all(ref_type != "app" for ref_type, _ in ref_types)


def test_build_chat_refs_ignores_legacy_binding_fields():
    spec = {
        "model": {"ref_key": "model:openai:gpt-legacy"},
        "model_ref": "model:openai:gpt-current",
        "tools": {"allowlist": ["tool:http:legacy"]},
        "tool_refs": ["tool:http:current"],
        "rag": {
            "knowledge_ids": ["knowledge:legacy-id"],
            "knowledges": ["knowledge:legacy-name"],
            "knowledge_refs": ["knowledge:current"],
        },
    }

    refs = build_chat_refs(spec)
    ref_keys = {ref.get("ref_key") for ref in refs}

    assert "model:openai:gpt-current" in ref_keys
    assert "tool:http:current" in ref_keys
    assert "knowledge:current" in ref_keys
    assert "model:openai:gpt-legacy" not in ref_keys
    assert "tool:http:legacy" not in ref_keys
    assert "knowledge:legacy-id" not in ref_keys
    assert "knowledge:legacy-name" not in ref_keys
