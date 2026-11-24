"""PostgreSQL contract: a consumer's database error does not wedge the outbox.

On PostgreSQL a failed statement aborts the surrounding transaction. When a
consumer ran directly in the dispatcher's batch transaction, the retry
bookkeeping after its error failed too, the whole batch rolled back without
counting the attempt, and the same row came back first on every tick. SQLite
does not abort a transaction on a failed statement, so this has no SQLite twin.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.events.dispatcher import OutboxDispatcherService
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.registry import OutboxHandlerRegistry
from app.kernel.runtime.db.models.events import EventConsumerCheckpoint, EventOutbox

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture
async def postgres_engine() -> AsyncEngine:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_async_engine(database_url, connect_args={"options": "-c timezone=UTC"})
    try:
        yield engine
    finally:
        await engine.dispose()


def _session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_consumer_database_error_is_counted_and_the_batch_continues(
    postgres_engine: AsyncEngine,
) -> None:
    token = uuid4().hex
    tenant_id = f"pg-tenant-{token}"
    event_type = f"pg.outbox.{token}"
    poison_event = f"evt-poison-{token}"
    healthy_event = f"evt-healthy-{token}"
    long_ago = datetime(2000, 1, 1, tzinfo=UTC)

    delivered: list[str] = []

    async def consumer(db: AsyncSession, row: EventOutbox) -> None:
        if row.event_id == poison_event:
            await db.exec(text("SELECT 1 / 0"))  # type: ignore[call-overload]
        delivered.append(row.event_id)

    registry = OutboxHandlerRegistry()
    registry.register(event_type, f"consumer-{token}", consumer)

    async with _session(postgres_engine) as db:
        repo = OutboxRepository(db)
        ids = []
        # Queued earlier than anything else so this tick picks them up first.
        for offset, event_id in enumerate((poison_event, healthy_event)):
            row = repo.enqueue_from_envelope(
                DomainEventEnvelope(
                    event_id=event_id,
                    event_type=event_type,
                    tenant_id=tenant_id,
                    occurred_at=long_ago,
                    payload={},
                ),
                available_at=long_ago + timedelta(seconds=offset),
            )
            ids.append(row.id)
        await db.commit()
    poison_id, healthy_id = ids

    try:
        service = OutboxDispatcherService(
            registry,
            db_factory=lambda: _session(postgres_engine),
            batch_limit=2,
        )
        assert await service.run_once() == 2

        async with _session(postgres_engine) as db:
            repo = OutboxRepository(db)
            poisoned = await repo.get(poison_id)
            healthy = await repo.get(healthy_id)
        assert delivered == [healthy_event]
        assert healthy is not None and healthy.status == "done"
        assert poisoned is not None
        assert poisoned.status == "pending"
        assert poisoned.attempt_count == 1
        assert "division by zero" in (poisoned.last_error or "")
    finally:
        async with _session(postgres_engine) as db:
            await db.exec(delete(EventOutbox).where(EventOutbox.tenant_id == tenant_id))  # type: ignore[call-overload]
            await db.exec(
                delete(EventConsumerCheckpoint).where(  # type: ignore[call-overload]
                    EventConsumerCheckpoint.consumer_name == f"consumer-{token}"
                )
            )
            await db.commit()


@pytest.mark.asyncio
async def test_failed_consumer_releases_its_idempotency_slot_for_the_retry(
    postgres_engine: AsyncEngine,
) -> None:
    """Notification consumers claim a slot before they deliver. If the slot
    outlived a failed delivery, the retry would find it, return early and the
    notification would be lost."""

    from app.kernel.events.checkpoint import try_claim_consumer_slot

    token = uuid4().hex
    tenant_id = f"pg-tenant-{token}"
    event_type = f"pg.outbox.{token}"
    slot_consumer = f"slot-{token}"
    long_ago = datetime(2000, 1, 1, tzinfo=UTC)
    claims: list[bool] = []

    async def deliver(db: AsyncSession, row: EventOutbox) -> None:
        claims.append(await try_claim_consumer_slot(db, consumer_name=slot_consumer, event_id=row.event_id))
        if len(claims) == 1:
            raise RuntimeError("delivery failed")

    registry = OutboxHandlerRegistry()
    registry.register(event_type, f"consumer-{token}", deliver)

    async with _session(postgres_engine) as db:
        row = OutboxRepository(db).enqueue_from_envelope(
            DomainEventEnvelope(
                event_id=f"evt-{token}",
                event_type=event_type,
                tenant_id=tenant_id,
                occurred_at=long_ago,
                payload={},
            ),
            available_at=long_ago,
        )
        await db.commit()
        row_id = row.id

    try:
        service = OutboxDispatcherService(
            registry,
            db_factory=lambda: _session(postgres_engine),
            batch_limit=1,
        )
        assert await service.run_once() == 1
        async with _session(postgres_engine) as db:
            retried = await OutboxRepository(db).get(row_id)
            assert retried is not None and retried.status == "pending"
            retried.available_at = long_ago
            await db.commit()

        assert await service.run_once() == 1
        async with _session(postgres_engine) as db:
            done = await OutboxRepository(db).get(row_id)
        assert claims == [True, True]
        assert done is not None and done.status == "done"
    finally:
        async with _session(postgres_engine) as db:
            await db.exec(delete(EventOutbox).where(EventOutbox.tenant_id == tenant_id))  # type: ignore[call-overload]
            await db.exec(
                delete(EventConsumerCheckpoint).where(  # type: ignore[call-overload]
                    EventConsumerCheckpoint.consumer_name.in_([slot_consumer, f"consumer-{token}"])  # type: ignore[attr-defined]
                )
            )
            await db.commit()
