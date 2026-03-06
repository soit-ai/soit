"""test_chat_bot_ref_extractors

Unit tests for chat/bot ref extraction.
"""

from app.kernel.projections.chat_projection import build_chat_refs
from app.kernel.projections.bot_projection import build_bot_refs


def test_build_chat_refs_extracts_model_tool_dataset_and_secret():
    spec = {
        "runtime": "chat_runtime_v1",
        "model": {"ref_key": "model:openai:gpt-4"},
        "tools": {
            "allowlist": ["tool:http:demo"],
            "configs": {"auth": {"secret_ref": "secret:demo"}},
        },
        "rag": {
            "datasets": ["ds:dataset_1"],
            "reranker_ref": "model:openai:rerank-1",
        },
    }
    refs = build_chat_refs(spec)
    types = {(ref.get("ref_type"), ref.get("ref_key"), ref.get("ref_id")) for ref in refs}
    assert ("model", "model:openai:gpt-4", None) in types
    assert ("tool", "tool:http:demo", None) in types
    assert ("dataset", "ds:dataset_1", None) in types
    assert ("model", "model:openai:rerank-1", None) in types
    assert ("secret", "secret:demo", None) in types


def test_build_bot_refs_includes_chat_and_trigger_refs():
    spec = {
        "runtime": "bot_runtime_v1",
        "chat": {
            "runtime": "chat_runtime_v1",
            "model": {"ref_key": "model:openai:gpt-4"},
        },
        "triggers": {"webhook": {"secret_ref": "secret:webhook"}},
        "channels": {"slack": {"secret_ref": "secret:slack"}},
    }
    refs = build_bot_refs(spec)
    types = {(ref.get("ref_type"), ref.get("ref_key")) for ref in refs}
    assert ("model", "model:openai:gpt-4") in types
    assert ("secret", "secret:webhook") in types
    assert ("secret", "secret:slack") in types
