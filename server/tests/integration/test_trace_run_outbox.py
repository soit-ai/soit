"""TraceWriter create_run writes transactional outbox rows (Wave B1)."""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.events.outbox_models import EventOutbox
from app.kernel.trace.writer import TraceWriter
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers


def test_create_run_inserts_outbox_row_same_transaction(db, ctx) -> None:
    tw = TraceWriter(db, ctx, event_bus=None)
    run = tw.create_run("integration_mode", kind="test")

    rows = list(db.exec(select(EventOutbox).where(EventOutbox.run_id == run.id)).all())
    assert len(rows) == 1
    assert rows[0].event_type == "run.created"
    assert rows[0].event_id == f"evt_run_created_{run.id}"
    assert rows[0].status == "pending"
    assert rows[0].payload_json.get("run_id") == run.id


@pytest.mark.asyncio
async def test_create_run_outbox_dispatched_to_done(db, ctx) -> None:
    register_outbox_handlers()
    tw = TraceWriter(db, ctx, event_bus=None)
    run = tw.create_run("dispatch_mode", kind="test")

    row = db.exec(select(EventOutbox).where(EventOutbox.run_id == run.id)).first()
    assert row is not None
    assert row.status == "pending"

    d = OutboxDispatcher(db, get_outbox_registry())
    n = await d.run_once(batch_limit=10)
    db.commit()
    assert n == 1

    updated = db.get(EventOutbox, row.id)
    assert updated is not None
    assert updated.status == "done"
