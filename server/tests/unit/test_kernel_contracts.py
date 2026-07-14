"""Unit tests for additive kernel contract dataclasses."""

from __future__ import annotations

from app.kernel.contracts.refs import KnowledgeRef, ModelRef, PluginRef, ToolRef
from app.kernel.contracts.tool_call import (
    ToolCallError,
    ToolCallRequest,
    ToolCallResult,
)
from app.kernel.contracts.vector import VectorDocument, VectorQuery, VectorQueryMatch


def test_ref_contracts_parse_provider_name_and_version():
    model_ref = ModelRef.parse("model:openai:gpt-5.1")
    tool_ref = ToolRef.parse("tool:http:fetch")
    plugin_ref = PluginRef.parse("plugin:acme:slack:1.2.0")
    knowledge_ref = KnowledgeRef.parse("knowledge:kb-1")

    assert model_ref.kind == "model"
    assert model_ref.provider == "openai"
    assert model_ref.name == "gpt-5.1"
    assert model_ref.version is None
    assert tool_ref.provider == "http"
    assert tool_ref.name == "fetch"
    assert plugin_ref.provider == "acme"
    assert plugin_ref.name == "slack"
    assert plugin_ref.version == "1.2.0"
    assert knowledge_ref.provider is None
    assert knowledge_ref.name == "kb-1"


def test_tool_call_contracts_round_trip_as_plain_data():
    request = ToolCallRequest(
        id="call-1",
        tool_ref="tool:http:fetch",
        arguments={"url": "https://example.com"},
        run_id="run-1",
    )
    result = ToolCallResult(
        id=request.id,
        tool_ref=request.tool_ref,
        success=False,
        error=ToolCallError(code="HTTP_500", message="upstream failed"),
    )

    request_data = request.to_dict()
    result_data = result.to_dict()

    assert request_data["arguments"]["url"] == "https://example.com"
    assert result_data["error"]["code"] == "HTTP_500"
    assert ToolCallRequest.from_dict(request_data) == request
    assert ToolCallResult.from_dict(result_data) == result


def test_vector_contracts_round_trip_as_plain_data():
    query = VectorQuery(
        collection="knowledge",
        vector=[0.1, 0.2],
        top_k=3,
        filter={"tenant_id": "tenant-1"},
    )
    match = VectorQueryMatch(
        document=VectorDocument(id="doc-1", text="hello", metadata={"source": "unit"}),
        score=0.9,
    )

    query_data = query.to_dict()
    match_data = match.to_dict()

    assert query_data["top_k"] == 3
    assert match_data["document"]["metadata"]["source"] == "unit"
    assert VectorQuery.from_dict(query_data) == query
    assert VectorQueryMatch.from_dict(match_data) == match


def test_ref_contracts_round_trip_as_dicts():
    ref = ModelRef.parse("model:openai:gpt-5.1:stable")
    data = ref.to_dict()

    assert data == {
        "raw": "model:openai:gpt-5.1:stable",
        "kind": "model",
        "provider": "openai",
        "name": "gpt-5.1",
        "version": "stable",
    }
    assert ModelRef.from_dict(data) == ref
