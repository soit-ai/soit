"""test_agent_service

Unit tests for AgentService with native function calling.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.adapters.tools.router import RegistryToolRouterPort
from app.kernel.ports.llm.interface import (
    ChatResponse,
    LLMPort,
    ToolCall,
)
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.registry.deps import get_registry
from app.kernel.runtime.db.models.runs import RunCostEntry
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.tools.resolver import ToolResolver
from app.modules.agent.application.schemas import (
    AgentRunRequest,
    AgentRuntimeRequest,
    ChatMessageInput,
)
from app.modules.agent.application.service import AgentService
from app.modules.agent.runtime.emitter import CollectingEmitter


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


def _runtime_request(**kwargs):
    defaults = {
        "messages": [ChatMessageInput(role="user", content="Hello")],
        "model_ref": "model:test:primary",
    }
    defaults.update(kwargs)
    return AgentRuntimeRequest(**defaults)


@pytest.mark.asyncio
async def test_agent_service_rejects_public_run_request(db, ctx):
    """AgentService uses resolved runtime requests, not public API payloads."""
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=QueueLLMPort([]),
        tool_port=StubToolPort(ToolResponse(result="done")),
    )

    request = AgentRunRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
    )

    with pytest.raises(TypeError, match="AgentRuntimeRequest"):
        await service.run(request)  # type: ignore[arg-type]


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

    request = _runtime_request(tool_refs=["tool:test:echo"])
    result = await service.run(request)

    assert result["output"] == "ok"
    assert result["tool_calls"] == 1
    assert result["llm_calls"] == 3
    assert tool_port.calls[0] == ("tool:test:echo", {"value": "hi"})


@pytest.mark.asyncio
async def test_agent_run_executes_plugin_exported_tool_ref(db, ctx):
    """Agent executes plugin-exported tools through explicit tool_refs."""
    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="tool:http:health_check",
        version="0.1.0",
        payload={
            "tool_spec": {
                "name": "health_check",
                "description": "Call plugin health endpoint.",
                "input_schema": {"type": "object", "properties": {}},
                "output_schema": {"type": "object"},
            },
            "plugin": {"name": "soit-plugin-health", "version": "0.1.0"},
        },
    )
    tc = ToolCall(id="call_1", name="tool:http:health_check", arguments={})
    llm_port = QueueLLMPort([
        ChatResponse(text=None, tokens_prompt=1, tokens_completion=1, finish_reason="tool_calls", tool_calls=[tc]),
        ChatResponse(text="plugin ok", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    tool_port = StubToolPort(ToolResponse(result={"ok": True}))
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        tool_resolver=_make_stub_resolver(),
    )

    result = await service.run(_runtime_request(tool_refs=["tool:http:health_check"], verify=False))

    assert result["output"] == "plugin ok"
    assert result["tool_calls"] == 1
    assert tool_port.calls[0] == ("tool:http:health_check", {})


@pytest.mark.asyncio
async def test_agent_tool_details_use_plugin_source_kind(db, ctx):
    """Agent records plugin-exported tool calls as plugin tool type."""
    tc = ToolCall(id="call_1", name="tool:http:plugin_echo", arguments={"value": "hi"})
    llm_port = QueueLLMPort([
        ChatResponse(text=None, tokens_prompt=1, tokens_completion=1, finish_reason="tool_calls", tool_calls=[tc]),
        ChatResponse(text="plugin ok", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
    ])
    tool_port = StubToolPort(
        ToolResponse(
            result={"ok": True},
            metadata={
                "source_kind": "plugin",
                "adapter": "plugin",
                "plugin_name": "demo-plugin",
                "plugin_version": "1.0.0",
                "tool_ref": "tool:http:plugin_echo",
            },
        )
    )
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        tool_resolver=_make_stub_resolver(),
    )

    result = await service.run(_runtime_request(tool_refs=["tool:http:plugin_echo"], verify=False))

    assert result["tool_call_details"][0]["tool_type"] == "plugin"
    assert result["tool_call_details"][0]["metadata_json"]["plugin_name"] == "demo-plugin"


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

    request = _runtime_request(
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

    request = _runtime_request(
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

    request = _runtime_request(
        max_cost=1.0,
        verify=False,
    )
    result = await service.run(request)

    assert result["budget_exceeded"] is True
    assert result["budget_reason"] == "cost_budget_exceeded"


@pytest.mark.asyncio
async def test_agent_does_not_duplicate_llm_policy_cost_entries(db, ctx):
    """Agent fallback cost recording should not duplicate entries from an LLM policy port."""

    class PolicyRecordingLLMPort(QueueLLMPort):
        async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
            response = await super().chat(
                messages,
                model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                **kwargs,
            )
            trace_writer.record_cost(
                run_id=kwargs["run_id"],
                step_id=None,
                unit="tokens",
                quantity=response.tokens_prompt + response.tokens_completion,
                model_ref=model,
                prompt_tokens=response.tokens_prompt,
                completion_tokens=response.tokens_completion,
                total_tokens=response.tokens_prompt + response.tokens_completion,
            )
            return response

    trace_writer = TraceWriter(db, ctx)
    llm_port = PolicyRecordingLLMPort([
        ChatResponse(text="policy cost", tokens_prompt=2, tokens_completion=3, finish_reason="stop"),
    ])
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=StubToolPort(ToolResponse(result="done")),
        tool_resolver=_make_stub_resolver(),
        trace_writer=trace_writer,
    )

    result = await service.run(_runtime_request(verify=False))

    entries = db.exec(
        select(RunCostEntry).where(RunCostEntry.run_id == result["run_id"], RunCostEntry.unit == "tokens")
    ).all()
    entries = [entry if hasattr(entry, "id") else entry[0] for entry in entries]
    assert len(entries) == 1
    assert entries[0].prompt_tokens == 2
    assert entries[0].completion_tokens == 3
