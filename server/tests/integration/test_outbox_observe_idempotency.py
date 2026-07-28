"""Wave C1b/C4: observe consumers stay idempotent on duplicate handler invocation."""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

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


def _count_projections(db: Session, consumer_name: str) -> int:
    rows = list(
        db.exec(
            select(EventConsumerCheckpoint).where(
                EventConsumerCheckpoint.consumer_name == consumer_name
            )
        ).all()
    )
    return len(rows)


def test_cost_observe_counts_usage_and_amount_from_one_event(db: Session) -> None:
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
    db.add(usage_row)
    db.flush()

    prompt_counter = tokens_total.labels(type="prompt", tenant_id="tenant-cost-semantics")
    completion_counter = tokens_total.labels(type="completion", tenant_id="tenant-cost-semantics")
    charge_counter = cost_total.labels(resource_type="tokens", tenant_id="tenant-cost-semantics")
    before_prompt = prompt_counter._value.get()
    before_completion = completion_counter._value.get()
    before_charge = charge_counter._value.get()

    handle_cost_recorded_observe(db, usage_row)

    assert prompt_counter._value.get() - before_prompt == 6
    assert completion_counter._value.get() - before_completion == 4
    assert charge_counter._value.get() - before_charge == 0.25


@pytest.mark.asyncio
async def test_run_created_observe_projection_single_slot_per_event(db: Session, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    tw = TraceWriter(db, ctx, event_bus=None)
    run = tw.create_run("integration_mode", kind="test")

    row = db.exec(select(EventOutbox).where(EventOutbox.run_id == run.id)).first()
    assert row is not None

    dispatcher = OutboxDispatcher(db, reg)
    assert await dispatcher.run_once(batch_limit=20) >= 1
    db.commit()

    assert db.get(EventOutbox, row.id).status == "done"
    assert _count_projections(db, "observe.run_created.side_effects") == 1

    handle_run_created_observe(db, row)
    db.commit()
    assert _count_projections(db, "observe.run_created.side_effects") == 1


@pytest.mark.asyncio
async def test_step_created_observe_projection_single_slot_per_event(db: Session, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    tw = TraceWriter(db, ctx, event_bus=None)
    run = tw.create_run("integration_mode", kind="test")
    tw.create_step(run_id=run.id, step_type="tool")

    row = db.exec(
        select(EventOutbox).where(EventOutbox.event_type == "step.created")
    ).first()
    assert row is not None

    dispatcher = OutboxDispatcher(db, reg)
    assert await dispatcher.run_once(batch_limit=20) >= 1
    db.commit()

    assert _count_projections(db, "observe.step_created.side_effects") == 1

    handle_step_created_observe(db, row)
    db.commit()
    assert _count_projections(db, "observe.step_created.side_effects") == 1


@pytest.mark.asyncio
async def test_run_status_observe_projection_single_slot_per_event(db: Session, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    tw = TraceWriter(db, ctx, event_bus=None)
    run = tw.create_run("integration_mode", kind="test")
    tw.update_run_status(run.id, "running")

    row = db.exec(
        select(EventOutbox).where(EventOutbox.event_type == "run.status.updated")
    ).first()
    assert row is not None

    dispatcher = OutboxDispatcher(db, reg)
    assert await dispatcher.run_once(batch_limit=20) >= 1
    db.commit()

    assert _count_projections(db, "observe.run_status.side_effects") == 1

    handle_run_status_updated_observe(db, row)
    db.commit()
    assert _count_projections(db, "observe.run_status.side_effects") == 1


@pytest.mark.asyncio
async def test_step_status_observe_projection_single_slot_per_event(db: Session, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    tw = TraceWriter(db, ctx, event_bus=None)
    run = tw.create_run("integration_mode", kind="test")
    step = tw.create_step(run_id=run.id, step_type="tool")
    tw.update_step_status(step.id, "running")
    tw.update_step_status(step.id, "succeeded", output_summary="ok")

    row = db.exec(
        select(EventOutbox).where(EventOutbox.event_type == "step.status.updated")
    ).first()
    assert row is not None

    dispatcher = OutboxDispatcher(db, reg)
    assert await dispatcher.run_once(batch_limit=20) >= 1
    db.commit()

    assert _count_projections(db, "observe.step_status.side_effects") == 2

    handle_step_status_updated_observe(db, row)
    db.commit()
    assert _count_projections(db, "observe.step_status.side_effects") == 2
