"""Retention of the outbox transport tables."""

from datetime import timedelta

import pytest
from sqlmodel import select

from app.kernel.commons.time import utc_now
from app.kernel.events.retention import OutboxRetentionService
from app.kernel.runtime.db.models.events import EventConsumerCheckpoint, EventOutbox

pytestmark = pytest.mark.asyncio


def _row(event_id: str, *, status: str, processed_days_ago: int | None) -> EventOutbox:
    return EventOutbox(
        event_id=event_id,
        event_type="run.created",
        idempotency_key=f"idem_{event_id}",
        payload_json={},
        status=status,
        processed_at=(
            utc_now() - timedelta(days=processed_days_ago)
            if processed_days_ago is not None
            else None
        ),
    )


async def _seed(async_db) -> None:
    async_db.add_all(
        [
            _row("evt_old_done", status="done", processed_days_ago=10),
            _row("evt_recent_done", status="done", processed_days_ago=1),
            _row("evt_old_failed", status="failed", processed_days_ago=10),
            _row("evt_pending", status="pending", processed_days_ago=None),
            EventConsumerCheckpoint(
                consumer_name="observe.run",
                event_id="evt_old_done",
                processed_at=utc_now() - timedelta(days=10),
            ),
            EventConsumerCheckpoint(
                consumer_name="observe.run",
                event_id="evt_recent_done",
                processed_at=utc_now() - timedelta(days=1),
            ),
        ]
    )
    await async_db.commit()


async def test_purge_removes_only_dispatched_rows_past_the_window(async_db):
    await _seed(async_db)
    service = OutboxRetentionService(lambda: async_db, retention_days=7, batch_size=1)

    outcome = await service.purge_once()

    assert outcome.outbox_rows == 1
    assert outcome.checkpoint_rows == 1
    remaining = sorted((await async_db.exec(select(EventOutbox.event_id))).all())
    assert remaining == ["evt_old_failed", "evt_pending", "evt_recent_done"]
    checkpoints = (await async_db.exec(select(EventConsumerCheckpoint.event_id))).all()
    assert checkpoints == ["evt_recent_done"]


async def test_purge_is_a_no_op_when_nothing_is_old_enough(async_db):
    await _seed(async_db)
    service = OutboxRetentionService(lambda: async_db, retention_days=30)

    outcome = await service.purge_once()

    assert outcome == type(outcome)(outbox_rows=0, checkpoint_rows=0)
    assert len((await async_db.exec(select(EventOutbox.id))).all()) == 4


def test_retention_window_must_be_positive():
    with pytest.raises(ValueError):
        OutboxRetentionService(lambda: None, retention_days=0)  # type: ignore[arg-type]
