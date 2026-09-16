"""Unit tests for OutboxDispatcher."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.events.checkpoint import ConsumerCheckpointRepository
from app.kernel.events.dispatcher import OutboxDispatcher, OutboxDispatcherService
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.registry import OutboxHandlerRegistry
from app.kernel.runtime.db.models.events import EventOutbox


def _env(eid: str = "evt_disp_1", etype: str = "run.created") -> DomainEventEnvelope:
    return DomainEventEnvelope(
        event_id=eid,
        event_type=etype,
        occurred_at=datetime(2025, 3, 23, 10, 0, 0, tzinfo=UTC),
        payload={"x": 1},
    )


async def _status(out: OutboxRepository, row_id: str) -> str:
    loaded = await out.get(row_id)
    assert loaded is not None
    return loaded.status


@pytest.mark.asyncio
async def test_dispatcher_invokes_handler_and_marks_done(async_db) -> None:
    registry = OutboxHandlerRegistry()
    seen: list[str] = []

    def h(_sess, row: EventOutbox) -> None:
        seen.append(row.event_id)

    registry.register("run.created", "consumer_a", h)
    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(_env())
    await async_db.commit()

    d = OutboxDispatcher(async_db, registry)
    n = await d.run_once(batch_limit=10)
    await async_db.commit()

    assert n == 1
    assert seen == ["evt_disp_1"]
    assert await _status(out, row.id) == "done"


@pytest.mark.asyncio
async def test_async_handlers_receive_the_dispatcher_session(async_db) -> None:
    registry = OutboxHandlerRegistry()
    seen: list[str] = []

    async def h(sess: AsyncSession, row: EventOutbox) -> None:
        loaded = await sess.get(EventOutbox, row.id)
        assert loaded is not None
        seen.append(loaded.event_id)

    registry.register("run.created", "consumer_async", h)
    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(_env("evt_async_handler"))
    await async_db.commit()

    await OutboxDispatcher(async_db, registry).run_once(batch_limit=10)
    await async_db.commit()

    assert seen == ["evt_async_handler"]
    assert await _status(out, row.id) == "done"


@pytest.mark.asyncio
async def test_two_handlers_run_in_registration_order(async_db) -> None:
    registry = OutboxHandlerRegistry()
    order: list[str] = []

    def h1(_s, _r) -> None:
        order.append("1")

    def h2(_s, _r) -> None:
        order.append("2")

    registry.register("run.created", "c1", h1)
    registry.register("run.created", "c2", h2)
    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(_env("evt_order"))
    await async_db.commit()

    d = OutboxDispatcher(async_db, registry)
    await d.run_once(batch_limit=10)
    await async_db.commit()

    assert order == ["1", "2"]
    assert await _status(out, row.id) == "done"


@pytest.mark.asyncio
async def test_checkpoint_skips_already_processed_handler(async_db) -> None:
    registry = OutboxHandlerRegistry()
    seen: list[str] = []

    def h(_s, _r) -> None:
        seen.append("run")

    registry.register("run.created", "c_skip", h)
    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(_env("evt_skip"))
    await async_db.commit()

    cp = ConsumerCheckpointRepository(async_db)
    assert await cp.try_record_success("c_skip", "evt_skip", result="pre") is True
    await async_db.commit()

    d = OutboxDispatcher(async_db, registry)
    await d.run_once(batch_limit=10)
    await async_db.commit()

    assert seen == []
    assert await _status(out, row.id) == "done"


@pytest.mark.asyncio
async def test_handler_failure_marks_retry(async_db) -> None:
    registry = OutboxHandlerRegistry()

    def boom(_s, _r) -> None:
        raise RuntimeError("no")

    registry.register("run.created", "c_fail", boom)
    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(_env("evt_fail"))
    await async_db.commit()

    d = OutboxDispatcher(async_db, registry, max_dispatch_attempts=5)
    await d.run_once(batch_limit=10)
    await async_db.commit()

    r = await out.get(row.id)
    assert r is not None
    assert r.status == "pending"
    assert r.attempt_count == 1
    assert "c_fail" in (r.last_error or "")


@pytest.mark.asyncio
async def test_max_attempts_marks_failed_on_outbox_row(async_db) -> None:
    registry = OutboxHandlerRegistry()

    def boom(_s, _r) -> None:
        raise ValueError("bad")

    registry.register("run.created", "c_dlq", boom)
    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(_env("evt_dlq"))
    await async_db.commit()

    d = OutboxDispatcher(async_db, registry, max_dispatch_attempts=1, record_dead_letter=True)
    await d.run_once(batch_limit=10)
    await async_db.commit()

    r = await out.get(row.id)
    assert r is not None
    assert r.status == "failed"
    assert r.failed_consumer_name == "c_dlq"
    assert "c_dlq" in (r.last_error or "")
    assert "bad" in (r.last_error or "")


@pytest.mark.asyncio
async def test_outbox_dispatcher_service_commits_via_db_factory(async_db) -> None:
    bind = async_db.bind
    registry = OutboxHandlerRegistry()
    seen: list[str] = []

    def h(_s, row: EventOutbox) -> None:
        seen.append(row.event_id)

    registry.register("run.created", "svc_consumer", h)
    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(_env("evt_svc_factory"))
    await async_db.commit()

    def factory() -> AsyncSession:
        return AsyncSession(bind, expire_on_commit=False)

    svc = OutboxDispatcherService(registry, db_factory=factory, batch_limit=10)
    n = await svc.run_once()
    assert n == 1
    assert seen == ["evt_svc_factory"]

    s2 = AsyncSession(bind, expire_on_commit=False)
    try:
        assert await _status(OutboxRepository(s2), row.id) == "done"
    finally:
        await s2.close()


@pytest.mark.asyncio
async def test_no_handlers_marks_done(async_db) -> None:
    registry = OutboxHandlerRegistry()
    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(_env("evt_noh", etype="orphan.type"))
    await async_db.commit()

    d = OutboxDispatcher(async_db, registry)
    await d.run_once(batch_limit=10)
    await async_db.commit()

    assert await _status(out, row.id) == "done"


@pytest.mark.asyncio
async def test_registered_event_version_mismatch_marks_failed_without_handler(async_db) -> None:
    registry = OutboxHandlerRegistry()
    seen: list[str] = []

    def h(_s, row: EventOutbox) -> None:
        seen.append(row.event_id)

    registry.register("run.created", "versioned_consumer", h)
    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(
        DomainEventEnvelope(
            event_id="evt_bad_version",
            event_type="run.created",
            event_version="999",
            occurred_at=datetime(2025, 3, 23, 10, 0, 0, tzinfo=UTC),
            payload={"x": 1},
        )
    )
    await async_db.commit()

    d = OutboxDispatcher(async_db, registry)
    await d.run_once(batch_limit=10)
    await async_db.commit()

    refreshed = await out.get(row.id)
    assert refreshed is not None
    assert seen == []
    assert refreshed.status == "failed"
    assert "event_version" in (refreshed.last_error or "")


@pytest.mark.asyncio
async def test_unknown_event_type_keeps_compatibility_path(async_db) -> None:
    registry = OutboxHandlerRegistry()
    out = OutboxRepository(async_db)
    row = out.enqueue_from_envelope(_env("evt_unknown_compat", etype="custom.compat"))
    await async_db.commit()

    d = OutboxDispatcher(async_db, registry)
    await d.run_once(batch_limit=10)
    await async_db.commit()

    assert await _status(out, row.id) == "done"


@pytest.mark.asyncio
async def test_dispatcher_continues_w3c_parent_trace(async_db) -> None:
    registry = OutboxHandlerRegistry()
    observed_trace_ids: list[int] = []

    def handler(_session, _row) -> None:
        observed_trace_ids.append(trace.get_current_span().get_span_context().trace_id)

    registry.register("run.created", "trace_consumer", handler)
    out = OutboxRepository(async_db)
    out.enqueue_from_envelope(
        _env("evt_trace_dispatch"),
        headers_json={
            "traceparent": (
                "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01"
            )
        },
    )
    await async_db.commit()

    provider = TracerProvider()
    dispatcher = OutboxDispatcher(
        async_db,
        registry,
        tracer=provider.get_tracer("test.outbox"),
    )
    await dispatcher.run_once(batch_limit=10)

    assert observed_trace_ids == [int("1234567890abcdef1234567890abcdef", 16)]
