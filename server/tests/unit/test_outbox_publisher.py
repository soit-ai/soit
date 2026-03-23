"""Unit tests for OutboxPublisher thin wrapper."""

from __future__ import annotations

from datetime import datetime, timezone

from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher


def test_publisher_delegates_enqueue_to_repository(db) -> None:
    env = DomainEventEnvelope(
        event_id="evt_pub",
        event_type="t",
        occurred_at=datetime(2025, 3, 23, 12, 0, 0, tzinfo=timezone.utc),
        payload={"a": 1},
    )
    repo = OutboxRepository(db)
    pub = OutboxPublisher(repo)
    row = pub.publish(env, headers_json={"h": "1"})
    db.commit()
    loaded = repo.get(row.id)
    assert loaded is not None
    assert loaded.event_id == "evt_pub"
    assert loaded.headers_json == {"h": "1"}
