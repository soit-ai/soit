"""Unit tests for OutboxRepository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository


def _env(event_id: str = "evt_a3_1") -> DomainEventEnvelope:
    return DomainEventEnvelope(
        event_id=event_id,
        event_type="run.created",
        occurred_at=datetime(2025, 3, 23, 10, 0, 0, tzinfo=timezone.utc),
        payload={"k": "v"},
    )


def test_enqueue_flush_list_pending_due(db) -> None:
    repo = OutboxRepository(db)
    row = repo.enqueue_from_envelope(_env())
    db.commit()
    before = datetime.now(timezone.utc) + timedelta(minutes=1)
    pending = repo.list_pending_due(before=before, limit=10)
    assert len(pending) == 1
    assert pending[0].id == row.id
    assert pending[0].status == "pending"
    assert pending[0].payload_json == {"k": "v"}


def test_try_claim_atomic(db) -> None:
    repo = OutboxRepository(db)
    row = repo.enqueue_from_envelope(_env("evt_claim"))
    db.commit()
    assert repo.try_claim(row.id) is True
    db.commit()
    loaded = repo.get(row.id)
    assert loaded is not None
    assert loaded.status == "processing"
    assert repo.try_claim(row.id) is False


def test_mark_done_sets_processed_at(db) -> None:
    repo = OutboxRepository(db)
    row = repo.enqueue_from_envelope(_env("evt_done"))
    db.commit()
    assert repo.try_claim(row.id) is True
    repo.mark_done(row.id)
    db.commit()
    loaded = repo.get(row.id)
    assert loaded is not None
    assert loaded.status == "done"
    assert loaded.processed_at is not None
