"""Wave C1b/C4: observe consumers stay idempotent on duplicate handler invocation."""

from __future__ import annotations

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.observe.handlers.execution_observe import (
    handle_cost_recorded_observe,
    handle_run_created_observe,
    handle_run_status_updated_observe,
    handle_step_created_observe,
    handle_step_status_updated_observe,
)
from app.kernel.observe.metrics import cost_total, tokens_total
from app.kernel.runtime.db.models.events import EventConsumerCheckpoint, EventOutbox
from app.kernel.runtime.runs.writer import TraceWriter
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers


async def _count_projections(async_db: AsyncSession, consumer_name: str) -> int:
    rows = list(
        (await async_db.exec(
            select(EventConsumerCheckpoint).where(
                EventConsumerCheckpoint.consumer_name == consumer_name
            )
        )).all()
    )
    return len(rows)


@pytest.mark.asyncio
async def test_cost_observe_counts_usage_and_amount_from_one_event(async_db: AsyncSession) -> None:
    usage_row = EventOutbox(
        event_id="evt_cost_usage_semantics",
        event_type="cost.recorded",
        tenant_id="tenant-cost-semantics",
        workspace_id="workspace-cost-semantics",
        idempotency_key="cost-usage-semantics",
        payload_json={
            "entry_type": "usage",
            "tenant_id": "tenant-cost-semantics",
            "unit": "tokens",
            "quantity": "10",
            "prompt_tokens": 6,
            "completion_tokens": 4,
            "amount": "0.25",
        },
    )
    async_db.add(usage_row)
    await async_db.flush()

    prompt_counter = tokens_total.labels(type="prompt", tenant_id="tenant-cost-semantics")
    completion_counter = tokens_total.labels(type="completion", tenant_id="tenant-cost-semantics")
    charge_counter = cost_total.labels(resource_type="tokens", tenant_id="tenant-cost-semantics")
    before_prompt = prompt_counter._value.get()
    before_completion = completion_counter._value.get()
    before_charge = charge_counter._value.get()

    await handle_cost_recorded_observe(async_db, usage_row)

    assert prompt_counter._value.get() - before_prompt == 6
    assert completion_counter._value.get() - before_completion == 4
    assert charge_counter._value.get() - before_charge == 0.25


@pytest.mark.asyncio
async def test_run_created_observe_projection_single_slot_per_event(async_db: AsyncSession, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    tw = TraceWriter(async_db, ctx, event_bus=None)
    run = await tw.create_run("integration_mode", kind="test")

    row = (await async_db.exec(select(EventOutbox).where(EventOutbox.run_id == run.id))).first()
    assert row is not None

    dispatcher = OutboxDispatcher(async_db, reg)
    assert await dispatcher.run_once(batch_limit=20) >= 1
    await async_db.commit()

    assert (await async_db.get(EventOutbox, row.id)).status == "done"
    assert await _count_projections(async_db, "observe.run_created.side_effects") == 1

    await handle_run_created_observe(async_db, row)
    await async_db.commit()
    assert await _count_projections(async_db, "observe.run_created.side_effects") == 1


@pytest.mark.asyncio
async def test_step_lifecycle_never_reaches_the_outbox(async_db: AsyncSession, ctx) -> None:
    """Step facts are observed in-process; only exactly-once facts are enqueued."""
    tw = TraceWriter(async_db, ctx, event_bus=None)
    run = await tw.create_run("integration_mode", kind="test")
    step = await tw.create_step(run_id=run.id, step_type="tool")
    await tw.update_step_status(step.id, "running")
    await tw.update_step_status(step.id, "succeeded", output_summary="ok")
    await tw.update_run_status(run.id, "running")

    rows = (await async_db.exec(select(EventOutbox).where(EventOutbox.run_id == run.id))).all()

    assert [row.event_type for row in rows] == ["run.created"]


def _step_row(event_type: str, *, event_id: str, step_id: str, run_id: str, ctx) -> EventOutbox:
    return EventOutbox(
        event_id=event_id,
        event_type=event_type,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        idempotency_key=f"idem_{event_id}",
        run_id=run_id,
        payload_json={
            "step_row_id": step_id,
            "run_id": run_id,
            "old_status": "queued",
            "new_status": "running",
            "tenant_id": ctx.tenant_id,
        },
    )


@pytest.mark.asyncio
async def test_step_created_observe_projection_single_slot_per_event(async_db: AsyncSession, ctx) -> None:
    """A step.created row still in flight is observed once, however often it is redelivered."""
    tw = TraceWriter(async_db, ctx, event_bus=None)
    run = await tw.create_run("integration_mode", kind="test")
    step = await tw.create_step(run_id=run.id, step_type="tool")
    row = _step_row("step.created", event_id=f"evt_step_created_{step.id}", step_id=step.id, run_id=run.id, ctx=ctx)

    await handle_step_created_observe(async_db, row)
    await async_db.commit()
    await handle_step_created_observe(async_db, row)
    await async_db.commit()

    assert await _count_projections(async_db, "observe.step_created.side_effects") == 1


@pytest.mark.asyncio
async def test_run_status_observe_projection_single_slot_per_event(async_db: AsyncSession, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    tw = TraceWriter(async_db, ctx, event_bus=None)
    run = await tw.create_run("integration_mode", kind="test")
    await tw.update_run_status(run.id, "running")
    await tw.update_run_status(run.id, "succeeded")

    rows = (await async_db.exec(
        select(EventOutbox).where(EventOutbox.event_type == "run.status.updated")
    )).all()
    # Only the terminal transition is a durable fact.
    assert [row.payload_json["new_status"] for row in rows] == ["succeeded"]
    row = rows[0]

    dispatcher = OutboxDispatcher(async_db, reg)
    assert await dispatcher.run_once(batch_limit=20) >= 1
    await async_db.commit()

    assert await _count_projections(async_db, "observe.run_status.side_effects") == 1

    await handle_run_status_updated_observe(async_db, row)
    await async_db.commit()
    assert await _count_projections(async_db, "observe.run_status.side_effects") == 1


@pytest.mark.asyncio
async def test_step_status_observe_projection_single_slot_per_event(async_db: AsyncSession, ctx) -> None:
    """A step.status.updated row still in flight is observed once per event id."""
    tw = TraceWriter(async_db, ctx, event_bus=None)
    run = await tw.create_run("integration_mode", kind="test")
    step = await tw.create_step(run_id=run.id, step_type="tool")
    row = _step_row("step.status.updated", event_id=f"evt_step_status_{step.id}", step_id=step.id, run_id=run.id, ctx=ctx)

    await handle_step_status_updated_observe(async_db, row)
    await async_db.commit()
    await handle_step_status_updated_observe(async_db, row)
    await async_db.commit()

    assert await _count_projections(async_db, "observe.step_status.side_effects") == 1
