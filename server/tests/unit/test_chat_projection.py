"""Unit tests for chat projection builder."""

from app.kernel.projections.chat_projection import build_chat_refs


def test_build_chat_refs_extracts_supported_refs_only():
    spec = {
        "model": {"ref_key": "model:openai:gpt-4"},
        "tool_refs": ["tool:http:demo"],
        "rag": {"knowledge_refs": ["knowledge:kb_1"]},
        "tools": {
            "configs": {
                "auth": {"secret_ref": "secret:demo"},
                "legacy": {"app_ref": "app:legacy-entry"},
            }
        },
    }

    refs = build_chat_refs(spec)
    ref_types = {(ref["ref_type"], ref.get("ref_key") or ref.get("ref_id")) for ref in refs}

    assert ("model", "model:openai:gpt-4") in ref_types
    assert ("tool", "tool:http:demo") in ref_types
    assert ("knowledge", "knowledge:kb_1") in ref_types
    assert ("secret", "secret:demo") in ref_types
    assert all(ref_type != "app" for ref_type, _ in ref_types)
