"""Unit tests for consumer checkpoint idempotency."""

from __future__ import annotations

import pytest

from app.kernel.events.checkpoint import ConsumerCheckpointRepository


@pytest.mark.asyncio
async def test_is_processed_false_until_recorded(async_db) -> None:
    repo = ConsumerCheckpointRepository(async_db)
    assert await repo.is_processed("c1", "evt1") is False


@pytest.mark.asyncio
async def test_try_record_success_idempotent(async_db) -> None:
    repo = ConsumerCheckpointRepository(async_db)
    assert await repo.try_record_success("c1", "evt1", result="ok") is True
    await async_db.commit()
    assert await repo.is_processed("c1", "evt1") is True
    assert await repo.try_record_success("c1", "evt1", result="ok") is False
    await async_db.commit()
    assert await repo.is_processed("c1", "evt1") is True


@pytest.mark.asyncio
async def test_duplicate_in_same_transaction_rolls_back_only_savepoint(async_db) -> None:
    """Outer transaction stays usable after duplicate checkpoint insert."""
    repo = ConsumerCheckpointRepository(async_db)
    assert await repo.try_record_success("c2", "evt2") is True
    assert await repo.try_record_success("c2", "evt2") is False
    assert await repo.try_record_success("c2", "evt2") is False
    await async_db.commit()
    assert await repo.is_processed("c2", "evt2") is True
