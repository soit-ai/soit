"""test_agent_service

Unit tests for AgentService with native function calling.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.adapters.tools.router import RegistryToolRouterPort
from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    LLMPort,
    ToolCall,
)
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.ports.tools.policy import ToolPolicyGateway
from app.kernel.registry.deps import get_registry
from app.kernel.runtime.db.models.runs import RunCostEntry, RunStep, RunStepToolCall
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.tools.resolver import ToolResolver
from app.modules.agent.application.application_service import AgentApplicationService
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
        self.calls = []

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        self.calls.append(kwargs)
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


def test_agent_application_projects_reasoning_to_durable_outputs():
    service = object.__new__(AgentApplicationService)
    result = {
        "output": "Done.",
        "reasoning": "Checked the evidence.",
        "run_id": "run_reasoning",
    }
    agent = SimpleNamespace(id="agent_reasoning")
    version = SimpleNamespace(id="version_reasoning")

    response_output = service._response_output_payload(result)
    task_output = service._task_output_payload(result, response_id="response_reasoning")
    message_metadata = service._assistant_message_metadata(
        agent,
        version,
        result,
        response_id="response_reasoning",
    )

    assert response_output["reasoning"] == "Checked the evidence."
    assert task_output["reasoning"] == "Checked the evidence."
    assert message_metadata["reasoning"] == "Checked the evidence."


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
        input="Hello",
    )

    with pytest.raises(TypeError, match="AgentRuntimeRequest"):
        await service.run(request)  # type: ignore[arg-type]


def test_agent_context_window_preserves_system_prompt_and_current_input(db, ctx):
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=QueueLLMPort([]),
        tool_port=StubToolPort(ToolResponse(result="done")),
    )
    messages = [
        ChatMessage(role="system", content="Published instructions"),
        ChatMessage(role="user", content="old question"),
        ChatMessage(role="assistant", content="old answer"),
        ChatMessage(role="user", content="current user input"),
    ]

    trimmed = service._apply_context_window(
        messages,
        max_messages=2,
        max_chars=3,
    )

    assert [(message.role, message.content) for message in trimmed] == [
        ("system", "Published instructions"),
        ("user", "current user input"),
    ]


@pytest.mark.asyncio
async def test_agent_run_cooperatively_stops_after_explicit_cancellation(db, ctx):
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="agent",
        subject_kind="agent",
        subject_id="agt_cancel",
        subject_version_id="agtv_cancel",
    )
    trace_writer.update_run_status(run.id, "running")

    class CancelingLLMPort(QueueLLMPort):
        async def chat(self, *args, **kwargs):
            trace_writer.update_run_status(run.id, "canceled")
            return ChatResponse(
                text="must not be returned",
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            )

    emitter = CollectingEmitter()
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=CancelingLLMPort([]),
        tool_port=StubToolPort(ToolResponse(result="done")),
        trace_writer=trace_writer,
    )

    with pytest.raises(KernelError) as exc_info:
        await service.run(
            _runtime_request(verify=False),
            existing_run_id=run.id,
            event_emitter=emitter,
        )

    db.refresh(run)
    assert exc_info.value.code == "AGENT_RUN_CANCELED"
    assert run.status == "canceled"
    assert [event for event, _ in emitter.events].count("agent.run.canceled") == 1
    assert "agent.run.succeeded" not in [event for event, _ in emitter.events]


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
async def test_agent_run_emits_enabled_provider_reasoning(db, ctx):
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text="Done.",
                reasoning="Checked the evidence.",
                tokens_prompt=2,
                tokens_completion=3,
                finish_reason="stop",
            )
        ]
    )
    emitter = CollectingEmitter()
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=StubToolPort(ToolResponse(result="done")),
    )

    result = await service.run(
        _runtime_request(
            verify=False,
            show_reasoning=True,
            reasoning_effort="high",
        ),
        event_emitter=emitter,
    )

    assert result["reasoning"] == "Checked the evidence."
    assert llm_port.calls[0]["reasoning_effort"] == "high"
    assert (
        "agent.reasoning.completed",
        {
            "iteration": 1,
            "content": "Checked the evidence.",
        },
    ) in emitter.events


@pytest.mark.asyncio
async def test_agent_tool_call_uses_one_runtime_step_and_one_control_record(db, ctx):
    tool_call = ToolCall(id="call_stable", name="tool:test:echo", arguments={"value": "first"})
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text=None,
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="tool_calls",
                tool_calls=[tool_call],
            ),
            ChatResponse(text="done", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
        ]
    )
    trace_writer = TraceWriter(db, ctx)
    base_tool_port = StubToolPort(ToolResponse(result={"value": "done"}))
    governed_tool_port = ToolPolicyGateway(
        gateway=base_tool_port,
        ctx=ctx,
        trace_writer=trace_writer,
        enable_egress_check=False,
    )
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=governed_tool_port,
        tool_resolver=_make_stub_resolver(),
        trace_writer=trace_writer,
    )

    result = await service.run(_runtime_request(tool_refs=["tool:test:echo"], verify=False))

    step_rows = db.execute(
        select(RunStep).where(
            RunStep.run_id == result["run_id"],
            RunStep.step_type == "tool",
        )
    ).scalars().all()
    call_rows = db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == result["run_id"])
    ).scalars().all()
    assert len(step_rows) == 1
    assert len(call_rows) == 1
    assert call_rows[0].run_step_id == step_rows[0].id
    assert call_rows[0].tool_call_id == "call_stable"


@pytest.mark.asyncio
async def test_agent_tool_approval_interrupts_before_side_effect(db, ctx):
    tc = ToolCall(id="call_approval", name="tool:test:echo", arguments={"value": "sensitive"})
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text=None,
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="tool_calls",
                tool_calls=[tc],
            )
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="must not execute"))

    class ApprovalGateway:
        def __init__(self):
            self.requests = []

        def evaluate(self, request_ctx, request):
            assert request_ctx is ctx
            self.requests.append(request)
            return SimpleNamespace(
                requires_approval=True,
                task_status="waiting_approval",
                policy_ref="policy:high-risk-tool",
                reason="required_by_workspace_policy",
                approval_payload={"title": "Approve sensitive tool"},
            )

    gateway = ApprovalGateway()
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run("agent", kind="agent")
    trace_writer.update_run_status(run.id, "running")
    emitter = CollectingEmitter()
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        tool_resolver=_make_stub_resolver(),
        trace_writer=trace_writer,
        approval_checkpoint_gateway=gateway,
    )

    result = await service.run(
        _runtime_request(
            tool_refs=["tool:test:echo"],
            verify=False,
            task_id="task_approval",
            thread_id="thread_approval",
            agent_id="agent_approval",
        ),
        existing_run_id=run.id,
        event_emitter=emitter,
    )

    db.refresh(run)
    assert result["status"] == "waiting_approval"
    assert result["interrupt"]["reason"] == "tool_call"
    assert result["interrupt"]["toolCallId"] == "call_approval"
    assert result["interrupt"]["metadata"]["toolRef"] == "tool:test:echo"
    assert tool_port.calls == []
    assert gateway.requests[0]["task_id"] == "task_approval"
    assert run.status == "waiting_approval"
    assert "agent.approval.required" in [event for event, _ in emitter.events]
    assert "agent.run.succeeded" not in [event for event, _ in emitter.events]


@pytest.mark.asyncio
async def test_agent_tool_spec_approval_interrupts_without_optional_gateway(db, ctx):
    tool_ref = "tool:test:explicit_approval"
    get_registry().register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name=tool_ref,
        version="1.0.0",
        payload={
            "tool_spec": {
                "name": "explicit_approval",
                "description": "A high-risk test tool.",
                "input_schema": {"type": "object"},
                "policy": {
                    "audit_level": "basic",
                    "approval": {"mode": "required", "risk_level": "high"},
                },
            }
        },
    )
    tool_call = ToolCall(
        id="call_explicit_approval",
        name=tool_ref,
        arguments={"value": "sensitive"},
    )
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text=None,
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="tool_calls",
                tool_calls=[tool_call],
            )
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="must not execute"))
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run("agent", kind="agent")
    trace_writer.update_run_status(run.id, "running")
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        tool_resolver=_make_stub_resolver(),
        trace_writer=trace_writer,
    )

    result = await service.run(
        _runtime_request(tool_refs=[tool_ref], verify=False),
        existing_run_id=run.id,
    )

    assert result["status"] == "waiting_approval"
    assert result["interrupt"]["metadata"]["toolRef"] == tool_ref
    assert result["interrupt"]["metadata"]["riskLevel"] == "high"
    assert result["interrupt"]["metadata"]["reason"] == "tool_spec_approval_required"
    assert tool_port.calls == []


@pytest.mark.asyncio
async def test_agent_rejected_approval_cancels_record_without_side_effect(db, ctx):
    tool_call = ToolCall(
        id="call_rejected",
        name="tool:test:echo",
        arguments={"value": "sensitive"},
    )
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text=None,
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="tool_calls",
                tool_calls=[tool_call],
            ),
            ChatResponse(
                text="The action was not executed.",
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="must not execute"))

    class ApprovalGateway:
        def evaluate(self, request_ctx, request):
            return SimpleNamespace(
                requires_approval=True,
                policy_ref="policy:reject-test",
                reason="approval_required",
                approval_payload={"title": "Approve test tool"},
            )

    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run("agent", kind="agent")
    trace_writer.update_run_status(run.id, "running")
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        tool_resolver=_make_stub_resolver(),
        trace_writer=trace_writer,
        approval_checkpoint_gateway=ApprovalGateway(),
    )
    request = _runtime_request(tool_refs=["tool:test:echo"], verify=False)
    interrupted = await service.run(request, existing_run_id=run.id)
    resumed = request.model_copy(
        update={
            "approval_responses": [
                {
                    "interrupt_id": interrupted["interrupt"]["id"],
                    "status": "resolved",
                    "payload": {"decision": "rejected"},
                }
            ],
            "approval_checkpoint": interrupted["checkpoint"],
        }
    )

    result = await service.run(resumed, existing_run_id=run.id)

    record = db.execute(
        select(RunStepToolCall).where(
            RunStepToolCall.run_id == run.id,
            RunStepToolCall.tool_call_id == "call_rejected",
        )
    ).scalars().one()
    step = db.get(RunStep, record.run_step_id)
    assert result["output"] == "The action was not executed."
    assert tool_port.calls == []
    assert record.status == "rejected"
    assert step is not None
    assert step.status == "canceled"


@pytest.mark.asyncio
async def test_agent_approval_resume_continues_from_durable_checkpoint(db, ctx):
    first_call = ToolCall(id="call_first", name="tool:test:echo", arguments={"value": "first"})
    gated_call = ToolCall(id="call_gated", name="tool:test:echo", arguments={"value": "gated"})
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text=None,
                tokens_prompt=2,
                tokens_completion=1,
                finish_reason="tool_calls",
                tool_calls=[first_call, gated_call],
            ),
            ChatResponse(
                text="completed once",
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
        ]
    )
    base_tool_port = StubToolPort(ToolResponse(result="done"))

    class ApprovalGateway:
        def evaluate(self, request_ctx, request):
            return SimpleNamespace(
                requires_approval=request["details"]["tool_call_id"] == "call_gated",
                policy_ref="policy:gated",
                reason="approval_required",
                approval_payload={"title": "Approve gated tool"},
            )

    trace_writer = TraceWriter(db, ctx)
    tool_port = ToolPolicyGateway(
        gateway=base_tool_port,
        ctx=ctx,
        trace_writer=trace_writer,
        enable_egress_check=False,
    )
    run = trace_writer.create_run("agent", kind="agent")
    trace_writer.update_run_status(run.id, "running")
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        tool_resolver=_make_stub_resolver(),
        trace_writer=trace_writer,
        approval_checkpoint_gateway=ApprovalGateway(),
    )
    request = _runtime_request(
        tool_refs=["tool:test:echo"],
        verify=False,
        task_id="task_checkpoint",
        thread_id="thread_checkpoint",
        agent_id="agent_checkpoint",
    )

    interrupted = await service.run(request, existing_run_id=run.id)

    assert interrupted["status"] == "waiting_approval"
    assert interrupted["checkpoint"]["schema_version"] == 1
    assert base_tool_port.calls == [("tool:test:echo", {"value": "first"})]
    interrupted_records = db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).scalars().all()
    assert {record.tool_call_id: record.status for record in interrupted_records} == {
        "call_first": "succeeded",
        "call_gated": "waiting_approval",
    }
    gated_record_id = next(
        record.id for record in interrupted_records if record.tool_call_id == "call_gated"
    )

    resumed_request = request.model_copy(
        update={
            "approval_responses": [
                {
                    "interrupt_id": interrupted["interrupt"]["id"],
                    "status": "resolved",
                    "payload": {"decision": "approved"},
                }
            ],
            "approval_checkpoint": interrupted["checkpoint"],
        }
    )
    result = await service.run(resumed_request, existing_run_id=run.id)

    assert result["output"] == "completed once"
    assert base_tool_port.calls == [
        ("tool:test:echo", {"value": "first"}),
        ("tool:test:echo", {"value": "gated"}),
    ]
    resumed_records = db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).scalars().all()
    assert len(resumed_records) == 2
    resumed_gated = next(
        record for record in resumed_records if record.tool_call_id == "call_gated"
    )
    assert resumed_gated.id == gated_record_id
    assert resumed_gated.status == "succeeded"
    assert llm_port._responses == []


@pytest.mark.asyncio
async def test_agent_approval_resume_rejects_edited_tool_arguments(db, ctx):
    gated_call = ToolCall(
        id="call_gated_edit",
        name="tool:test:echo",
        arguments={"value": "approved"},
    )
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text=None,
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="tool_calls",
                tool_calls=[gated_call],
            )
        ]
    )
    tool_port = StubToolPort(ToolResponse(result="must not execute"))

    class ApprovalGateway:
        def evaluate(self, request_ctx, request):
            return SimpleNamespace(
                requires_approval=True,
                policy_ref="policy:gated-edit",
                reason="approval_required",
                approval_payload={"title": "Approve gated tool"},
            )

    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run("agent", kind="agent")
    trace_writer.update_run_status(run.id, "running")
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        tool_resolver=_make_stub_resolver(),
        trace_writer=trace_writer,
        approval_checkpoint_gateway=ApprovalGateway(),
    )
    request = _runtime_request(tool_refs=["tool:test:echo"], verify=False)
    interrupted = await service.run(request, existing_run_id=run.id)
    resumed_request = request.model_copy(
        update={
            "approval_responses": [
                {
                    "interrupt_id": interrupted["interrupt"]["id"],
                    "status": "resolved",
                    "payload": {
                        "decision": "approved",
                        "editedArgs": {"value": "attacker-controlled"},
                    },
                }
            ],
            "approval_checkpoint": interrupted["checkpoint"],
        }
    )

    with pytest.raises(ValidationError, match="Edited tool arguments require a new approval"):
        await service.run(resumed_request, existing_run_id=run.id)

    assert tool_port.calls == []


@pytest.mark.asyncio
async def test_agent_emits_only_the_verified_authoritative_response(db, ctx):
    llm_port = QueueLLMPort(
        [
            ChatResponse(
                text="pre-verification draft",
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="stop",
            ),
            ChatResponse(
                text=None,
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(
                        id="call_verify",
                        name="verify_response",
                        arguments={"ok": False, "reason": "unsafe claim"},
                    )
                ],
            ),
        ]
    )
    emitter = CollectingEmitter()
    service = AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=StubToolPort(ToolResponse(result="done")),
    )

    result = await service.run(_runtime_request(), event_emitter=emitter)

    response_events = [payload for name, payload in emitter.events if name == "agent.response.succeeded"]
    assert result["output"] == "Agent verification failed: unsafe claim"
    assert response_events == [{"output": result["output"]}]


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
    assert "agent.plan.succeeded" in event_names
    assert "agent.response.succeeded" in event_names
    assert "agent.run.succeeded" in event_names


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
