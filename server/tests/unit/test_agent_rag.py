"""Tests for Agent RAG integration."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.adapters.tools.router import RegistryToolRouterPort
from app.kernel.ports.llm.interface import (
    ChatResponse,
    LLMPort,
)
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.db.models.runs import RunStep
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.tools.resolver import ToolResolver
from app.modules.agent.application.schemas import AgentRuntimeRequest, ChatMessageInput
from app.modules.agent.application.service import AgentService


class QueueLLMPort(LLMPort):
    def __init__(self, responses):
        self._responses = list(responses)

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        return self._responses.pop(0)

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class StubToolPort(ToolPort):
    async def invoke(self, tool_ref, parameters, **kwargs):
        return ToolResponse(result="done")


def _make_resolver():
    return ToolResolver(tool_port=RegistryToolRouterPort())


def _runtime_request(**kwargs):
    defaults = {
        "messages": [ChatMessageInput(role="user", content="Hello")],
        "model_ref": "model:test:primary",
    }
    defaults.update(kwargs)
    return AgentRuntimeRequest(**defaults)


@pytest.mark.asyncio
async def test_rag_system_message_strategy(db, ctx):
    """RAG context is prepended as system message when strategy is system_message."""
    captured_messages = []

    class CaptureLLMPort(QueueLLMPort):
        async def chat(self, messages, model, **kwargs):
            captured_messages.extend(messages)
            return await super().chat(messages, model, **kwargs)

    llm_port = CaptureLLMPort([
        ChatResponse(text="rag answer", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    service = AgentService(
        db=db, ctx=ctx, llm_port=llm_port, tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(db, ctx),
    )

    expected_citation = {
        "knowledge_id": "kb_support",
        "document_id": "doc_refund",
        "chunk_id": "chunk_refund_1",
        "rank": 1,
        "score": 0.8,
        "doc_key": "refund-policy.md",
        "title": "Refund Policy",
        "source_uri": "s3://kb/refund-policy.md",
        "chunk_no": 2,
        "snippet": "Refund tickets require account verification.",
    }
    mock_knowledge_query = AsyncMock(return_value={
        "results": [
            {"text": "Document chunk 1", "score": 0.8},
            {"text": "Document chunk 2", "score": 0.6},
        ],
        "citations": [expected_citation],
    })

    request = _runtime_request(
        messages=[ChatMessageInput(role="user", content="What is X?")],
        knowledge_refs=["knowledge:kb_support"],
        rag_strategy="system_message",
        rag_top_k=3,
        verify=False,
    )

    with patch("app.modules.knowledge.runtime.tool_entrypoint.knowledge_query", mock_knowledge_query):
        result = await service.run(request)

    assert result["output"] == "rag answer"
    # Check that RAG context was injected as system message
    system_msgs = [m for m in captured_messages if m.role == "system"]
    assert any("Retrieved context:" in (m.content or "") for m in system_msgs)
    assert any("Document chunk 1" in (m.content or "") for m in system_msgs)

    # Verify knowledge_query was called
    mock_knowledge_query.assert_called_once()
    call_kwargs = mock_knowledge_query.call_args
    assert call_kwargs[1]["knowledge_id"] == "kb_support"
    assert call_kwargs[1]["top_k"] == 3
    retrieval_step = db.execute(
        select(RunStep).where(RunStep.step_type == "retrieval", RunStep.step_id == "rag:kb_support")
    ).scalars().one()
    assert retrieval_step.status == "succeeded"
    assert retrieval_step.metrics_json["knowledge_id"] == "kb_support"
    assert retrieval_step.metrics_json["result_count"] == 2
    assert retrieval_step.metrics_json["citation_count"] == 1
    assert retrieval_step.metrics_json["avg_score"] == pytest.approx(0.7)
    assert result["citations"] == [expected_citation]


@pytest.mark.asyncio
async def test_rag_citation_inherits_source_metadata_from_matching_result(db, ctx):
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=QueueLLMPort([]),
        tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(db, ctx),
    )
    mock_knowledge_query = AsyncMock(
        return_value={
            "results": [
                {
                    "chunk_id": "chunk_ops_1",
                    "document_id": "doc_ops",
                    "text": "Operations guidance",
                    "score": 0.91,
                    "metadata": {
                        "title": "Operations Manual",
                        "doc_key": "operations.pdf",
                        "source_uri": "s3://kb/operations.pdf",
                    },
                }
            ],
            "citations": [
                {
                    "chunk_id": "chunk_ops_1",
                    "document_id": "doc_ops",
                    "rank": 1,
                    "score": 0.91,
                }
            ],
        }
    )

    with patch(
        "app.modules.knowledge.runtime.tool_entrypoint.knowledge_query",
        mock_knowledge_query,
    ):
        _, citations = await service._retrieve_rag_context(
            ["knowledge:kb_ops"],
            "How do I operate this?",
        )

    assert citations == [
        {
            "chunk_id": "chunk_ops_1",
            "document_id": "doc_ops",
            "rank": 1,
            "score": 0.91,
            "knowledge_id": "kb_ops",
            "title": "Operations Manual",
            "doc_key": "operations.pdf",
            "source_uri": "s3://kb/operations.pdf",
        }
    ]


@pytest.mark.asyncio
async def test_rag_planner_context_strategy(db, ctx):
    """RAG context is passed to planner when strategy is planner_context."""
    captured_messages = []

    class CaptureLLMPort(QueueLLMPort):
        async def chat(self, messages, model, **kwargs):
            captured_messages.extend(messages)
            return await super().chat(messages, model, **kwargs)

    llm_port = CaptureLLMPort([
        ChatResponse(text="planner rag answer", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    service = AgentService(
        db=db, ctx=ctx, llm_port=llm_port, tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(db, ctx),
    )

    mock_knowledge_query = AsyncMock(return_value={
        "results": [{"text": "Planner chunk"}],
    })

    request = _runtime_request(
        messages=[ChatMessageInput(role="user", content="What is Y?")],
        knowledge_refs=["knowledge:kb_docs"],
        rag_strategy="planner_context",
        verify=False,
    )

    with patch("app.modules.knowledge.runtime.tool_entrypoint.knowledge_query", mock_knowledge_query):
        result = await service.run(request)

    assert result["output"] == "planner rag answer"
    # In planner_context mode, the context goes through planner's rag_context param
    # which prepends a system message with "Retrieved knowledge context:"
    system_msgs = [m for m in captured_messages if m.role == "system"]
    assert any("Retrieved knowledge context:" in (m.content or "") for m in system_msgs)
    assert any("Planner chunk" in (m.content or "") for m in system_msgs)


@pytest.mark.asyncio
async def test_rag_no_knowledge_refs_skips_retrieval(db, ctx):
    """No RAG retrieval when knowledge_refs is empty."""
    llm_port = QueueLLMPort([
        ChatResponse(text="no rag", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    service = AgentService(
        db=db, ctx=ctx, llm_port=llm_port, tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(db, ctx),
    )

    request = _runtime_request(
        messages=[ChatMessageInput(role="user", content="Hello")],
        verify=False,
    )

    # No patching needed - knowledge_query should never be called
    result = await service.run(request)
    assert result["output"] == "no rag"


@pytest.mark.asyncio
async def test_rag_retrieval_failure_graceful(db, ctx):
    """RAG retrieval failure is handled gracefully without stopping the agent."""
    llm_port = QueueLLMPort([
        ChatResponse(text="fallback", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    service = AgentService(
        db=db, ctx=ctx, llm_port=llm_port, tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(db, ctx),
    )

    mock_knowledge_query = AsyncMock(side_effect=Exception("DB error"))

    request = _runtime_request(
        messages=[ChatMessageInput(role="user", content="Failing RAG")],
        knowledge_refs=["knowledge:broken_kb"],
        verify=False,
    )

    with patch("app.modules.knowledge.runtime.tool_entrypoint.knowledge_query", mock_knowledge_query):
        result = await service.run(request)

    # Agent should still produce output despite RAG failure
    assert result["output"] == "fallback"
    retrieval_step = db.execute(
        select(RunStep).where(RunStep.step_type == "retrieval", RunStep.step_id == "rag:broken_kb")
    ).scalars().one()
    assert retrieval_step.status == "failed"
    assert retrieval_step.metrics_json["knowledge_id"] == "broken_kb"
    assert retrieval_step.metrics_json["result_count"] == 0
    assert retrieval_step.error_code == "rag_retrieval_failed"
