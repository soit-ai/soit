"""test_agent_service

Unit tests for AgentService with native function calling.
"""

import pytest
from types import SimpleNamespace

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import (
    LLMPort,
    ChatResponse,
    ToolDefinition,
    ToolCall,
    EmbeddingResponse,
    RerankResponse,
)
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.modules.agent.application.service import AgentService
from app.modules.agent.application.schemas import AgentRunRequest, ChatMessageInput
from app.modules.agent.runtime.emitter import CollectingEmitter
from app.adapters.tools.resolver import ToolResolver
from app.adapters.tools.router import RegistryToolRouterPort


class QueueLLMPort(LLMPort):
    """Queue-based LLM stub that supports function calling."""

    def __init__(self, responses):
        self._responses = list(responses)

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        return self._responses.pop(0)

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class StubToolPort(ToolPort):
    """Stub tool port."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    async def invoke(self, tool_ref, parameters, **kwargs):
        self.calls.append((tool_ref, parameters))
        return self.response


class StubMemoryService:
    """Stub memory service."""

    def __init__(self, summary: str):
        self.summary = summary
        self.queries = []

    async def query_memory(self, data, run_id=None):
        self.queries.append(data)
        memory = SimpleNamespace(content_summary=self.summary, content={"text": self.summary})
        return [SimpleNamespace(memory=memory, score=0.9)]


def _make_stub_resolver(tool_port=None):
    """Create a ToolResolver with a stub router."""
    router = tool_port if isinstance(tool_port, RegistryToolRouterPort) else RegistryToolRouterPort()
    return ToolResolver(tool_port=router)


@pytest.mark.asyncio
async def test_agent_run_with_tool_success(db, ctx):
    """Agent calls tool via function calling then responds."""
    tc = ToolCall(id="call_1", name="tool:test:echo", arguments={"value": "hi"})
    llm_port = QueueLLMPort([
        # Plan step 1: call tool
        ChatResponse(text=None, tokens_prompt=1, tokens_completion=1, finish_reason="tool_calls", tool_calls=[tc]),
        # Plan step 2: respond
        ChatResponse(text="ok", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
        # Verify step
        ChatResponse(text=None, tokens_prompt=1, tokens_completion=1, finish_reason="tool_calls",
                     tool_calls=[ToolCall(id="call_v", name="verify_response", arguments={"ok": True})]),
    ])
    tool_port = StubToolPort(ToolResponse(result="done"))
    resolver = _make_stub_resolver()
    service = AgentService(
        db=db, ctx=ctx, llm_port=llm_port, tool_port=tool_port,
        tool_resolver=resolver,
    )

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
        tool_refs=["tool:test:echo"],
    )
    result = await service.run(request)

    assert result["output"] == "ok"
    assert result["tool_calls"] == 1
    assert result["llm_calls"] == 3
    assert tool_port.calls[0] == ("tool:test:echo", {"value": "hi"})


@pytest.mark.asyncio
async def test_agent_respects_tool_budget(db, ctx):
    """Agent stops when tool budget exceeded."""
    tc = ToolCall(id="call_1", name="tool:test:echo", arguments={"value": "hi"})
    llm_port = QueueLLMPort([
        ChatResponse(text=None, tokens_prompt=1, tokens_completion=1, finish_reason="tool_calls", tool_calls=[tc]),
    ])
    tool_port = StubToolPort(ToolResponse(result="done"))
    resolver = _make_stub_resolver()
    service = AgentService(
        db=db, ctx=ctx, llm_port=llm_port, tool_port=tool_port,
        tool_resolver=resolver,
    )

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
        tool_refs=["tool:test:echo"],
        max_tool_calls=0,
    )
    result = await service.run(request)

    assert result["budget_exceeded"] is True
    assert result["budget_reason"] == "tool_budget_exceeded"


@pytest.mark.asyncio
async def test_agent_emits_events(db, ctx):
    """EventEmitter receives lifecycle events."""
    llm_port = QueueLLMPort([
        ChatResponse(text="done", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    tool_port = StubToolPort(ToolResponse(result="done"))
    resolver = _make_stub_resolver()
    emitter = CollectingEmitter()
    service = AgentService(
        db=db, ctx=ctx, llm_port=llm_port, tool_port=tool_port,
        tool_resolver=resolver,
    )

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
        verify=False,
    )
    await service.run(request, event_emitter=emitter)

    event_names = [e[0] for e in emitter.events]
    assert "agent.run.started" in event_names
    assert "agent.plan.started" in event_names
    assert "agent.plan.completed" in event_names
    assert "agent.response.completed" in event_names
    assert "agent.run.completed" in event_names


@pytest.mark.asyncio
async def test_agent_cost_budget(db, ctx, monkeypatch):
    """Agent stops when cost budget exceeded."""
    llm_port = QueueLLMPort([
        ChatResponse(text="ok", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    tool_port = StubToolPort(ToolResponse(result="done"))
    resolver = _make_stub_resolver()
    service = AgentService(
        db=db, ctx=ctx, llm_port=llm_port, tool_port=tool_port,
        tool_resolver=resolver,
    )
    monkeypatch.setattr(service, "_get_cost_total", lambda run_id, currency: 10.0)

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
        max_cost=1.0,
        verify=False,
    )
    result = await service.run(request)

    assert result["budget_exceeded"] is True
    assert result["budget_reason"] == "cost_budget_exceeded"
