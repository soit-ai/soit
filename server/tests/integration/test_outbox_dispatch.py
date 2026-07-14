"""Integration-style tests for transactional outbox enqueue → dispatch (A8/A10)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlmodel import Session

from app.kernel.events.dispatcher import OutboxDispatcher, OutboxDispatcherService
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.kernel.events.registry import OutboxHandlerRegistry


def _env(eid: str, etype: str = "integration.demo") -> DomainEventEnvelope:
    return DomainEventEnvelope(
        event_id=eid,
        event_type=etype,
        occurred_at=datetime(2025, 3, 23, 10, 0, 0, tzinfo=UTC),
        payload={"n": 1},
    )


@pytest.mark.asyncio
async def test_enqueue_publish_dispatch_marks_done(db: Session) -> None:
    """A8: same transaction path as callers (publisher → commit → dispatcher)."""
    reg = OutboxHandlerRegistry()
    seen: list[str] = []

    def h(_s, row) -> None:
        seen.append(row.event_id)

    reg.register("integration.demo", "integration.consumer", h)
    pub = OutboxPublisher(OutboxRepository(db))
    row = pub.publish(_env("evt_int_1"))
    db.commit()

    d = OutboxDispatcher(db, reg)
    n = await d.run_once(batch_limit=10)
    db.commit()

    assert n == 1
    assert seen == ["evt_int_1"]
    assert OutboxRepository(db).get(row.id).status == "done"


@pytest.mark.asyncio
async def test_second_tick_does_not_reprocess_done_row(db: Session) -> None:
    reg = OutboxHandlerRegistry()
    calls: list[int] = []

    def h(_s, _r) -> None:
        calls.append(1)

    reg.register("integration.demo", "c", h)
    OutboxRepository(db).enqueue_from_envelope(_env("evt_tick"))
    db.commit()

    d = OutboxDispatcher(db, reg)
    assert await d.run_once(batch_limit=10) == 1
    db.commit()
    assert len(calls) == 1

    assert await d.run_once(batch_limit=10) == 0
    db.commit()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_requeued_pending_skips_handler_when_checkpoint_exists(db: Session) -> None:
    """A10: forced re-delivery still skips completed consumer (checkpoint)."""
    reg = OutboxHandlerRegistry()
    calls: list[str] = []

    def h(_s, row) -> None:
        calls.append(row.event_id)

    reg.register("integration.demo", "c_once", h)
    out = OutboxRepository(db)
    row = out.enqueue_from_envelope(_env("evt_requeue"))
    db.commit()

    d = OutboxDispatcher(db, reg)
    await d.run_once(batch_limit=10)
    db.commit()
    assert calls == ["evt_requeue"]

    r = out.get(row.id)
    r.status = "pending"
    r.processed_at = None
    db.add(r)
    db.commit()

    await d.run_once(batch_limit=10)
    db.commit()
    assert calls == ["evt_requeue"]
    assert out.get(row.id).status == "done"


@pytest.mark.asyncio
async def test_outbox_dispatcher_service_commits_per_tick(db: Session) -> None:
    """OutboxDispatcherService uses a fresh session per tick (mirrors API worker)."""
    bind = db.get_bind()
    reg = OutboxHandlerRegistry()
    reg.register("integration.demo", "svc_c", lambda _s, _r: None)

    out = OutboxRepository(db)
    row = out.enqueue_from_envelope(_env("evt_svc"))
    db.commit()

    def factory() -> Session:
        return Session(bind)

    svc = OutboxDispatcherService(reg, db_factory=factory, batch_limit=10)
    n = await svc.run_once()
    assert n == 1

    s2 = Session(bind)
    try:
        assert OutboxRepository(s2).get(row.id).status == "done"
    finally:
        s2.close()


def test_wiring_register_outbox_handlers_is_idempotent() -> None:
    from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers

    register_outbox_handlers()
    register_outbox_handlers()
    reg = get_outbox_registry()
    names = [h.consumer_name for h in reg.get_handlers("outbox.smoke")]
    assert names == ["builtin.smoke"]
