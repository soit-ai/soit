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
from app.kernel.runtime.db.models.runs import Run, RunStep
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
async def test_rag_system_message_strategy(async_db, ctx):
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
        db=async_db, ctx=ctx, llm_port=llm_port, tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(async_db, ctx),
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
    # Retrieval runs under the agent's own request context, roles and all.
    assert call_kwargs[1]["ctx"] is service.ctx
    retrieval_step = (await async_db.execute(
        select(RunStep).where(RunStep.step_type == "retrieval", RunStep.step_id == "rag:kb_support")
    )).scalars().one()
    assert retrieval_step.status == "succeeded"
    assert retrieval_step.metrics_json["knowledge_id"] == "kb_support"
    assert retrieval_step.metrics_json["result_count"] == 2
    assert retrieval_step.metrics_json["citation_count"] == 1
    assert retrieval_step.metrics_json["avg_score"] == pytest.approx(0.7)
    assert result["citations"] == [expected_citation]


@pytest.mark.asyncio
async def test_rag_citation_inherits_source_metadata_from_matching_result(async_db, ctx):
    service = AgentService(
        db=async_db,
        ctx=ctx,
        llm_port=QueueLLMPort([]),
        tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(async_db, ctx),
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
async def test_rag_planner_context_strategy(async_db, ctx):
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
        db=async_db, ctx=ctx, llm_port=llm_port, tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(async_db, ctx),
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
async def test_rag_no_knowledge_refs_skips_retrieval(async_db, ctx):
    """No RAG retrieval when knowledge_refs is empty."""
    llm_port = QueueLLMPort([
        ChatResponse(text="no rag", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    service = AgentService(
        db=async_db, ctx=ctx, llm_port=llm_port, tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(async_db, ctx),
    )

    request = _runtime_request(
        messages=[ChatMessageInput(role="user", content="Hello")],
        verify=False,
    )

    # No patching needed - knowledge_query should never be called
    result = await service.run(request)
    assert result["output"] == "no rag"


@pytest.mark.asyncio
async def test_rag_retrieval_failure_graceful(async_db, ctx):
    """RAG retrieval failure is handled gracefully without stopping the agent."""
    llm_port = QueueLLMPort([
        ChatResponse(text="fallback", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    service = AgentService(
        db=async_db, ctx=ctx, llm_port=llm_port, tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(async_db, ctx),
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
    retrieval_step = (await async_db.execute(
        select(RunStep).where(RunStep.step_type == "retrieval", RunStep.step_id == "rag:broken_kb")
    )).scalars().one()
    assert retrieval_step.status == "failed"
    assert retrieval_step.metrics_json["knowledge_id"] == "broken_kb"
    assert retrieval_step.metrics_json["result_count"] == 0
    assert retrieval_step.error_code == "rag_retrieval_failed"


@pytest.mark.asyncio
async def test_a_spend_refusal_in_retrieval_ends_the_run_with_it(async_db, ctx):
    from app.kernel.commons.errors import BudgetExhaustedError

    llm_port = QueueLLMPort([
        ChatResponse(text="never used", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    service = AgentService(
        db=async_db, ctx=ctx, llm_port=llm_port, tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(async_db, ctx),
    )
    refusing = AsyncMock(side_effect=BudgetExhaustedError("Budget exhausted", {"budget_id": "bud_1"}))
    request = _runtime_request(
        messages=[ChatMessageInput(role="user", content="Spent")],
        knowledge_refs=["knowledge:kb_support"],
        verify=False,
    )

    with patch("app.modules.knowledge.runtime.tool_entrypoint.knowledge_query", refusing):
        with pytest.raises(BudgetExhaustedError):
            await service.run(request)

    retrieval_step = (await async_db.execute(
        select(RunStep).where(RunStep.step_type == "retrieval", RunStep.step_id == "rag:kb_support")
    )).scalars().one()
    assert (retrieval_step.status, retrieval_step.error_code) == ("failed", "BUDGET_EXHAUSTED")
    # The run itself is closed with the refusal, not left running.
    run = await async_db.get(Run, retrieval_step.run_id)
    await async_db.refresh(run)
    assert (run.status, run.error_code) == ("failed", "BUDGET_EXHAUSTED")


@pytest.mark.asyncio
async def test_a_policy_refusal_in_retrieval_shows_on_its_step(async_db, ctx):
    from app.kernel.commons.errors import ForbiddenError

    llm_port = QueueLLMPort([
        ChatResponse(text="answered without it", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    service = AgentService(
        db=async_db, ctx=ctx, llm_port=llm_port, tool_port=StubToolPort(),
        tool_resolver=_make_resolver(),
        trace_writer=TraceWriter(async_db, ctx),
    )
    refusing = AsyncMock(side_effect=ForbiddenError("This API key may not use this model", {"reason": "model_not_allowed"}))
    request = _runtime_request(
        messages=[ChatMessageInput(role="user", content="Not allowed")],
        knowledge_refs=["knowledge:kb_support"],
        verify=False,
    )

    with patch("app.modules.knowledge.runtime.tool_entrypoint.knowledge_query", refusing):
        result = await service.run(request)

    assert result["output"] == "answered without it"
    retrieval_step = (await async_db.execute(
        select(RunStep).where(RunStep.step_type == "retrieval", RunStep.step_id == "rag:kb_support")
    )).scalars().one()
    assert retrieval_step.error_code == "FORBIDDEN"
    assert retrieval_step.error_message == "This API key may not use this model"
