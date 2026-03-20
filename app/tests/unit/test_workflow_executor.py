"""test_workflow_executor

Unit tests for workflow executor node routing and step recording.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from sqlalchemy import select
from sqlmodel import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.ports.llm.interface import LLMPort, ChatMessage, ChatResponse, EmbeddingResponse, RerankResponse
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.responses.repository import ResponseEventRepository, ResponseRepository
from app.kernel.responses.service import ResponseService
from app.kernel.trace.models import RunStep
from app.kernel.trace.writer import TraceWriter
from app.modules.workflow.runtime.engine import ExecutionEngine
from app.modules.workflow.runtime.executor import WorkflowExecutor
from app.modules.workflow.runtime.executors.base import ExecutionContext


class FakeLLMPort(LLMPort):
    """Deterministic LLM port for tests."""

    async def chat(
        self,
        messages: List[ChatMessage],
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

    async def embed(self, texts: List[str], model: str, **kwargs: Any) -> EmbeddingResponse:
        return EmbeddingResponse(embeddings=[[0.0] * 3 for _ in texts], tokens_used=0, model=model)

    async def rerank(
        self,
        query: str,
        documents: List[str],
        model: str,
        top_n: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        return RerankResponse(results=[], tokens_used=0, model=model)


class FakeToolPort(ToolPort):
    """Tool port that records invocations."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def invoke(self, tool_ref: str, parameters: Dict[str, Any], **kwargs: Any) -> ToolResponse:
        self.calls.append({"tool_ref": tool_ref, "parameters": parameters})
        return ToolResponse(result={"tool_ref": tool_ref, "parameters": parameters}, success=True, metadata={})


class FlakyToolPort(ToolPort):
    """Tool port that fails once then succeeds."""

    def __init__(self) -> None:
        self.calls: int = 0

    async def invoke(self, tool_ref: str, parameters: Dict[str, Any], **kwargs: Any) -> ToolResponse:
        self.calls += 1
        if self.calls == 1:
            return ToolResponse(result=None, success=False, error="boom", metadata={})
        return ToolResponse(result={"ok": True}, success=True, metadata={})


def _unwrap_steps(rows: list[Any]) -> list[RunStep]:
    """Normalize SQLModel rows to RunStep instances."""
    steps: list[RunStep] = []
    for row in rows:
        if isinstance(row, RunStep):
            steps.append(row)
            continue
        if isinstance(row, (list, tuple)) and row:
            steps.append(row[0])
            continue
        if hasattr(row, "_mapping"):
            steps.append(row[0])
    return steps


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

    rows = db.exec(select(RunStep).where(RunStep.run_id == run.id)).all()
    steps = _unwrap_steps(rows)
    status_by_node = {step.node_id: step.status for step in steps}
    for node_id in ("set1", "cond1", "tool1", "http1", "llm1", "out1"):
        assert status_by_node.get(node_id) == "succeeded"


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
    assert response.status == "completed"
    assert [event.type for event in events] == [
        "response.created",
        "response.input.added",
        "response.output_text.completed",
        "response.completed",
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
    _, _, tool_calls = response_service.get_response_detail(response_id)

    assert response.run_id == run.id
    assert response.status == "completed"
    assert len(tool_calls) == 1
    assert tool_calls[0]["tool_name"] == "tool:function:time_now"
    assert tool_calls[0]["status"] == "completed"
    assert tool_calls[0]["arguments_json"] == {"zone": "UTC"}
    assert tool_calls[0]["result_json"]["result"]["tool_ref"] == "tool:function:time_now"
    assert [event.type for event in events] == [
        "response.created",
        "response.input.added",
        "tool.call.requested",
        "tool.call.started",
        "tool.call.completed",
        "response.completed",
    ]


