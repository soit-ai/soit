"""test_workflow_executor

Unit tests for workflow executor node routing and step recording.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlmodel import Session

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
)
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.ports.tools.policy import ToolPolicyGateway
from app.kernel.runtime.db.models.runs import Run, RunStep, RunStepToolCall
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.workflow.application.capabilities import get_workflow_node_capabilities
from app.modules.workflow.application.compiler import WorkflowCompiler
from app.modules.workflow.domain.models import WorkflowRun
from app.modules.workflow.runtime.engine import ExecutionEngine
from app.modules.workflow.runtime.executor import WorkflowExecutor
from app.modules.workflow.runtime.executors import _executor_registry, get_executor
from app.modules.workflow.runtime.executors.base import ExecutionContext
from app.modules.workflow.runtime.executors.input import InputNodeExecutor
from app.modules.workflow.runtime.executors.node import RegistryNodeExecutor
from app.modules.workflow.runtime.executors.tool import ToolNodeExecutor
from tests.fixtures.workflow_specs import CANONICAL_NODE_TYPES, canonical_workflow_spec


def test_workflow_executor_registry_records_current_node_types() -> None:
    """The current runtime registry includes canonical and compatibility executors."""
    assert set(_executor_registry) == {
        "condition",
        "http",
        "input",
        "llm",
        "node",
        "output",
        "retrieve",
        "set_var",
        "tool",
        "transform",
    }


def test_every_executable_capability_resolves_to_a_registered_executor() -> None:
    executable_node_types = {
        capability.type
        for capability in get_workflow_node_capabilities()
        if capability.executable
    }

    assert executable_node_types <= set(_executor_registry)
    assert all(get_executor(node_type) is _executor_registry[node_type] for node_type in executable_node_types)


def test_canonical_node_types_document_the_approved_target() -> None:
    assert CANONICAL_NODE_TYPES == (
        "input",
        "transform",
        "set_var",
        "llm",
        "retrieve",
        "tool",
        "condition",
        "output",
    )


def test_canonical_workflow_spec_returns_deeply_isolated_copies() -> None:
    caller_params = {"mapping": {"value": {"tags": ["original"]}}}
    caller_spec = canonical_workflow_spec(params=caller_params)
    first_default_spec = canonical_workflow_spec()
    second_default_spec = canonical_workflow_spec()

    caller_params["mapping"]["value"]["tags"].append("mutated")
    caller_spec["graph"]["nodes"][0]["params"]["mapping"]["value"]["tags"].append("saved")
    first_default_spec["graph"]["nodes"][0]["params"]["mapping"]["value"] = False

    assert caller_spec["graph"]["nodes"][0]["params"]["mapping"]["value"]["tags"] == ["original", "saved"]
    assert second_default_spec["graph"]["nodes"][0]["params"] == {"mapping": {"value": True}}


@pytest.mark.parametrize(
    ("limits", "expected"),
    [
        (None, {"budget_currency": "USD"}),
        ({"budget": 3.5}, {"budget": 3.5, "budget_currency": "USD"}),
        (
            {"budget": 3.5, "budget_currency": "EUR"},
            {"budget": 3.5, "budget_currency": "EUR"},
        ),
    ],
)
def test_workflow_compiler_materializes_budget_currency_default(
    limits: dict[str, Any] | None,
    expected: dict[str, Any],
) -> None:
    spec = canonical_workflow_spec()
    if limits is not None:
        spec["limits"] = limits
    original_limits = dict(limits) if limits is not None else None

    plan = WorkflowCompiler().compile(spec, {}, "run-budget-default")

    assert plan.plan_data["limits"] == expected
    if original_limits is None:
        assert "limits" not in spec
    else:
        assert spec["limits"] == original_limits


class FakeLLMPort(LLMPort):
    """Deterministic LLM port for tests."""

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        last_user = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_user = msg.content or ""
                break
        return ChatResponse(text=last_user or "ok", model=model, finish_reason="stop")

    async def embed(self, texts: list[str], model: str, **kwargs: Any) -> EmbeddingResponse:
        return EmbeddingResponse(embeddings=[[0.0] * 3 for _ in texts], tokens_used=0, model=model)

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        return RerankResponse(results=[], tokens_used=0, model=model)


class FakeToolPort(ToolPort):
    """Tool port that records invocations."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        self.calls.append({"tool_ref": tool_ref, "parameters": parameters, "kwargs": kwargs})
        return ToolResponse(result={"tool_ref": tool_ref, "parameters": parameters}, success=True, metadata={})


class FakeWorkflowKnowledgeQueryPort:
    """Knowledge port that records canonical workflow retrieval requests."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def query(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "context": "Refund policy",
            "documents": [{"id": "chunk-1", "text": "Refund policy"}],
            "citations": [{"id": "chunk-1", "rank": 1}],
            "count": 1,
        }


class FakeKnowledgeRuntimeService:
    """Knowledge runtime fake that records its scoped application request."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def query(self, knowledge_id: str, request: Any) -> Any:
        self.calls.append((knowledge_id, request))
        return type(
            "KnowledgeQueryResponse",
            (),
            {
                "model_dump": lambda self: {
                    "results": [
                        {
                            "chunk_id": "chunk-1",
                            "document_id": "document-1",
                            "score": 0.9,
                            "text": "Refund policy",
                            "snippets": ["Refund policy"],
                        }
                    ],
                    "total": 1,
                    "citations": [
                        {
                            "chunk_id": "chunk-1",
                            "document_id": "document-1",
                            "rank": 1,
                            "score": 0.9,
                        }
                    ],
                }
            },
        )()


class ExplicitApprovalToolPort(FakeToolPort):
    """Tool port exposing a required ToolSpec approval policy."""

    def get_tool_policy(
        self,
        tool_ref: str,
        ctx: RequestContext,
    ) -> dict[str, Any]:
        return {
            "audit_level": "basic",
            "approval": {"mode": "required", "risk_level": "high"},
        }


class FlakyToolPort(ToolPort):
    """Tool port that fails once then succeeds."""

    def __init__(self) -> None:
        self.calls: int = 0

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        self.calls += 1
        if self.calls == 1:
            return ToolResponse(result=None, success=False, error="boom", metadata={})
        return ToolResponse(result={"ok": True}, success=True, metadata={})


class FailingToolPort(ToolPort):
    """Tool port that always fails."""

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        return ToolResponse(result=None, success=False, error="boom", metadata={})


class PluginToolPort(ToolPort):
    """Tool port that returns plugin source metadata."""

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        return ToolResponse(
            result={"tool_ref": tool_ref, "parameters": parameters},
            success=True,
            metadata={
                "source_kind": "plugin",
                "adapter": "plugin",
                "plugin_name": "demo-plugin",
                "plugin_version": "1.0.0",
                "tool_ref": tool_ref,
            },
        )


class RequiredApprovalGateway:
    """Approval gateway fake that requires approval for tool invocations."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def evaluate(self, ctx: RequestContext, request: dict[str, Any]) -> Any:
        self.requests.append(dict(request))
        return type(
            "ApprovalDecision",
            (),
            {
                "requires_approval": True,
                "reason": "required_by_workspace_policy",
                "policy_ref": "approval:critical-tools",
                "task_status": "waiting_approval",
                "approval_payload": {
                    "run_id": request.get("run_id"),
                    "title": "Approve tool call",
                    "policy_ref": "approval:critical-tools",
                },
            },
        )()


def _unwrap_steps(rows: list[Any]) -> list[RunStep]:
    """Normalize SQLModel rows to RunStep instances."""
    steps: list[RunStep] = []
    for row in rows:
        if isinstance(row, RunStep):
            steps.append(row)
            continue
        if isinstance(row, list | tuple) and row:
            steps.append(row[0])
            continue
        if hasattr(row, "_mapping"):
            steps.append(row[0])
    return steps


def _branching_output_execution(
    db: Session,
    ctx: RequestContext,
    *,
    approved: bool,
    true_when: str = "{{ steps.condition.output.result }}",
    false_when: str = "{{ steps.condition.output.result }} == false",
) -> tuple[Run, ExecutionPlan, WorkflowExecutor, ExecutionContext]:
    trace_writer = TraceWriter(db, ctx)
    engine = ExecutionEngine(db, ctx, trace_writer)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_active_output",
        subject_version_id="ver_workflow",
    )
    plan = ExecutionPlan(
        run_id=run.id,
        mode="workflow",
        inputs={"approved": approved},
        plan_data={
            "nodes": {
                "false_output": {
                    "id": "false_output",
                    "type": "output",
                    "input": {"path": "false"},
                },
                "condition": {
                    "id": "condition",
                    "type": "condition",
                    "input": {"condition": "{{ inputs.approved }}"},
                },
                "true_output": {
                    "id": "true_output",
                    "type": "output",
                    "input": {"path": "true"},
                },
            },
            "edges": [
                {"from": "condition", "to": "true_output", "when": true_when},
                {"from": "condition", "to": "false_output", "when": false_when},
            ],
            "execution_order": ["condition", "true_output", "false_output"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )
    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=FakeLLMPort(),
        tool_port=FakeToolPort(),
        vector_port=None,
        plugin_runtime_port=None,
        workflow_policy={},
    )
    return run, plan, WorkflowExecutor(engine), context


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('False == "false"', False),
        ('"false"', True),
        ("False == false", True),
        ("false", False),
    ],
)
def test_workflow_executor_distinguishes_quoted_boolean_literals(
    db: Session,
    ctx: RequestContext,
    expression: str,
    expected: bool,
) -> None:
    trace_writer = TraceWriter(db, ctx)
    executor = WorkflowExecutor(ExecutionEngine(db, ctx, trace_writer))

    assert executor._evaluate_condition(expression, {}) is expected


def test_workflow_compiler_rejects_conflicting_condition_and_when() -> None:
    edge = {
        "id": "edge-1",
        "from": "input",
        "to": "output",
        "condition": "{{ inputs.enabled }}",
        "when": "{{ inputs.disabled }}",
    }

    with pytest.raises(ValidationError, match="condition.*when"):
        WorkflowCompiler()._normalize_edges([edge])


@pytest.mark.asyncio
async def test_retrieve_step_delegates_exact_reference_and_options(
    db: Session,
    ctx: RequestContext,
) -> None:
    trace_writer = TraceWriter(db, ctx)
    engine = ExecutionEngine(db, ctx, trace_writer)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_retrieve",
        subject_version_id="ver_workflow",
    )
    knowledge_port = FakeWorkflowKnowledgeQueryPort()
    plan = ExecutionPlan(
        run_id=run.id,
        mode="workflow",
        inputs={"question": "Can I get a refund?"},
        plan_data={
            "nodes": {
                "retrieve": {
                    "id": "retrieve",
                    "type": "retrieve",
                    "input": {
                        "knowledge_ref": "knowledge:refund-policy",
                        "query": "{{ inputs.question }}",
                        "top_k": 7,
                        "filters": {"locale": "en-US"},
                        "rerank_model": "model:test:reranker",
                    },
                },
                "output": {
                    "id": "output",
                    "type": "output",
                    "input": {"value": "{{ steps.retrieve.output.context }}"},
                },
            },
            "edges": [{"from": "retrieve", "to": "output"}],
            "execution_order": ["retrieve", "output"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )
    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        workflow_knowledge_query_port=knowledge_port,
        workflow_policy={},
    )

    result = await WorkflowExecutor(engine).execute(plan, context)

    assert result == {"value": "Refund policy"}
    assert knowledge_port.calls == [
        {
            "knowledge_ref": "knowledge:refund-policy",
            "query": "Can I get a refund?",
            "top_k": 7,
            "filters": {"locale": "en-US"},
            "rerank_model": "model:test:reranker",
            "ctx": ctx,
            "run_id": run.id,
        }
    ]


@pytest.mark.asyncio
async def test_scoped_workflow_knowledge_adapter_delegates_to_runtime_service(
    ctx: RequestContext,
) -> None:
    from app.wiring.workflow_resources import KnowledgeRuntimeWorkflowQueryAdapter

    runtime_service = FakeKnowledgeRuntimeService()
    adapter = KnowledgeRuntimeWorkflowQueryAdapter(
        runtime_service=runtime_service,
        ctx=ctx,
    )

    result = await adapter.query(
        knowledge_ref="knowledge:refund-policy",
        query="Can I get a refund?",
        top_k=7,
        filters={"locale": "en-US"},
        rerank_model="model:test:reranker",
        ctx=ctx,
        run_id="run-1",
    )

    assert result == {
        "context": "Refund policy",
        "documents": [
            {
                "chunk_id": "chunk-1",
                "document_id": "document-1",
                "score": 0.9,
                "text": "Refund policy",
                "snippets": ["Refund policy"],
            }
        ],
        "citations": [
            {
                "chunk_id": "chunk-1",
                "document_id": "document-1",
                "rank": 1,
                "score": 0.9,
            }
        ],
        "count": 1,
    }
    assert len(runtime_service.calls) == 1
    knowledge_id, request = runtime_service.calls[0]
    assert knowledge_id == "refund-policy"
    assert request.query == "Can I get a refund?"
    assert request.top_k == 7
    assert request.filter == {"locale": "en-US"}
    assert request.use_rerank is True
    assert request.reranker_ref == "model:test:reranker"


@pytest.mark.asyncio
async def test_scoped_workflow_knowledge_adapter_rejects_context_mismatch(
    ctx: RequestContext,
) -> None:
    from app.wiring.workflow_resources import KnowledgeRuntimeWorkflowQueryAdapter

    runtime_service = FakeKnowledgeRuntimeService()
    adapter = KnowledgeRuntimeWorkflowQueryAdapter(
        runtime_service=runtime_service,
        ctx=ctx,
    )
    other_ctx = RequestContext(
        tenant_id="other-tenant",
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
    )

    with pytest.raises(ValidationError, match="scope"):
        await adapter.query(
            knowledge_ref="knowledge:refund-policy",
            query="Can I get a refund?",
            top_k=7,
            filters=None,
            rerank_model=None,
            ctx=other_ctx,
            run_id="run-1",
        )

    assert runtime_service.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ctx_overrides",
    [
        {"user_id": "other-user"},
        {"workspace_role": "Viewer"},
        {"tenant_role": "Viewer"},
    ],
)
async def test_scoped_workflow_knowledge_adapter_rejects_rebound_identity(
    ctx: RequestContext,
    ctx_overrides: dict[str, str],
) -> None:
    from app.wiring.workflow_resources import KnowledgeRuntimeWorkflowQueryAdapter

    runtime_service = FakeKnowledgeRuntimeService()
    adapter = KnowledgeRuntimeWorkflowQueryAdapter(
        runtime_service=runtime_service,
        ctx=ctx,
    )
    other_ctx = RequestContext(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx_overrides.get("user_id", ctx.user_id),
        tenant_role=ctx_overrides.get("tenant_role", ctx.tenant_role),
        workspace_role=ctx_overrides.get("workspace_role", ctx.workspace_role),
    )

    with pytest.raises(ValidationError, match="scope"):
        await adapter.query(
            knowledge_ref="knowledge:refund-policy",
            query="Can I get a refund?",
            top_k=7,
            filters=None,
            rerank_model=None,
            ctx=other_ctx,
            run_id="run-1",
        )

    assert runtime_service.calls == []


@pytest.mark.asyncio
async def test_tool_node_uses_canonical_arguments_payload(
    db: Session,
    ctx: RequestContext,
) -> None:
    trace_writer = TraceWriter(db, ctx)
    tool_port = FakeToolPort()
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_tool_arguments",
        subject_version_id="ver_workflow",
    )
    context = ExecutionContext(
        run_id=run.id,
        step_id="step_tool_arguments",
        ctx=ctx,
        trace_writer=trace_writer,
        tool_port=tool_port,
        workflow_policy={},
    )

    result = await ToolNodeExecutor().execute(
        {"id": "ticket_tool", "type": "tool"},
        context,
        {
            "tool_ref": "builtin.ticket.create_review_ticket",
            "arguments": {
                "customer_id": "customer-1",
                "api_token": {"secret_id": "sec_ticket_api_key"},
            },
        },
    )

    assert result["result"]["parameters"] == {
        "customer_id": "customer-1",
        "api_token": {"secret_id": "sec_ticket_api_key"},
    }
    assert tool_port.calls[0]["parameters"] == {
        "customer_id": "customer-1",
        "api_token": {"secret_id": "sec_ticket_api_key"},
    }


class TransientlyRaisingToolPort(ToolPort):
    """Tool port that raises a configured number of times, then succeeds."""

    def __init__(self, fail_times: int = 0) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail_times = fail_times

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        self.calls.append({"tool_ref": tool_ref, "parameters": parameters})
        if len(self.calls) <= self.fail_times:
            raise RuntimeError("transient adapter outage")
        return ToolResponse(result={"call_count": len(self.calls)}, success=True, metadata={})


def _attempt_context(
    trace_writer: TraceWriter,
    ctx: RequestContext,
    run_id: str,
    *,
    node_id: str,
    attempt: int,
    tool_port: ToolPort,
) -> ExecutionContext:
    step = trace_writer.create_step(
        run_id=run_id,
        step_type="workflow_node",
        step_id=f"st_{node_id}" if attempt == 1 else f"st_{node_id}_retry{attempt}",
        node_id=node_id,
    )
    return ExecutionContext(
        run_id=run_id,
        step_id=step.id,
        ctx=ctx,
        trace_writer=trace_writer,
        tool_port=tool_port,
        workflow_policy={},
    )


@pytest.mark.asyncio
async def test_tool_node_second_attempt_replays_completed_call(
    db: Session,
    ctx: RequestContext,
) -> None:
    """A retry after a completed tool call must not reissue the side effect."""

    trace_writer = TraceWriter(db, ctx)
    tool_port = TransientlyRaisingToolPort(fail_times=0)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_tool_replay",
        subject_version_id="ver_workflow",
    )
    node = {"id": "ticket", "type": "tool"}
    inputs = {"tool_ref": "builtin.ticket.create", "arguments": {"customer_id": "c1"}}

    first_ctx = _attempt_context(
        trace_writer, ctx, run.id, node_id="ticket", attempt=1, tool_port=tool_port
    )
    first = await ToolNodeExecutor().execute(node, first_ctx, inputs)
    second_ctx = _attempt_context(
        trace_writer, ctx, run.id, node_id="ticket", attempt=2, tool_port=tool_port
    )
    second = await ToolNodeExecutor().execute(node, second_ctx, inputs)

    assert len(tool_port.calls) == 1
    assert first["result"]["call_count"] == 1
    assert second["result"]["call_count"] == 1
    record = db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).scalars().one()
    assert record.tool_call_id == f"workflow:{run.id}:ticket:0"
    assert record.status == "succeeded"
    tool_steps = db.execute(
        select(RunStep).where(RunStep.run_id == run.id, RunStep.step_type == "tool")
    ).scalars().all()
    assert len(tool_steps) == 1


@pytest.mark.asyncio
async def test_tool_node_retry_reexecutes_failed_call(
    db: Session,
    ctx: RequestContext,
) -> None:
    """A retry after a failed tool call must re-execute, not replay the failure."""

    trace_writer = TraceWriter(db, ctx)
    tool_port = TransientlyRaisingToolPort(fail_times=1)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_tool_retry",
        subject_version_id="ver_workflow",
    )
    node = {"id": "ticket", "type": "tool"}
    inputs = {"tool_ref": "builtin.ticket.create", "arguments": {"customer_id": "c1"}}

    first_ctx = _attempt_context(
        trace_writer, ctx, run.id, node_id="ticket", attempt=1, tool_port=tool_port
    )
    with pytest.raises(RuntimeError, match="transient adapter outage"):
        await ToolNodeExecutor().execute(node, first_ctx, inputs)
    second_ctx = _attempt_context(
        trace_writer, ctx, run.id, node_id="ticket", attempt=2, tool_port=tool_port
    )
    second = await ToolNodeExecutor().execute(node, second_ctx, inputs)

    assert len(tool_port.calls) == 2
    assert second["result"]["call_count"] == 2
    record = db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).scalars().one()
    assert record.status == "succeeded"
    assert record.attempt_count == 2


@pytest.mark.asyncio
async def test_input_node_exposes_validated_workflow_inputs(db: Session, ctx: RequestContext) -> None:
    trace_writer = TraceWriter(db, ctx)
    engine = ExecutionEngine(db, ctx, trace_writer)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_input",
        subject_version_id="ver_workflow",
    )
    plan = ExecutionPlan(
        run_id=run.id,
        mode="workflow",
        inputs={"ticket_id": "T-100", "ignored": "not-exposed"},
        plan_data={
            "nodes": {
                "start": {
                    "id": "start",
                    "type": "input",
                    "input": {"select": ["ticket_id"]},
                },
                "out": {
                    "id": "out",
                    "type": "output",
                    "input": {"value": "{{ steps.start.output.ticket_id }}"},
                },
            },
            "edges": [{"from": "start", "to": "out"}],
            "execution_order": ["start", "out"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )
    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=FakeLLMPort(),
        tool_port=FakeToolPort(),
        vector_port=None,
        plugin_runtime_port=None,
        workflow_policy={},
    )

    result = await WorkflowExecutor(engine).execute(plan, context)

    assert result == {"value": "T-100"}
    rows = db.exec(select(RunStep).where(RunStep.run_id == run.id)).all()
    start_step = next(step for step in _unwrap_steps(rows) if step.node_id == "start")
    assert "T-100" in (start_step.output_summary or "")
    assert "ignored" not in (start_step.output_summary or "")
    assert "not-exposed" not in (start_step.output_summary or "")


@pytest.mark.asyncio
async def test_input_node_safely_ignores_malformed_select(db: Session, ctx: RequestContext) -> None:
    context = ExecutionContext(
        run_id="run_input_malformed",
        step_id="step_input_malformed",
        ctx=ctx,
        trace_writer=TraceWriter(db, ctx),
        workflow_inputs={"ticket_id": "T-100"},
    )

    result = await InputNodeExecutor().execute({}, context, {"select": 42})

    assert result == {}


@pytest.mark.asyncio
async def test_input_node_ignores_malformed_select_entries(db: Session, ctx: RequestContext) -> None:
    context = ExecutionContext(
        run_id="run_input_mixed_select",
        step_id="step_input_mixed_select",
        ctx=ctx,
        trace_writer=TraceWriter(db, ctx),
        workflow_inputs={"ticket_id": "T-100"},
    )

    result = await InputNodeExecutor().execute(
        {},
        context,
        {"select": [{}, 42, "ticket_id", "missing"]},
    )

    assert result == {"ticket_id": "T-100"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("approved", "expected_output", "inactive_output"),
    [
        (True, {"path": "true"}, "false_output"),
        (False, {"path": "false"}, "true_output"),
    ],
)
async def test_workflow_executor_returns_only_the_active_output(
    db: Session,
    ctx: RequestContext,
    approved: bool,
    expected_output: dict[str, str],
    inactive_output: str,
) -> None:
    run, plan, executor, context = _branching_output_execution(db, ctx, approved=approved)

    result = await executor.execute(plan, context)

    assert result == expected_output
    rows = db.exec(select(RunStep).where(RunStep.run_id == run.id)).all()
    status_by_node = {step.node_id: step.status for step in _unwrap_steps(rows)}
    assert status_by_node[inactive_output] == "skipped"


@pytest.mark.asyncio
async def test_workflow_executor_rejects_zero_active_outputs(db: Session, ctx: RequestContext) -> None:
    _, plan, executor, context = _branching_output_execution(
        db,
        ctx,
        approved=True,
        true_when="false",
        false_when="false",
    )

    with pytest.raises(ValidationError, match="^Workflow must produce exactly one active output$"):
        await executor.execute(plan, context)


@pytest.mark.asyncio
async def test_workflow_executor_rejects_more_than_one_active_output(
    db: Session,
    ctx: RequestContext,
) -> None:
    _, plan, executor, context = _branching_output_execution(
        db,
        ctx,
        approved=True,
        true_when="true",
        false_when="true",
    )

    with pytest.raises(ValidationError, match="^Workflow must produce exactly one active output$"):
        await executor.execute(plan, context)


@pytest.mark.asyncio
async def test_workflow_executor_runs_nodes_and_records_steps(db: Session, ctx: RequestContext) -> None:
    trace_writer = TraceWriter(db, ctx)
    engine = ExecutionEngine(db, ctx, trace_writer)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_executor",
        subject_version_id="ver_workflow",
    )

    plan = ExecutionPlan(
        run_id=run.id,
        mode="workflow",
        inputs={},
        plan_data={
            "nodes": {
                "set1": {"id": "set1", "type": "set_var", "input": {"set": {"flag": True}}},
                "cond1": {"id": "cond1", "type": "condition", "input": {"condition": "{{ steps.set1.output.flag }}"}},
                "tool1": {"id": "tool1", "type": "tool", "input": {"tool_ref": "tool:function:time_now"}},
                "http1": {"id": "http1", "type": "http", "input": {"url": "https://example.com"}},
                "llm1": {
                    "id": "llm1",
                    "type": "llm",
                    "input": {
                        "prompt": "Tool={{ steps.tool1.output.result.tool_ref }}, Http={{ steps.http1.output.result.tool_ref }}",
                    },
                },
                "out1": {"id": "out1", "type": "output", "input": {"value": "{{ steps.llm1.output.text }}"}},
            },
            "edges": [
                {"from": "set1", "to": "cond1"},
                {"from": "cond1", "to": "tool1", "when": "{{ steps.cond1.output.result }}"},
                {"from": "cond1", "to": "http1", "when": "{{ steps.cond1.output.result }}"},
                {"from": "tool1", "to": "llm1"},
                {"from": "http1", "to": "llm1"},
                {"from": "llm1", "to": "out1"},
            ],
            "execution_order": ["set1", "cond1", "tool1", "http1", "llm1", "out1"],
            "semantics": {"concurrency": 2},
            "policy": {},
        },
    )

    fake_tool = FakeToolPort()
    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=FakeLLMPort(),
        tool_port=fake_tool,
        vector_port=None,
        plugin_runtime_port=None,
        workflow_policy={},
    )

    executor = WorkflowExecutor(engine)
    output = await executor.execute(plan, context)

    assert output["value"]
    assert {call["tool_ref"] for call in fake_tool.calls} == {"tool:function:time_now", "tool:http:request"}
    assert all(call["kwargs"].get("tool_call_id") for call in fake_tool.calls)
    assert all(call["kwargs"].get("idempotency_key") for call in fake_tool.calls)

    rows = db.exec(select(RunStep).where(RunStep.run_id == run.id)).all()
    steps = _unwrap_steps(rows)
    status_by_node = {step.node_id: step.status for step in steps}
    for node_id in ("set1", "cond1", "tool1", "http1", "llm1", "out1"):
        assert status_by_node.get(node_id) == "succeeded"


@pytest.mark.asyncio
async def test_registry_workflow_node_passes_stable_tool_identity(db: Session, ctx: RequestContext) -> None:
    from app.kernel.registry.deps import get_registry

    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(mode="workflow", kind="workflow")
    node_step = trace_writer.create_step(
        run_id=run.id,
        step_type="workflow_node",
        step_id="node:plugin1",
        node_id="plugin1",
    )
    fake_tool = FakeToolPort()
    get_registry().register(
        kind="workflow_node",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="node:test:echo",
        version="1.0.0",
        payload={
            "node_spec": {
                "input_schema": {"type": "object"},
                "adapter": "tool",
                "tool_ref": "tool:test:echo",
            }
        },
    )
    context = ExecutionContext(
        run_id=run.id,
        step_id=node_step.id,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=FakeLLMPort(),
        tool_port=fake_tool,
        vector_port=None,
        plugin_runtime_port=None,
        workflow_policy={},
        workflow_run_id="wfr-1",
    )

    await RegistryNodeExecutor().execute(
        {"id": "plugin1", "type": "node"},
        context,
        {"node_ref": "node:test:echo", "parameters": {"value": "hello"}},
    )

    assert len(fake_tool.calls) == 1
    kwargs = fake_tool.calls[0]["kwargs"]
    assert kwargs["tool_call_id"] == "workflow:wfr-1:plugin1:0"
    # Attempt-independent: a retry or crash-resume must reach the same ledger
    # record and replay it rather than reissuing the call.
    assert node_step.id not in kwargs["tool_call_id"]
    assert kwargs["idempotency_key"] == f"tool:{run.id}:{kwargs['tool_call_id']}"
    assert kwargs["retry_failed"] is True


@pytest.mark.asyncio
async def test_execution_engine_agent_passes_existing_tool_step_identity(
    db: Session,
    ctx: RequestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class QueueAgentLLM(FakeLLMPort):
        def __init__(self) -> None:
            self.responses = [
                ChatResponse(
                    text='{"tool_call":{"tool_ref":"tool:test:echo","parameters":{"value":"one"}}}',
                    model="model:test:primary",
                    finish_reason="stop",
                ),
                ChatResponse(text="done", model="model:test:primary", finish_reason="stop"),
            ]

        async def chat(self, *args: Any, **kwargs: Any) -> ChatResponse:
            return self.responses.pop(0)

    fake_tool = FakeToolPort()
    fake_llm = QueueAgentLLM()

    class FakeContainer:
        def get_llm_port(self, **kwargs: Any) -> LLMPort:
            return fake_llm

        def get_tool_port(self, **kwargs: Any) -> ToolPort:
            return fake_tool

    import app.wiring

    monkeypatch.setattr(app.wiring, "get_container", lambda: FakeContainer())
    trace_writer = TraceWriter(db, ctx)
    engine = ExecutionEngine(db, ctx, trace_writer)
    run = trace_writer.create_run(mode="agent", kind="agent")
    plan = ExecutionPlan(
        run_id=run.id,
        mode="agent",
        inputs={
            "messages": [{"role": "user", "content": "use the tool"}],
            "model": "model:test:primary",
            "max_iterations": 2,
            "tools": [{"ref": "tool:test:echo"}],
        },
    )

    await engine._execute_agent(plan)

    assert len(fake_tool.calls) == 1
    kwargs = fake_tool.calls[0]["kwargs"]
    assert kwargs["tool_call_id"] == kwargs["run_step_id"]
    assert kwargs["idempotency_key"] == f"tool:{run.id}:{kwargs['tool_call_id']}"


@pytest.mark.asyncio
async def test_workflow_executor_skips_nodes_when_edge_condition_false(db: Session, ctx: RequestContext) -> None:
    trace_writer = TraceWriter(db, ctx)
    engine = ExecutionEngine(db, ctx, trace_writer)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_skip",
        subject_version_id="ver_workflow",
    )

    plan = ExecutionPlan(
        run_id=run.id,
        mode="workflow",
        inputs={},
        plan_data={
            "nodes": {
                "set1": {"id": "set1", "type": "set_var", "input": {"set": {"flag": False}}},
                "cond1": {"id": "cond1", "type": "condition", "input": {"condition": "{{ steps.set1.output.flag }}"}},
                "tool1": {"id": "tool1", "type": "tool", "input": {"tool_ref": "tool:function:time_now"}},
                "out1": {"id": "out1", "type": "output", "input": {"value": "{{ steps.set1.output.flag }}"}},
            },
            "edges": [
                {"from": "set1", "to": "cond1"},
                {"from": "cond1", "to": "tool1", "when": "{{ steps.cond1.output.result }}"},
                {"from": "cond1", "to": "out1"},
            ],
            "execution_order": ["set1", "cond1", "tool1", "out1"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )

    executor = WorkflowExecutor(engine)
    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=FakeLLMPort(),
        tool_port=FakeToolPort(),
        vector_port=None,
        plugin_runtime_port=None,
        workflow_policy={},
    )

    output = await executor.execute(plan, context)
    assert output["value"] is False

    rows = db.exec(select(RunStep).where(RunStep.run_id == run.id)).all()
    steps = _unwrap_steps(rows)
    status_by_node = {step.node_id: step.status for step in steps}
    assert status_by_node.get("tool1") == "skipped"
    assert status_by_node.get("out1") == "succeeded"


@pytest.mark.asyncio
async def test_workflow_executor_defaults_to_fail_fast_on_node_failure(db: Session, ctx: RequestContext) -> None:
    trace_writer = TraceWriter(db, ctx)
    engine = ExecutionEngine(db, ctx, trace_writer)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_default_fail_fast",
        subject_version_id="ver_workflow",
    )

    plan = ExecutionPlan(
        run_id=run.id,
        mode="workflow",
        inputs={},
        plan_data={
            "nodes": {
                "tool1": {"id": "tool1", "type": "tool", "input": {"tool_ref": "tool:function:time_now"}},
                "out1": {"id": "out1", "type": "output", "input": {"value": "{{ steps.tool1.output.result.ok }}"}},
            },
            "edges": [{"from": "tool1", "to": "out1"}],
            "execution_order": ["tool1", "out1"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )

    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=FakeLLMPort(),
        tool_port=FailingToolPort(),
        vector_port=None,
        plugin_runtime_port=None,
        workflow_policy={},
    )

    executor = WorkflowExecutor(engine)
    with pytest.raises(ValidationError):
        await executor.execute(plan, context)


@pytest.mark.asyncio
async def test_workflow_executor_creates_retry_steps(db: Session, ctx: RequestContext) -> None:
    """Retry attempts create additional steps instead of overwriting."""
    trace_writer = TraceWriter(db, ctx)
    engine = ExecutionEngine(db, ctx, trace_writer)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_retry",
        subject_version_id="ver_workflow",
    )

    plan = ExecutionPlan(
        run_id=run.id,
        mode="workflow",
        inputs={},
        plan_data={
            "nodes": {
                "tool1": {
                    "id": "tool1",
                    "type": "tool",
                    "input": {"tool_ref": "tool:function:time_now"},
                    "retry_policy": {"max_retries": 1},
                },
                "out1": {"id": "out1", "type": "output", "input": {"value": "{{ steps.tool1.output.result.ok }}"}},
            },
            "edges": [{"from": "tool1", "to": "out1"}],
            "execution_order": ["tool1", "out1"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )

    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=FakeLLMPort(),
        tool_port=FlakyToolPort(),
        vector_port=None,
        plugin_runtime_port=None,
        workflow_policy={},
    )

    executor = WorkflowExecutor(engine)
    output = await executor.execute(plan, context)
    assert output["value"] is True

    rows = db.exec(select(RunStep).where(RunStep.run_id == run.id)).all()
    steps = _unwrap_steps(rows)
    tool_steps = [step for step in steps if step.node_id == "tool1"]
    assert len(tool_steps) == 2
    statuses = {step.status for step in tool_steps}
    assert "failed" in statuses
    assert "succeeded" in statuses


@pytest.mark.asyncio
async def test_workflow_llm_node_creates_linked_response_events(db: Session, ctx: RequestContext) -> None:
    trace_writer = TraceWriter(db, ctx)
    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=trace_writer,
    )
    engine = ExecutionEngine(db, ctx, trace_writer, response_service=response_service)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_llm",
        subject_version_id="ver_workflow",
    )

    plan = ExecutionPlan(
        run_id=run.id,
        mode="workflow",
        inputs={},
        plan_data={
            "nodes": {
                "llm1": {
                    "id": "llm1",
                    "type": "llm",
                    "input": {"prompt": "hello workflow"},
                },
                "out1": {
                    "id": "out1",
                    "type": "output",
                    "input": {
                        "value": {
                            "text": "{{ steps.llm1.output.text }}",
                            "response_id": "{{ steps.llm1.output.response_id }}",
                        }
                    },
                },
            },
            "edges": [{"from": "llm1", "to": "out1"}],
            "execution_order": ["llm1", "out1"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )

    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=FakeLLMPort(),
        tool_port=FakeToolPort(),
        vector_port=None,
        plugin_runtime_port=None,
        response_service=response_service,
        workflow_policy={},
    )

    executor = WorkflowExecutor(engine)
    output = await executor.execute(plan, context)
    response_id = output["value"]["response_id"]

    assert response_id.startswith("resp_")

    response = response_service.get_response(response_id)
    events = response_service.list_response_events(response_id, limit=20, offset=0)
    assert response.run_id == run.id
    assert response.status == "succeeded"
    assert [event.type for event in events] == [
        "response.created",
        "response.input.added",
        "response.output_text.done",
        "response.succeeded",
    ]


@pytest.mark.asyncio
async def test_workflow_tool_node_creates_tool_call_detail(db: Session, ctx: RequestContext) -> None:
    trace_writer = TraceWriter(db, ctx)
    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=trace_writer,
    )
    engine = ExecutionEngine(db, ctx, trace_writer, response_service=response_service)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_tool",
        subject_version_id="ver_workflow",
    )

    plan = ExecutionPlan(
        run_id=run.id,
        mode="workflow",
        inputs={},
        plan_data={
            "nodes": {
                "tool1": {
                    "id": "tool1",
                    "type": "tool",
                    "input": {"tool_ref": "tool:function:time_now", "zone": "UTC"},
                },
                "out1": {
                    "id": "out1",
                    "type": "output",
                    "input": {
                        "value": {
                            "tool_ref": "{{ steps.tool1.output.result.tool_ref }}",
                            "response_id": "{{ steps.tool1.output.response_id }}",
                        }
                    },
                },
            },
            "edges": [{"from": "tool1", "to": "out1"}],
            "execution_order": ["tool1", "out1"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )

    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=FakeLLMPort(),
        tool_port=ToolPolicyGateway(
            gateway=FakeToolPort(),
            ctx=ctx,
            trace_writer=trace_writer,
            enable_egress_check=False,
        ),
        vector_port=None,
        plugin_runtime_port=None,
        response_service=response_service,
        workflow_policy={},
    )

    executor = WorkflowExecutor(engine)
    output = await executor.execute(plan, context)
    response_id = output["value"]["response_id"]

    assert response_id.startswith("resp_")
    response = response_service.get_response(response_id)
    events = response_service.list_response_events(response_id, limit=20, offset=0)
    _, _, tool_calls = response_service.get_response_detail(response_id)

    assert response.run_id == run.id
    assert response.status == "succeeded"
    assert len(tool_calls) == 1
    assert tool_calls[0]["tool_name"] == "tool:function:time_now"
    assert tool_calls[0]["status"] == "completed"
    assert tool_calls[0]["arguments_json"] == {"zone": "UTC"}
    assert tool_calls[0]["result_json"]["result"]["tool_ref"] == "tool:function:time_now"
    node_step = db.execute(
        select(RunStep).where(
            RunStep.run_id == run.id,
            RunStep.node_id == "tool1",
            RunStep.step_type == "workflow_node",
        )
    ).scalars().one()
    call_record = db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).scalars().one()
    tool_step = db.get(RunStep, call_record.run_step_id)
    assert call_record.tool_call_id == f"workflow:{run.id}:tool1:0"
    # The identity must stay attempt-independent or retries re-run side effects.
    assert node_step.id not in call_record.tool_call_id
    assert tool_step is not None
    assert tool_step.step_type == "tool"
    tool_events = [event for event in events if event.type.startswith("tool.call.")]
    assert {event.payload_json["step_id"] for event in tool_events} == {tool_step.id}
    assert {event.payload_json["run_step_id"] for event in tool_events} == {tool_step.id}
    assert [event.type for event in events] == [
        "response.created",
        "response.input.added",
        "tool.call.requested",
        "tool.call.started",
        "tool.call.completed",
        "response.succeeded",
    ]


@pytest.mark.asyncio
async def test_workflow_tool_node_records_plugin_tool_type(db: Session, ctx: RequestContext) -> None:
    trace_writer = TraceWriter(db, ctx)
    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=trace_writer,
    )
    engine = ExecutionEngine(db, ctx, trace_writer, response_service=response_service)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_plugin_tool",
        subject_version_id="ver_workflow",
    )

    plan = ExecutionPlan(
        run_id=run.id,
        mode="workflow",
        inputs={},
        plan_data={
            "nodes": {
                "tool1": {
                    "id": "tool1",
                    "type": "tool",
                    "input": {"tool_ref": "tool:http:plugin_echo", "value": "hello"},
                },
                "out1": {
                    "id": "out1",
                    "type": "output",
                    "input": {
                        "value": {
                            "metadata": "{{ steps.tool1.output.metadata }}",
                            "response_id": "{{ steps.tool1.output.response_id }}",
                        }
                    },
                },
            },
            "edges": [{"from": "tool1", "to": "out1"}],
            "execution_order": ["tool1", "out1"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )

    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=FakeLLMPort(),
        tool_port=ToolPolicyGateway(
            gateway=PluginToolPort(),
            ctx=ctx,
            trace_writer=trace_writer,
            enable_egress_check=False,
        ),
        vector_port=None,
        plugin_runtime_port=None,
        response_service=response_service,
        workflow_policy={},
    )

    executor = WorkflowExecutor(engine)
    output = await executor.execute(plan, context)
    response_id = output["value"]["response_id"]

    events = response_service.list_response_events(response_id, limit=20, offset=0)
    completed_event = next(event for event in events if event.type == "tool.call.completed")
    _, _, tool_calls = response_service.get_response_detail(response_id)

    assert output["value"]["metadata"]["source_kind"] == "plugin"
    assert completed_event.payload_json["tool_type"] == "plugin"
    assert completed_event.payload_json["metadata"]["plugin_name"] == "demo-plugin"
    assert tool_calls[0]["tool_type"] == "plugin"
    assert tool_calls[0]["metadata_json"]["plugin_name"] == "demo-plugin"
    call_record = db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).scalars().one()
    assert call_record.tool_ref == "tool:http:plugin_echo"
    assert call_record.status == "succeeded"


@pytest.mark.asyncio
async def test_workflow_tool_node_intercepts_required_approval_before_tool_invocation(
    db: Session,
    ctx: RequestContext,
) -> None:
    trace_writer = TraceWriter(db, ctx)
    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=trace_writer,
    )
    engine = ExecutionEngine(db, ctx, trace_writer, response_service=response_service)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_approval_tool",
        subject_version_id="ver_workflow",
    )
    tool_backend = FakeToolPort()
    tool_port = ToolPolicyGateway(
        gateway=tool_backend,
        ctx=ctx,
        trace_writer=trace_writer,
        enable_egress_check=False,
    )
    approval_gateway = RequiredApprovalGateway()
    plan = ExecutionPlan(
        run_id=run.id,
        mode="workflow",
        inputs={},
        plan_data={
            "nodes": {
                "tool1": {
                    "id": "tool1",
                    "type": "tool",
                    "input": {
                        "tool_ref": "tool:http:prod_delete_user",
                        "risk_level": "critical",
                    },
                },
                "out1": {
                    "id": "out1",
                    "type": "output",
                    "input": {
                        "value": {
                            "tool_ref": "{{ steps.tool1.output.result.tool_ref }}",
                            "response_id": "{{ steps.tool1.output.response_id }}",
                        }
                    },
                },
            },
            "edges": [{"from": "tool1", "to": "out1"}],
            "execution_order": ["tool1", "out1"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )
    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=FakeLLMPort(),
        tool_port=tool_port,
        vector_port=None,
        plugin_runtime_port=None,
        response_service=response_service,
        workflow_policy={},
        approval_checkpoint_gateway=approval_gateway,
    )

    output = await WorkflowExecutor(engine).execute(plan, context)
    assert output["status"] == "waiting_approval"
    checkpoint = output["_checkpoint"]
    response_id = output["response_id"]
    events = response_service.list_response_events(response_id, limit=20, offset=0)
    _, _, tool_calls = response_service.get_response_detail(response_id)

    assert tool_backend.calls == []
    assert approval_gateway.requests == [
        {
            "action": "invoke",
            "resource_type": "tool",
            "resource_ref": "tool:http:prod_delete_user",
            "risk_level": "critical",
            "run_id": run.id,
            "task_id": None,
            "thread_id": None,
            "agent_id": None,
            "title": "Approve tool call: tool:http:prod_delete_user",
            "details": {
                "node_id": "tool1",
                "tool_ref": "tool:http:prod_delete_user",
                "parameters": {"risk_level": "critical"},
            },
        }
    ]
    assert any(event.type == "tool.call.approval_required" for event in events)
    record = db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).scalars().one()
    tool_step = db.get(RunStep, record.run_step_id)
    assert record.status == "waiting_approval"
    assert record.outbound_started_at is None
    assert tool_step is not None
    assert tool_step.status == "waiting_approval"
    assert len(tool_calls) == 1
    assert tool_calls[0]["run_step_tool_call_id"] == record.id
    assert tool_calls[0]["tool_call_id"] == record.tool_call_id
    assert tool_calls[0]["status"] == "waiting_approval"

    resumed = await WorkflowExecutor(engine).execute(
        plan,
        context,
        checkpoint=checkpoint,
    )

    assert resumed["value"]["tool_ref"] == "tool:http:prod_delete_user"
    assert resumed["value"]["response_id"] == response_id
    assert len(tool_backend.calls) == 1
    assert tool_backend.calls[0]["kwargs"]["resume_approval"] is True
    resumed_record = db.get(RunStepToolCall, record.id)
    assert resumed_record is not None
    assert resumed_record.status == "succeeded"
    assert db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).scalars().all() == [resumed_record]


@pytest.mark.asyncio
async def test_workflow_tool_spec_approval_interrupts_without_optional_gateway(
    db: Session,
    ctx: RequestContext,
) -> None:
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_explicit_tool_approval",
        subject_version_id="ver_workflow",
    )
    tool_port = ExplicitApprovalToolPort()
    context = ExecutionContext(
        run_id=run.id,
        step_id="workflow_attempt_explicit_approval",
        ctx=ctx,
        trace_writer=trace_writer,
        tool_port=tool_port,
    )

    output = await ToolNodeExecutor().execute(
        {"id": "tool1", "type": "tool"},
        context,
        {"tool_ref": "tool:test:explicit_approval", "value": "sensitive"},
    )

    assert output["status"] == "waiting_approval"
    assert output["metadata"]["reason"] == "tool_spec_approval_required"
    assert output["metadata"]["risk_level"] == "high"
    assert tool_port.calls == []
    record = db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).scalars().one()
    assert record.status == "waiting_approval"
    assert record.outbound_started_at is None


@pytest.mark.asyncio
async def test_execution_engine_persists_and_resumes_workflow_approval_checkpoint(
    db: Session,
    ctx: RequestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace_writer = TraceWriter(db, ctx)
    backend = ExplicitApprovalToolPort()
    tool_port = ToolPolicyGateway(
        gateway=backend,
        ctx=ctx,
        trace_writer=trace_writer,
        enable_egress_check=False,
    )

    class FakeContainer:
        def get_llm_port(self, **_: Any) -> LLMPort:
            return FakeLLMPort()

        def get_tool_port(self, **_: Any) -> ToolPort:
            return tool_port

        def get_vector_port(self, **_: Any) -> None:
            return None

        def get_plugin_runtime_port(self, **_: Any) -> None:
            return None

    monkeypatch.setattr("app.wiring.get_container", lambda: FakeContainer())
    engine = ExecutionEngine(db, ctx, trace_writer)
    plan = ExecutionPlan(
        run_id="",
        mode="workflow",
        inputs={"value": "approved"},
        subject_kind="workflow",
        subject_id="wf_durable_approval",
        subject_version_id="ver_durable_approval",
        plan_data={
            "nodes": {
                "tool1": {
                    "id": "tool1",
                    "type": "tool",
                    "input": {
                        "tool_ref": "tool:test:explicit_approval",
                        "value": "{{ inputs.value }}",
                    },
                },
                "out1": {
                    "id": "out1",
                    "type": "output",
                    "input": {
                        "value": "{{ steps.tool1.output.result.parameters.value }}"
                    },
                },
            },
            "edges": [{"from": "tool1", "to": "out1"}],
            "execution_order": ["tool1", "out1"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )

    waiting = await engine.execute(plan)

    run = db.get(Run, plan.run_id)
    workflow_run = db.execute(
        select(WorkflowRun).where(WorkflowRun.run_id == plan.run_id)
    ).scalars().one()
    record = db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == plan.run_id)
    ).scalars().one()
    assert waiting["status"] == "waiting_approval"
    assert "_checkpoint" not in waiting
    assert run is not None and run.status == "waiting_approval"
    assert workflow_run.status == "waiting_approval"
    assert workflow_run.checkpoint_json is not None
    assert backend.calls == []

    completed = await engine.resume_workflow(
        plan,
        workflow_run_id=workflow_run.id,
        checkpoint=dict(workflow_run.checkpoint_json),
    )

    db.refresh(run)
    db.refresh(workflow_run)
    db.refresh(record)
    assert completed == {"value": "approved"}
    assert run.status == "succeeded"
    assert workflow_run.status == "succeeded"
    assert workflow_run.checkpoint_json is None
    assert record.status == "succeeded"
    assert len(backend.calls) == 1
    assert db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == plan.run_id)
    ).scalars().all() == [record]
