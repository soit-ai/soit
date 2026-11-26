"""PostgreSQL-only: a failing branch stops its running siblings.

Concurrent nodes need sessions of their own, which SQLite cannot hold, so
the scheduler's failure paths under real overlap are checked here: fail-fast
cancels the sibling before the run fails, and compensation still runs when a
sibling has to be cancelled first.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import ValidationError
from app.kernel.commons.ids import generate_ulid
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunStep, RunStepToolCall
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.workflow.runtime.engine import ExecutionEngine
from app.modules.workflow.runtime.executor import WorkflowExecutor
from app.modules.workflow.runtime.executors.base import ExecutionContext

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

SLOW_SECONDS = 5.0


class FailOneSlowOtherToolPort(ToolPort):
    def __init__(self) -> None:
        self.slow_cancelled = False
        self.slow_finished = False

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        if tool_ref.endswith(":fail"):
            await asyncio.sleep(0.2)
            return ToolResponse(result=None, success=False, error="boom", metadata={})
        try:
            await asyncio.sleep(SLOW_SECONDS)
        except asyncio.CancelledError:
            self.slow_cancelled = True
            raise
        self.slow_finished = True
        return ToolResponse(result={"tool_ref": tool_ref}, success=True, metadata={})


@pytest_asyncio.fixture
async def postgres_async_engine():
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_async_engine(
        database_url,
        connect_args={"options": "-c timezone=UTC"},
        pool_pre_ping=True,
        pool_size=8,
    )
    try:
        yield engine
    finally:
        await engine.dispose()


def _plan(run_id: str, on_error: str) -> ExecutionPlan:
    return ExecutionPlan(
        run_id=run_id,
        mode="workflow",
        inputs={},
        plan_data={
            "nodes": {
                "setup": {
                    "id": "setup",
                    "type": "set_var",
                    "input": {"set": {"ready": True}, "__compensate_with": ["undo"]},
                },
                "undo": {"id": "undo", "type": "set_var", "input": {"set": {"undone": True}}},
                "fail": {"id": "fail", "type": "tool", "input": {"tool_ref": "tool:function:fail"}},
                "slow": {"id": "slow", "type": "tool", "input": {"tool_ref": "tool:function:slow"}},
            },
            "edges": [{"from": "setup", "to": "fail"}, {"from": "setup", "to": "slow"}],
            "execution_order": ["setup", "undo", "fail", "slow"],
            "semantics": {"concurrency": 2, "on_error": on_error},
            "policy": {},
        },
    )


async def _run(engine, on_error: str) -> tuple[FailOneSlowOtherToolPort, BaseException, float, list[RunStep]]:
    token = generate_ulid()
    ctx = RequestContext(
        tenant_id=f"pg-tenant-{token}",
        workspace_id=f"pg-workspace-{token}",
        user_id="pg-user",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    db = AsyncSession(engine, expire_on_commit=False)
    trace_writer = TraceWriter(db, ctx)
    run = await trace_writer.create_run(mode="workflow", kind="workflow")
    await db.commit()
    tool_port = FailOneSlowOtherToolPort()

    async def build_node_context() -> ExecutionContext:
        session = AsyncSession(engine, expire_on_commit=False)
        return ExecutionContext(
            run_id=run.id,
            step_id=None,
            ctx=ctx,
            trace_writer=TraceWriter(session, ctx),
            tool_port=tool_port,
            workflow_policy={},
            owned_session=session,
        )

    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        tool_port=tool_port,
        workflow_policy={},
        node_context_factory=build_node_context,
    )
    started = time.monotonic()
    try:
        with pytest.raises(BaseException) as raised:
            await WorkflowExecutor(ExecutionEngine(db, ctx, trace_writer)).execute(_plan(run.id, on_error), context)
        elapsed = time.monotonic() - started
        await db.commit()
        async with AsyncSession(engine, expire_on_commit=False) as reader:
            steps = list((await reader.exec(select(RunStep).where(RunStep.run_id == run.id))).scalars().all())
        return tool_port, raised.value, elapsed, steps
    finally:
        await db.close()
        async with AsyncSession(engine) as cleanup:
            for model in (EventOutbox, RunStepToolCall, RunStep):
                await cleanup.exec(delete(model).where(model.run_id == run.id))
            await cleanup.exec(delete(Run).where(Run.id == run.id))
            await cleanup.commit()


@pytest.mark.asyncio
async def test_fail_fast_cancels_the_running_sibling(postgres_async_engine) -> None:
    tool_port, error, elapsed, steps = await _run(postgres_async_engine, "fail_fast")

    assert isinstance(error, ValidationError)
    assert tool_port.slow_cancelled
    assert not tool_port.slow_finished
    assert elapsed < SLOW_SECONDS
    status = {step.node_id: step.status for step in steps if step.step_type == "workflow_node"}
    assert status["fail"] == "failed"
    assert status["slow"] == "canceled"


@pytest.mark.asyncio
async def test_compensation_runs_after_cancelling_a_sibling(postgres_async_engine) -> None:
    tool_port, error, elapsed, steps = await _run(postgres_async_engine, "compensate")

    # A sibling's CancelledError used to escape the drain, so the run ended
    # as cancelled and no compensation step was written.
    assert isinstance(error, ValidationError)
    assert "compensated" in str(error)
    assert tool_port.slow_cancelled
    assert elapsed < SLOW_SECONDS
    compensations = [step for step in steps if step.step_type == "workflow_compensate"]
    assert [step.node_id for step in compensations] == ["undo"]
    assert compensations[0].status == "succeeded"
