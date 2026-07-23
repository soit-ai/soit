"""test_agent_ref_extractor

Unit tests for agent ref extraction.
"""

from app.kernel.projections.agent_projection import build_agent_refs


def test_build_agent_refs_extracts_bindings_and_inline_secret_ids():
    spec = {
        "runtime": "agent_runtime_v1",
        "bindings": {
            "model_ref": "model:openai:gpt-4",
            "knowledge_refs": ["knowledge:kb_1"],
            "tool_refs": ["tool:http:demo"],
        },
        "tools": {
            "configs": {"auth": {"secret_id": "sec_demo"}},
        },
    }
    refs = build_agent_refs(spec)
    types = {(ref.get("ref_type"), ref.get("ref_key"), ref.get("ref_id")) for ref in refs}
    assert ("model", "model:openai:gpt-4", None) in types
    assert ("tool", "tool:http:demo", None) in types
    assert ("knowledge", "knowledge:kb_1", None) in types
    assert ("secret", None, "sec_demo") in types


def test_build_agent_refs_ignores_legacy_binding_fields():
    spec = {
        "runtime": "agent_runtime_v1",
        "model": {"ref_key": "model:openai:gpt-4"},
        "model_ref": "model:openai:gpt-4o",
        "tools": {"allowlist": ["tool:http:legacy"]},
        "rag": {"knowledges": ["knowledge:legacy"]},
        "bindings": {
            "model_ref": "model:openai:gpt-5",
            "knowledge_refs": ["knowledge:current"],
            "tool_refs": ["tool:http:current"],
        },
    }

    refs = build_agent_refs(spec)
    ref_keys = {ref.get("ref_key") for ref in refs}

    assert "model:openai:gpt-5" in ref_keys
    assert "knowledge:current" in ref_keys
    assert "tool:http:current" in ref_keys
    assert "model:openai:gpt-4" not in ref_keys
    assert "model:openai:gpt-4o" not in ref_keys
    assert "tool:http:legacy" not in ref_keys
    assert "knowledge:legacy" not in ref_keys


def test_build_agent_refs_ignores_legacy_app_refs():
    spec = {
        "tools": {
            "configs": {
                "legacy": {
                    "app_ref": "app:legacy-entry",
                }
            }
        }
    }

    refs = build_agent_refs(spec)

    assert refs == []


def test_build_agent_refs_extracts_structured_bindings():
    spec = {
        "runtime": "agent_runtime_v1",
        "bindings": {
            "model_ref": "model:openai:gpt-4",
            "workflow_refs": ["wf:handoff"],
            "skill_refs": ["skill:triage"],
        },
    }

    refs = build_agent_refs(spec)
    ref_types = {(ref["ref_type"], ref.get("ref_key") or ref.get("ref_id")) for ref in refs}

    assert ("workflow", "wf:handoff") in ref_types
    assert ("skill", "skill:triage") in ref_types


def test_build_agent_refs_ignores_removed_plugin_refs_binding():
    spec = {
        "runtime": "agent_runtime_v1",
        "bindings": {
            "model_ref": "model:openai:gpt-4",
            "plugin_refs": ["plugin:soit:search:1.0.0"],
        },
    }

    refs = build_agent_refs(spec)
    ref_types = {(ref["ref_type"], ref.get("ref_key") or ref.get("ref_id")) for ref in refs}

    assert ("model", "model:openai:gpt-4") in ref_types
    assert ("plugin", "plugin:soit:search:1.0.0") not in ref_types
