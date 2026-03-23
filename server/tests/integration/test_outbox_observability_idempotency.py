"""Wave C1b/C4: observability consumers stay idempotent on duplicate handler invocation."""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.events.outbox_models import EventOutbox
from app.kernel.observability.handlers.execution_observability import (
    handle_run_created_observability,
    handle_run_status_updated_observability,
    handle_step_created_observability,
    handle_step_status_updated_observability,
)
from app.kernel.observability.projection_models import ObservabilityProjectionRecord
from app.kernel.trace.writer import TraceWriter
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers


def _count_projections(db: Session, consumer_name: str) -> int:
    rows = list(
        db.exec(
            select(ObservabilityProjectionRecord).where(
                ObservabilityProjectionRecord.consumer_name == consumer_name
            )
        ).all()
    )
    return len(rows)


@pytest.mark.asyncio
async def test_run_created_observability_projection_single_slot_per_event(db: Session, ctx) -> None:
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
    assert _count_projections(db, "observability.run_created.side_effects") == 1

    handle_run_created_observability(db, row)
    db.commit()
    assert _count_projections(db, "observability.run_created.side_effects") == 1


@pytest.mark.asyncio
async def test_step_created_observability_projection_single_slot_per_event(db: Session, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    tw = TraceWriter(db, ctx, event_bus=None)
    run = tw.create_run("integration_mode", kind="test")
    step = tw.create_step(run_id=run.id, step_type="tool")

    row = db.exec(
        select(EventOutbox).where(EventOutbox.event_type == "step.created")
    ).first()
    assert row is not None

    dispatcher = OutboxDispatcher(db, reg)
    assert await dispatcher.run_once(batch_limit=20) >= 1
    db.commit()

    assert _count_projections(db, "observability.step_created.side_effects") == 1

    handle_step_created_observability(db, row)
    db.commit()
    assert _count_projections(db, "observability.step_created.side_effects") == 1


@pytest.mark.asyncio
async def test_run_status_observability_projection_single_slot_per_event(db: Session, ctx) -> None:
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

    assert _count_projections(db, "observability.run_status.side_effects") == 1

    handle_run_status_updated_observability(db, row)
    db.commit()
    assert _count_projections(db, "observability.run_status.side_effects") == 1


@pytest.mark.asyncio
async def test_step_status_observability_projection_single_slot_per_event(db: Session, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    tw = TraceWriter(db, ctx, event_bus=None)
    run = tw.create_run("integration_mode", kind="test")
    step = tw.create_step(run_id=run.id, step_type="tool")
    tw.update_step_status(step.id, "succeeded", output_summary="ok")

    row = db.exec(
        select(EventOutbox).where(EventOutbox.event_type == "step.status.updated")
    ).first()
    assert row is not None

    dispatcher = OutboxDispatcher(db, reg)
    assert await dispatcher.run_once(batch_limit=20) >= 1
    db.commit()

    assert _count_projections(db, "observability.step_status.side_effects") == 1

    handle_step_status_updated_observability(db, row)
    db.commit()
    assert _count_projections(db, "observability.step_status.side_effects") == 1
