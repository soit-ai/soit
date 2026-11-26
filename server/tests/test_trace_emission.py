"""Trace emission tests: every workflow execution leaves a run and its steps.

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
async def test_a_plan_that_is_not_a_workflow_fails_its_run(async_db: AsyncSession, ctx: RequestContext) -> None:
    """Agents and chat run through their own services, so the engine refuses
    any other plan and records the refusal on the run it opened."""
    engine = ExecutionEngine(async_db, ctx, TraceWriter(async_db, ctx))
    plan = ExecutionPlan(mode="agent", subject_kind="agent", subject_id="agt-trace", inputs={})

    with pytest.raises(ValueError, match="Unsupported mode"):
        await engine.execute(plan)

    runs = await _runs(async_db, ctx, "agent")
    assert [run.status for run in runs] == ["failed"]
