"""Trace emission tests: every engine execution leaves a run and its steps.

The executions run for real on the in-memory model that the container hands
out under pytest, so nothing here tolerates a failure: a run that does not
succeed, or a step that is missing, is a red test.
"""

from __future__ import annotations

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.runtime.db.models.runs import Run, RunStep
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.workflow.domain.models import Workflow
from app.modules.workflow.runtime.engine import ExecutionEngine


@pytest.fixture
def ctx() -> RequestContext:
    """Create test context."""
    return RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
        tenant_role="Owner",
        workspace_role="Owner",
    )


async def _runs(db: AsyncSession, ctx: RequestContext, mode: str) -> list[Run]:
    rows = await db.exec(
        select(Run).where(
            Run.tenant_id == ctx.tenant_id,
            Run.workspace_id == ctx.workspace_id,
            Run.mode == mode,
        )
    )
    return list(rows.all())


async def _steps(db: AsyncSession, run_id: str) -> list[RunStep]:
    rows = await db.exec(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.started_at))
    return list(rows.all())


@pytest.mark.asyncio
async def test_chat_execution_creates_trace(async_db: AsyncSession, ctx: RequestContext) -> None:
    """A chat execution records one succeeded run whose steps are all llm.

    Two llm steps are expected: the engine's own chat step and the one the
    policy-wrapped LLM port records around the model call.
    """
    trace_writer = TraceWriter(async_db, ctx)
    engine = ExecutionEngine(async_db, ctx, trace_writer)

    plan = ExecutionPlan(
        mode="chat",
        subject_kind="thread",
        subject_id="thr-trace-chat",
        subject_version_id="ver-chat",
        inputs={
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "model:test:trace-chat",
        },
    )

    result = await engine.execute(plan)

    assert result["text"]
    runs = await _runs(async_db, ctx, "chat")
    assert len(runs) == 1
    run = runs[0]
    assert run.id == plan.run_id
    assert run.status == "succeeded"
    assert run.subject_kind == "thread"
    assert run.subject_id == "thr-trace-chat"

    steps = await _steps(async_db, run.id)
    assert [step.step_type for step in steps] == ["llm", "llm"]
    assert all(step.status == "succeeded" for step in steps)


@pytest.mark.asyncio
async def test_workflow_execution_creates_trace(async_db: AsyncSession, ctx: RequestContext) -> None:
    """A workflow execution records a succeeded run with a step per node."""
    trace_writer = TraceWriter(async_db, ctx)
    engine = ExecutionEngine(async_db, ctx, trace_writer)
    workflow = Workflow(
        id="wf-trace",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="trace-workflow",
    )
    async_db.add(workflow)
    await async_db.commit()

    plan = ExecutionPlan(
        mode="workflow",
        subject_kind="workflow",
        subject_id=workflow.id,
        subject_version_id="ver-workflow",
        inputs={},
        plan_data={
            "nodes": {"done": {"id": "done", "type": "output", "input": {"value": "traced"}}},
            "edges": [],
            "execution_order": ["done"],
            "semantics": {},
            "policy": {},
        },
    )

    result = await engine.execute(plan)

    assert result["value"] == "traced"
    runs = await _runs(async_db, ctx, "workflow")
    assert len(runs) == 1
    run = runs[0]
    assert run.id == plan.run_id
    assert run.status == "succeeded"
    assert run.subject_kind == "workflow"
    assert run.subject_id == workflow.id

    steps = await _steps(async_db, run.id)
    assert [(step.step_type, step.node_id, step.status) for step in steps] == [
        ("workflow_node", "done", "succeeded")
    ]


@pytest.mark.asyncio
async def test_agent_execution_creates_trace(async_db: AsyncSession, ctx: RequestContext) -> None:
    """An agent execution records a succeeded run with an agent_plan audit step
    for its one iteration, plus the llm step of the model call inside it."""
    trace_writer = TraceWriter(async_db, ctx)
    engine = ExecutionEngine(async_db, ctx, trace_writer)

    plan = ExecutionPlan(
        mode="agent",
        subject_kind="agent",
        subject_id="agt-trace",
        subject_version_id="ver-agent",
        inputs={
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "model:test:trace-agent",
            "max_iterations": 1,
        },
    )

    result = await engine.execute(plan)

    assert result["output"]
    assert result["iterations"] == 1
    runs = await _runs(async_db, ctx, "agent")
    assert len(runs) == 1
    run = runs[0]
    assert run.id == plan.run_id
    assert run.status == "succeeded"
    assert run.subject_kind == "agent"
    assert run.subject_id == "agt-trace"

    steps = await _steps(async_db, run.id)
    assert [step.step_type for step in steps] == ["agent_plan", "llm"], (
        "Agent execution must emit an agent_plan audit step"
    )
    assert all(step.status == "succeeded" for step in steps)
