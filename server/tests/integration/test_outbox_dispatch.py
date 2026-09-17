"""Integration-style tests for transactional outbox enqueue → dispatch (A8/A10)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

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
async def test_enqueue_publish_dispatch_marks_done(async_db) -> None:
    """A8: same transaction path as callers (publisher → commit → dispatcher)."""
    reg = OutboxHandlerRegistry()
    seen: list[str] = []

    def h(_s, row) -> None:
        seen.append(row.event_id)

    reg.register("integration.demo", "integration.consumer", h)
    pub = OutboxPublisher(OutboxRepository(async_db))
    row = pub.publish(_env("evt_int_1"))
    await async_db.commit()

    d = OutboxDispatcher(async_db, reg)
    n = await d.run_once(batch_limit=10)
    await async_db.commit()

    assert n == 1
    assert seen == ["evt_int_1"]
    assert (await OutboxRepository(async_db).get(row.id)).status == "done"


@pytest.mark.asyncio
async def test_second_tick_does_not_reprocess_done_row(async_db) -> None:
    reg = OutboxHandlerRegistry()
    calls: list[int] = []

    def h(_s, _r) -> None:
        calls.append(1)

    reg.register("integration.demo", "c", h)
    OutboxRepository(async_db).enqueue_from_envelope(_env("evt_tick"))
    await async_db.commit()

    d = OutboxDispatcher(async_db, reg)
    assert await d.run_once(batch_limit=10) == 1
    await async_db.commit()
    assert len(calls) == 1

    assert await d.run_once(batch_limit=10) == 0
    await async_db.commit()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_requeued_pending_skips_handler_when_checkpoint_exists(async_db) -> None:
    """A10: forced re-delivery still skips completed consumer (checkpoint)."""
    reg = OutboxHandlerRegistry()
    calls: list[str] = []

    def h(_s, row) -> None:
        calls.append(row.event_id)

    reg.register("integration.demo", "c_once", h)
    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(_env("evt_requeue"))
    await async_db.commit()

    d = OutboxDispatcher(async_db, reg)
    await d.run_once(batch_limit=10)
    await async_db.commit()
    assert calls == ["evt_requeue"]

    r = await out.get(row.id)
    r.status = "pending"
    r.processed_at = None
    async_db.add(r)
    await async_db.commit()

    await d.run_once(batch_limit=10)
    await async_db.commit()
    assert calls == ["evt_requeue"]
    assert (await out.get(row.id)).status == "done"


@pytest.mark.asyncio
async def test_outbox_dispatcher_service_commits_per_tick(async_db) -> None:
    """OutboxDispatcherService uses a fresh session per tick (mirrors API worker)."""
    bind = async_db.bind
    reg = OutboxHandlerRegistry()
    reg.register("integration.demo", "svc_c", lambda _s, _r: None)

    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(_env("evt_svc"))
    await async_db.commit()

    def factory() -> AsyncSession:
        return AsyncSession(bind=bind, expire_on_commit=False)

    svc = OutboxDispatcherService(reg, db_factory=factory, batch_limit=10)
    n = await svc.run_once()
    assert n == 1

    s2 = AsyncSession(bind=bind, expire_on_commit=False)
    try:
        assert (await OutboxRepository(s2).get(row.id)).status == "done"
    finally:
        await s2.close()


def test_wiring_register_outbox_handlers_is_idempotent() -> None:
    from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers

    register_outbox_handlers()
    register_outbox_handlers()
    reg = get_outbox_registry()
    names = [h.consumer_name for h in reg.get_handlers("outbox.smoke")]
    assert names == ["builtin.smoke"]
