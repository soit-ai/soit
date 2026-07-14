"""Unit tests for OutboxRepository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository


def _env(event_id: str = "evt_a3_1") -> DomainEventEnvelope:
    return DomainEventEnvelope(
        event_id=event_id,
        event_type="run.created",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        occurred_at=datetime(2025, 3, 23, 10, 0, 0, tzinfo=UTC),
        payload={"k": "v"},
    )


def test_enqueue_flush_list_pending_due(db) -> None:
    repo = OutboxRepository(db)
    row = repo.enqueue_from_envelope(_env())
    db.commit()
    before = datetime.now(UTC) + timedelta(minutes=1)
    pending = repo.list_pending_due(before=before, limit=10)
    assert len(pending) == 1
    assert pending[0].id == row.id
    assert pending[0].status == "pending"
    assert pending[0].payload_json == {"k": "v"}
    assert pending[0].workspace_id == "workspace-a"
    assert pending[0].idempotency_key == "evt_a3_1"


def test_try_claim_atomic(db) -> None:
    repo = OutboxRepository(db)
    row = repo.enqueue_from_envelope(_env("evt_claim"))
    db.commit()
    claimed_at = datetime.now(UTC)
    assert repo.try_claim(row.id, owner="worker-a", now=claimed_at) is True
    db.commit()
    loaded = repo.get(row.id)
    assert loaded is not None
    assert loaded.status == "processing"
    assert loaded.lock_owner == "worker-a"
    assert loaded.locked_at.replace(tzinfo=UTC) == claimed_at
    assert loaded.lock_expires_at.replace(tzinfo=UTC) == claimed_at + timedelta(seconds=60)
    assert repo.try_claim(row.id, owner="worker-b", now=claimed_at) is False


def test_expired_lease_can_be_reclaimed(db) -> None:
    repo = OutboxRepository(db)
    row = repo.enqueue_from_envelope(_env("evt_reclaim"))
    db.commit()
    claimed_at = datetime.now(UTC)
    assert repo.try_claim(row.id, owner="worker-a", now=claimed_at) is True
    db.commit()

    reclaim_at = claimed_at + timedelta(seconds=61)
    due = repo.list_pending_due(before=reclaim_at, limit=10)
    assert [candidate.id for candidate in due] == [row.id]
    assert repo.try_claim(row.id, owner="worker-b", now=reclaim_at) is True
    db.commit()

    loaded = repo.get(row.id)
    assert loaded is not None
    assert loaded.lock_owner == "worker-b"
    assert loaded.locked_at.replace(tzinfo=UTC) == reclaim_at


def test_mark_retry_applies_bounded_exponential_backoff(db) -> None:
    repo = OutboxRepository(db)
    row = repo.enqueue_from_envelope(_env("evt_backoff"))
    db.commit()
    now = datetime.now(UTC)
    assert repo.try_claim(row.id, owner="worker-a", now=now) is True

    repo.mark_retry(row.id, "temporary", now=now, base_delay_seconds=2, max_delay_seconds=5)
    db.commit()

    loaded = repo.get(row.id)
    assert loaded is not None
    assert loaded.status == "pending"
    assert loaded.attempt_count == 1
    assert loaded.available_at.replace(tzinfo=UTC) == now + timedelta(seconds=2)
    assert loaded.lock_owner is None
    assert loaded.lock_expires_at is None

    loaded.attempt_count = 10
    db.add(loaded)
    db.commit()
    repo.mark_retry(row.id, "temporary again", now=now, base_delay_seconds=2, max_delay_seconds=5)
    db.commit()
    assert repo.get(row.id).available_at.replace(tzinfo=UTC) == now + timedelta(seconds=5)


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


def test_operational_stats_report_backlog_retries_and_failures(db) -> None:
    repo = OutboxRepository(db)
    pending = repo.enqueue_from_envelope(_env("evt_stats_pending"))
    retry = repo.enqueue_from_envelope(_env("evt_stats_retry"))
    failed = repo.enqueue_from_envelope(_env("evt_stats_failed"))
    db.commit()

    now = datetime.now(UTC)
    assert repo.try_claim(retry.id, now=now) is True
    repo.mark_retry(retry.id, "temporary", now=now)
    assert repo.try_claim(failed.id, now=now) is True
    repo.mark_failed(failed.id, "permanent")
    db.commit()

    stats = repo.get_operational_stats()
    assert stats.pending_count == 2
    assert stats.retry_count == 1
    assert stats.failed_count == 1
    assert stats.oldest_pending_at is not None
    assert stats.oldest_pending_at <= pending.created_at


def test_failed_row_can_be_safely_replayed(db) -> None:
    repo = OutboxRepository(db)
    row = repo.enqueue_from_envelope(_env("evt_replay"))
    db.commit()
    assert repo.try_claim(row.id, owner="worker-a") is True
    repo.mark_failed(row.id, "poison", consumer_name="consumer-a")
    db.commit()

    replay_at = datetime.now(UTC)
    assert repo.replay_failed(row.id, now=replay_at) is True
    assert repo.replay_failed(row.id, now=replay_at) is False
    db.commit()

    loaded = repo.get(row.id)
    assert loaded is not None
    assert loaded.status == "pending"
    assert loaded.attempt_count == 0
    assert loaded.failed_consumer_name is None
    assert loaded.processed_at is None
    assert loaded.available_at.replace(tzinfo=UTC) == replay_at
