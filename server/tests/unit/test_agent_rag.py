"""Tests for Agent RAG integration."""

import pytest
from unittest.mock import AsyncMock, patch

from app.kernel.ports.llm.interface import (
    LLMPort,
    ChatResponse,
    ToolCall,
)
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.modules.agent.application.service import AgentService
from app.modules.agent.application.schemas import AgentRunRequest, ChatMessageInput
from app.adapters.tools.resolver import ToolResolver
from app.adapters.tools.router import RegistryToolRouterPort


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
    )

    mock_knowledge_query = AsyncMock(return_value={
        "results": [
            {"text": "Document chunk 1"},
            {"text": "Document chunk 2"},
        ],
    })

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="What is X?")],
        knowledge_refs=["knowledge:kb_support"],
        rag_strategy="system_message",
        rag_top_k=3,
        verify=False,
    )

    with patch("app.modules.knowledge.application.tools.knowledge_query", mock_knowledge_query):
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
    )

    mock_knowledge_query = AsyncMock(return_value={
        "results": [{"text": "Planner chunk"}],
    })

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="What is Y?")],
        knowledge_refs=["knowledge:kb_docs"],
        rag_strategy="planner_context",
        verify=False,
    )

    with patch("app.modules.knowledge.application.tools.knowledge_query", mock_knowledge_query):
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
    )

    request = AgentRunRequest(
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
    )

    mock_knowledge_query = AsyncMock(side_effect=Exception("DB error"))

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Failing RAG")],
        knowledge_refs=["knowledge:broken_kb"],
        verify=False,
    )

    with patch("app.modules.knowledge.application.tools.knowledge_query", mock_knowledge_query):
        result = await service.run(request)

    # Agent should still produce output despite RAG failure
    assert result["output"] == "fallback"
