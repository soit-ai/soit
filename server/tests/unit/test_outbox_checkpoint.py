"""Unit tests for consumer checkpoint idempotency."""

from __future__ import annotations

from app.kernel.events.checkpoint import ConsumerCheckpointRepository


def test_is_processed_false_until_recorded(db) -> None:
    repo = ConsumerCheckpointRepository(db)
    assert repo.is_processed("c1", "evt1") is False


def test_try_record_success_idempotent(db) -> None:
    repo = ConsumerCheckpointRepository(db)
    assert repo.try_record_success("c1", "evt1", result="ok") is True
    db.commit()
    assert repo.is_processed("c1", "evt1") is True
    assert repo.try_record_success("c1", "evt1", result="ok") is False
    db.commit()
    assert repo.is_processed("c1", "evt1") is True


def test_duplicate_in_same_transaction_rolls_back_only_savepoint(db) -> None:
    """Outer transaction stays usable after duplicate checkpoint insert."""
    repo = ConsumerCheckpointRepository(db)
    assert repo.try_record_success("c2", "evt2") is True
    assert repo.try_record_success("c2", "evt2") is False
    assert repo.try_record_success("c2", "evt2") is False
    db.commit()
    assert repo.is_processed("c2", "evt2") is True
