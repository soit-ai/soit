"""test_agent_service

Unit tests for AgentService.
"""

import pytest
from types import SimpleNamespace

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import LLMPort, ChatResponse
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.modules.agent.application.service import AgentService
from app.modules.agent.application.schemas import AgentRunRequest
from app.modules.chat.application.schemas import ChatMessageInput


class QueueLLMPort(LLMPort):
    """Queue-based LLM stub."""

    def __init__(self, responses):
        self._responses = list(responses)

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        return self._responses.pop(0)

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError("embed not used in agent tests")

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError("rerank not used in agent tests")


class StubToolPort(ToolPort):
    """Stub tool port."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    async def invoke(self, tool_ref, parameters, **kwargs):
        self.calls.append((tool_ref, parameters))
        return self.response


class RecordingLLMPort(LLMPort):
    """LLM stub that records chat messages."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        self.calls.append(messages)
        return self._responses.pop(0)

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError("embed not used in agent tests")

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError("rerank not used in agent tests")


class StubMemoryService:
    """Stub memory service returning a fixed memory summary."""

    def __init__(self, summary: str):
        self.summary = summary
        self.queries = []

    async def query_memory(self, data, run_id=None):
        self.queries.append(data)
        memory = SimpleNamespace(content_summary=self.summary, content={"text": self.summary})
        return [SimpleNamespace(memory=memory, score=0.9)]


@pytest.mark.asyncio
async def test_agent_run_with_tool_success(db, ctx):
    """Agent runs tool then responds."""
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text='{"action":"tool","tool_ref":"tool:test:echo","parameters":{"value":"hi"}}',
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
            ChatResponse(
                text='{"action":"respond","response":"ok"}',
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
            ChatResponse(
                text='{"ok": true, "reason": "ok"}',
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="done"))
    service = AgentService(db=db, ctx=ctx, llm_port=llm_port, tool_port=tool_port)

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
        tool_refs=["tool:test:echo"],
    )
    result = await service.run(request)

    assert result["output"] == "ok"
    assert result["tool_calls"] == 1
    assert result["llm_calls"] == 3
    assert result["budget_exceeded"] is False
    assert tool_port.calls[0][0] == "tool:test:echo"


@pytest.mark.asyncio
async def test_agent_respects_tool_budget(db, ctx):
    """Agent stops when tool budget is exceeded."""
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text='{"action":"tool","tool_ref":"tool:test:echo","parameters":{"value":"hi"}}',
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="done"))
    service = AgentService(db=db, ctx=ctx, llm_port=llm_port, tool_port=tool_port)

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
        tool_refs=["tool:test:echo"],
        max_tool_calls=0,
    )
    result = await service.run(request)

    assert result["budget_exceeded"] is True
    assert result["budget_reason"] == "tool_budget_exceeded"
    assert result["tool_calls"] == 0
    assert "tool_budget_exceeded" in result["output"]


@pytest.mark.asyncio
async def test_agent_cost_budget(db, ctx, monkeypatch):
    """Agent stops when cost budget is exceeded."""
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text='{"action":"respond","response":"ok"}',
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="done"))
    service = AgentService(db=db, ctx=ctx, llm_port=llm_port, tool_port=tool_port)

    monkeypatch.setattr(service, "_get_cost_total", lambda run_id, currency: 10.0)

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
        max_cost=1.0,
        verify=False,
    )
    result = await service.run(request)

    assert result["budget_exceeded"] is True
    assert result["budget_reason"] == "cost_budget_exceeded"
    assert result["cost_total"] == 10.0
    assert "cost_budget_exceeded" in result["output"]


@pytest.mark.asyncio
async def test_agent_memory_strategy_planner_only(db, ctx):
    """Memory context is injected into planner system message."""
    llm_port = RecordingLLMPort(
        [
            ChatResponse(
                text='{"action":"respond","response":"ok"}',
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="done"))
    memory_service = StubMemoryService("remember me")
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        memory_service=memory_service,
    )

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
        memory_strategy="planner_only",
        memory_top_k=3,
        verify=False,
    )
    await service.run(request)

    system_message = llm_port.calls[0][0]
    assert system_message.role == "system"
    assert "Memory context:" in system_message.content
    assert "remember me" in system_message.content
    assert len(llm_port.calls[0]) == 2
    assert memory_service.queries[0].top_k == 3


@pytest.mark.asyncio
async def test_agent_memory_strategy_system_message(db, ctx):
    """Memory context is injected as a system message."""
    llm_port = RecordingLLMPort(
        [
            ChatResponse(
                text='{"action":"respond","response":"ok"}',
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="done"))
    memory_service = StubMemoryService("remember me")
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        memory_service=memory_service,
    )

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
        memory_strategy="system_message",
        verify=False,
    )
    await service.run(request)

    messages = llm_port.calls[0]
    assert messages[0].role == "system"
    assert "Memory context:" not in messages[0].content
    assert messages[1].role == "system"
    assert "Memory context:" in messages[1].content


@pytest.mark.asyncio
async def test_agent_failure_strategy_abort(db, ctx):
    """Abort strategy raises when failures exceed max_failures."""
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text='{"action":"tool"}',
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="done"))
    service = AgentService(db=db, ctx=ctx, llm_port=llm_port, tool_port=tool_port)

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
        max_failures=0,
        failure_strategy="abort",
        verify=False,
    )

    with pytest.raises(ValidationError):
        await service.run(request)


@pytest.mark.asyncio
async def test_agent_context_window_messages(db, ctx):
    """Context window trims to recent messages."""
    llm_port = RecordingLLMPort(
        [
            ChatResponse(
                text='{"action":"respond","response":"ok"}',
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="done"))
    service = AgentService(db=db, ctx=ctx, llm_port=llm_port, tool_port=tool_port)

    request = AgentRunRequest(
        messages=[
            ChatMessageInput(role="user", content="one"),
            ChatMessageInput(role="user", content="two"),
            ChatMessageInput(role="user", content="three"),
        ],
        context_window_messages=1,
        verify=False,
    )
    await service.run(request)

    planner_messages = llm_port.calls[0]
    assert len(planner_messages) == 2
    assert planner_messages[-1].content == "three"


@pytest.mark.asyncio
async def test_agent_context_window_chars(db, ctx):
    """Context window trims by character budget."""
    llm_port = RecordingLLMPort(
        [
            ChatResponse(
                text='{"action":"respond","response":"ok"}',
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="done"))
    service = AgentService(db=db, ctx=ctx, llm_port=llm_port, tool_port=tool_port)

    request = AgentRunRequest(
        messages=[
            ChatMessageInput(role="user", content="hello world"),
            ChatMessageInput(role="user", content="bye"),
        ],
        context_window_chars=5,
        verify=False,
    )
    await service.run(request)

    planner_messages = llm_port.calls[0]
    assert planner_messages[-1].content == "bye"
