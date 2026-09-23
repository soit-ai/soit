"""PostgreSQL-only: concurrent workflow nodes really overlap on their own sessions.

SQLite cannot hold two open write transactions, so the overlap half of the
per-node session contract is checked here against the acceptance database.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.ids import generate_ulid
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunStep, RunStepToolCall
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.workflow.domain.models import Workflow, WorkflowRun
from app.modules.workflow.runtime.engine import ExecutionEngine
from app.modules.workflow.runtime.executor import WorkflowExecutor
from app.modules.workflow.runtime.executors.base import ExecutionContext

if sys.platform == "win32":
    # psycopg's async mode refuses the Proactor loop that pytest-asyncio
    # would otherwise create on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class OverlapRecordingToolPort(ToolPort):
    def __init__(self) -> None:
        self.active = 0
        self.peak = 0

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0.3)
        finally:
            self.active -= 1
        return ToolResponse(result={"tool_ref": tool_ref}, success=True, metadata={})


@pytest_asyncio.fixture
async def postgres_async_engine():
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    # Pinned to UTC like the application engine: these fixtures write
    # through their own engine, and on a server whose default zone is not
    # UTC every aware datetime would otherwise land shifted.
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


def _fan_out_plan(run_id: str) -> ExecutionPlan:
    return ExecutionPlan(
        run_id=run_id,
        mode="workflow",
        inputs={},
        plan_data={
            "nodes": {
                "left": {"id": "left", "type": "tool", "input": {"tool_ref": "tool:function:left"}},
                "right": {"id": "right", "type": "tool", "input": {"tool_ref": "tool:function:right"}},
                "join": {
                    "id": "join",
                    "type": "output",
                    "input": {"value": "{{ steps.left.output.result.tool_ref }}+{{ steps.right.output.result.tool_ref }}"},
                },
            },
            "edges": [{"from": "left", "to": "join"}, {"from": "right", "to": "join"}],
            "execution_order": ["left", "right", "join"],
            "semantics": {"concurrency": 2},
            "policy": {},
        },
    )


@pytest.mark.asyncio
async def test_nodes_overlap_on_their_own_sessions_and_the_checkpoint_names_both(postgres_async_engine) -> None:
    token = generate_ulid()
    ctx = RequestContext(
        tenant_id=f"pg-tenant-{token}",
        workspace_id=f"pg-workspace-{token}",
        user_id="pg-user",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    db = AsyncSession(postgres_async_engine, expire_on_commit=False)
    trace_writer = TraceWriter(db, ctx)
    run = await trace_writer.create_run(mode="workflow", kind="workflow")
    workflow = Workflow(tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, name=f"fan-out-{token}")
    db.add(workflow)
    await db.flush()
    workflow_run = WorkflowRun(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run.id,
        workflow_id=workflow.id,
        status="running",
        total_nodes=3,
        completed_nodes=0,
        failed_nodes=0,
        waiting_nodes=3,
    )
    db.add(workflow_run)
    await db.commit()

    tool_port = OverlapRecordingToolPort()

    async def build_node_context() -> ExecutionContext:
        session = AsyncSession(postgres_async_engine, expire_on_commit=False)
        return ExecutionContext(
            run_id=run.id,
            step_id=None,
            ctx=ctx,
            trace_writer=TraceWriter(session, ctx),
            tool_port=tool_port,
            workflow_policy={},
            workflow_run_id=workflow_run.id,
            owned_session=session,
        )

    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        tool_port=tool_port,
        workflow_policy={},
        workflow_run_id=workflow_run.id,
        node_context_factory=build_node_context,
    )

    try:
        output = await WorkflowExecutor(ExecutionEngine(db, ctx, trace_writer)).execute(
            _fan_out_plan(run.id), context
        )
        await db.commit()

        assert output["value"] == "tool:function:left+tool:function:right"
        assert tool_port.peak == 2, "the two branches did not overlap"

        async with AsyncSession(postgres_async_engine, expire_on_commit=False) as reader:
            steps = (await reader.exec(select(RunStep).where(RunStep.run_id == run.id))).scalars().all()
            assert {s.node_id: s.status for s in steps if s.node_id} == {
                "left": "succeeded",
                "right": "succeeded",
                "join": "succeeded",
            }
            row = await reader.get(WorkflowRun, workflow_run.id)
            assert row is not None
            states = (row.checkpoint_json or {}).get("node_states", {})
            assert states == {"left": "succeeded", "right": "succeeded", "join": "succeeded"}
    finally:
        await db.close()
        async with AsyncSession(postgres_async_engine) as cleanup:
            for model in (EventOutbox, RunStepToolCall, RunStep):
                await cleanup.exec(delete(model).where(model.run_id == run.id))
            await cleanup.exec(delete(WorkflowRun).where(WorkflowRun.id == workflow_run.id))
            await cleanup.exec(delete(Workflow).where(Workflow.id == workflow.id))
            await cleanup.exec(delete(Run).where(Run.id == run.id))
            await cleanup.commit()
