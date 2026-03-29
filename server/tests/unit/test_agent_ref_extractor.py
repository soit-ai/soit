"""test_agent_ref_extractor

Unit tests for agent ref extraction.
"""

from app.kernel.projections.agent_projection import build_agent_refs


def test_build_agent_refs_extracts_model_tool_and_secret():
    spec = {
        "runtime": "agent_runtime_v1",
        "model": {"ref_key": "model:openai:gpt-4"},
        "tools": {
            "allowlist": ["tool:http:demo"],
            "configs": {"auth": {"secret_ref": "secret:demo"}},
        },
        "rag": {"knowledges": ["knowledge:kb_1"]},
    }
    refs = build_agent_refs(spec)
    types = {(ref.get("ref_type"), ref.get("ref_key"), ref.get("ref_id")) for ref in refs}
    assert ("model", "model:openai:gpt-4", None) in types
    assert ("tool", "tool:http:demo", None) in types
    assert ("knowledge", "knowledge:kb_1", None) in types
    assert ("secret", "secret:demo", None) in types


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
        "model": {"ref_key": "model:openai:gpt-4"},
        "bindings": {
            "workflow_refs": ["wf:handoff"],
            "skill_refs": ["skill:triage"],
            "plugin_refs": ["plugin:soit:search:1.0.0"],
        },
    }

    refs = build_agent_refs(spec)
    ref_types = {(ref["ref_type"], ref.get("ref_key") or ref.get("ref_id")) for ref in refs}

    assert ("workflow", "wf:handoff") in ref_types
    assert ("skill", "skill:triage") in ref_types
    assert ("plugin", "plugin:soit:search:1.0.0") in ref_types
