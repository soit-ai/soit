"""test_trace_events

Unit tests for trace event emission.
"""

import asyncio

import pytest
from sqlmodel import select

from app.kernel.events.bus import InMemoryEventBus
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.runs.writer import TraceWriter


@pytest.mark.asyncio
async def test_trace_writer_emits_events(async_db, ctx):
    """TraceWriter emits run/step/cost events."""
    bus = InMemoryEventBus()
    events = []

    def handler(event):
        events.append(event)

    await bus.subscribe(handler)

    writer = TraceWriter(async_db, ctx, event_bus=bus)
    run = await writer.create_run(
        mode="workflow",
        kind="workflow",
        subject_kind="workflow",
        subject_id="wf_trace",
        subject_version_id="ver_workflow",
    )
    step = await writer.create_step(run_id=run.id, step_type="workflow_node")
    await writer.update_step_status(step.id, "running")
    await writer.update_step_status(step.id, "succeeded", output_summary="ok")
    await writer.record_cost(
        run_id=run.id, step_id=step.id, billing_basis="requests", billed_quantity=1
    )

    # Without publish_sync the writer schedules publish() as a task; let it run.
    await asyncio.sleep(0)

    types = {event.type for event in events}
    assert "run.created" in types
    assert "step.created" in types
    assert "step.status" in types
    assert "cost.recorded" in types

    run_event = next(event for event in events if event.type == "run.created")
    assert run_event.tenant_id == ctx.tenant_id
    assert run_event.workspace_id == ctx.workspace_id
    assert run_event.run_id == run.id

    cost_event = next(event for event in events if event.type == "cost.recorded")
    assert cost_event.payload["run_id"] == run.id
    assert cost_event.payload["step_id"] == step.id
    assert cost_event.payload["billing_basis"] == "requests"


@pytest.mark.asyncio
async def test_trace_writer_keeps_only_exactly_once_facts_on_the_outbox(async_db, ctx):
    """Step lifecycle and intermediate run transitions never become outbox rows."""
    writer = TraceWriter(async_db, ctx, event_bus=None)
    run = await writer.create_run(mode="agent", kind="agent")
    await writer.update_run_status(run.id, "running")
    step = await writer.create_step(run_id=run.id, step_type="agent_plan")
    await writer.update_step_status(step.id, "running")
    await writer.update_step_status(step.id, "succeeded", output_summary="ok")
    await writer.record_cost(
        run_id=run.id, step_id=step.id, billing_basis="requests", billed_quantity=1
    )
    await writer.update_run_status(run.id, "succeeded")
    await async_db.commit()

    rows = (
        await async_db.exec(select(EventOutbox).where(EventOutbox.run_id == run.id))
    ).all()
    types = sorted(row.event_type for row in rows)

    assert types == ["cost.recorded", "run.created", "run.status.updated"]
    terminal = next(row for row in rows if row.event_type == "run.status.updated")
    assert terminal.payload_json["new_status"] == "succeeded"
