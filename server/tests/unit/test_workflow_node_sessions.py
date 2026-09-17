"""Workflow nodes run on their own sessions when the context can build them.

A session cannot be driven from two tasks at once, so without a node context
factory the executor runs nodes one at a time on the shared session. With one,
every node gets a context of its own and the executor commits and closes that
context's session when the node is done. Real overlap needs row-level locking,
so that half of the contract lives in ``tests/postgres``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.workflow.runtime.engine import ExecutionEngine
from app.modules.workflow.runtime.executor import WorkflowExecutor
from app.modules.workflow.runtime.executors.base import ExecutionContext


class OverlapRecordingToolPort(ToolPort):
    """Tool port that measures how many invocations were in flight at once."""

    def __init__(self) -> None:
        self.active = 0
        self.peak = 0
        self.calls: list[str] = []

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.calls.append(tool_ref)
        try:
            await asyncio.sleep(0.05)
        finally:
            self.active -= 1
        return ToolResponse(result={"tool_ref": tool_ref}, success=True, metadata={})


class _SessionSpy:
    """Stands in for a node's owned session; the real writes go elsewhere."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def close(self) -> None:
        self.closed = True


def fan_out_plan(run_id: str, *, concurrency: int = 2) -> ExecutionPlan:
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
            "semantics": {"concurrency": concurrency},
            "policy": {},
        },
    )


@pytest.mark.asyncio
async def test_without_a_factory_nodes_run_one_at_a_time(async_db, ctx: RequestContext) -> None:
    trace_writer = TraceWriter(async_db, ctx)
    run = await trace_writer.create_run(mode="workflow", kind="workflow")
    tool_port = OverlapRecordingToolPort()
    context = ExecutionContext(
        run_id=run.id, step_id=None, ctx=ctx, trace_writer=trace_writer, tool_port=tool_port, workflow_policy={}
    )

    output = await WorkflowExecutor(ExecutionEngine(async_db, ctx, trace_writer)).execute(
        fan_out_plan(run.id), context
    )

    assert output["value"] == "tool:function:left+tool:function:right"
    assert tool_port.peak == 1


@pytest.mark.asyncio
async def test_every_node_gets_its_own_context_which_is_committed_and_closed(
    async_db, ctx: RequestContext
) -> None:
    """The in-memory database has one connection, so the node contexts here
    write through the shared session and only the ownership bookkeeping is
    exercised: one context per node, each committed and closed exactly once."""
    trace_writer = TraceWriter(async_db, ctx)
    run = await trace_writer.create_run(mode="workflow", kind="workflow")
    tool_port = OverlapRecordingToolPort()
    spies: list[_SessionSpy] = []

    async def build_node_context() -> ExecutionContext:
        spy = _SessionSpy()
        spies.append(spy)
        return ExecutionContext(
            run_id=run.id,
            step_id=None,
            ctx=ctx,
            trace_writer=trace_writer,
            tool_port=tool_port,
            workflow_policy={},
            owned_session=spy,  # type: ignore[arg-type]
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
    # A chain rather than a fan-out: the shared session must not be driven
    # from two tasks, and this test is about ownership, not overlap.
    plan = fan_out_plan(run.id)
    plan.plan_data["edges"] = [{"from": "left", "to": "right"}, {"from": "right", "to": "join"}]

    output = await WorkflowExecutor(ExecutionEngine(async_db, ctx, trace_writer)).execute(plan, context)

    assert output["value"] == "tool:function:left+tool:function:right"
    assert len(spies) == 3
    assert all(spy.commits == 1 and spy.closed for spy in spies)
    assert all(spy.rollbacks == 0 for spy in spies)
