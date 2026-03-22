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
