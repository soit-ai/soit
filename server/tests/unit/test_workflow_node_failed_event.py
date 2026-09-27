"""A failed workflow node's event keeps its error text only where content is kept."""

from __future__ import annotations

from dataclasses import replace

import pytest
from sqlmodel import select

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.workflow.runtime.executor import _emit_workflow_node_failed_outbox
from app.modules.workflow.runtime.executors.base import ExecutionContext

SECRET = "could not parse the patient record 7731"


@pytest.mark.asyncio
@pytest.mark.parametrize("capture", ["metadata_only", "full"])
async def test_the_node_failed_event_follows_the_capture_mode(async_db, ctx: RequestContext, capture) -> None:
    scoped = replace(ctx, content_capture=capture)
    writer = TraceWriter(async_db, scoped)
    run = await writer.create_run("workflow")
    step = await writer.create_step(run.id, "workflow_node", status="running")
    await async_db.commit()
    context = ExecutionContext(
        run_id=run.id, step_id=step.id, ctx=scoped, trace_writer=writer, workflow_run_id="wfr_node_failed"
    )

    await _emit_workflow_node_failed_outbox(
        context, node_id="parse", run_step=step, error_code="NODE_EXECUTION_ERROR", error_message=SECRET
    )

    [event] = (
        await async_db.exec(select(EventOutbox).where(EventOutbox.event_type == "workflow.node.failed"))
    ).all()
    assert (SECRET in str(event.payload_json)) is (capture == "full")
    assert "NODE_EXECUTION_ERROR" in str(event.payload_json)
