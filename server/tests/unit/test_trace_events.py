"""test_trace_events

Unit tests for trace event emission.
"""

import asyncio

from app.kernel.events.bus import InMemoryEventBus
from app.kernel.runtime.runs.writer import TraceWriter


def test_trace_writer_emits_events(db, ctx):
    """TraceWriter emits run/step/cost events."""
    bus = InMemoryEventBus()
    events = []

    def handler(event):
        events.append(event)

    asyncio.run(bus.subscribe(handler))

    writer = TraceWriter(db, ctx, event_bus=bus)
    run = writer.create_run(
        mode="workflow",
        kind="workflow",
        subject_kind="workflow",
        subject_id="wf_trace",
        subject_version_id="ver_workflow",
    )
    step = writer.create_step(run_id=run.id, step_type="workflow_node")
    writer.update_step_status(step.id, "running")
    writer.update_step_status(step.id, "succeeded", output_summary="ok")
    writer.record_cost(run_id=run.id, step_id=step.id, unit="requests", quantity=1)

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
    assert cost_event.payload["unit"] == "requests"


