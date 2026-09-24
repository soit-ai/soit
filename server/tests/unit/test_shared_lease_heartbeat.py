"""All of a worker's leases renew in one statement, and each outcome is reported per row."""

from __future__ import annotations

import asyncio
from datetime import UTC, timedelta

import pytest
from sqlalchemy import event

from app.kernel.commons.time import utc_now
from app.kernel.runtime.common import lease
from app.kernel.runtime.db.models.responses import ResponseInteraction
from app.wiring.response_interaction_worker import SharedLeaseHeartbeat

WORKER = "worker-shared"


def _claimed(index: int, *, owner: str = WORKER, attempt_count: int = 1, status: str = "running") -> ResponseInteraction:
    return ResponseInteraction(
        id=f"pk_shared_{index}",
        tenant_id="t",
        workspace_id="w",
        interaction_id=f"interaction_shared_{index}",
        thread_id="thread",
        request_hash=f"hash_shared_{index}",
        status=status,
        lease_owner=owner,
        lease_expires_at=utc_now() + timedelta(seconds=1),
        attempt_count=attempt_count,
    )


@pytest.fixture
def statements(async_db) -> list[str]:
    seen: list[str] = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        seen.append(statement)

    engine = async_db.bind.sync_engine
    event.listen(engine, "before_cursor_execute", record)
    yield seen
    event.remove(engine, "before_cursor_execute", record)


@pytest.mark.asyncio
async def test_renew_leases_reports_each_row_and_extends_the_held_ones(async_db) -> None:
    held = _claimed(1)
    taken_over = _claimed(2, owner="worker-other", attempt_count=2)
    finished = _claimed(3, status="succeeded")
    for row in (held, taken_over, finished):
        async_db.add(row)
    await async_db.commit()
    before = held.lease_expires_at

    outcomes = await lease.renew_leases(
        async_db,
        ResponseInteraction,
        {held.id: 1, taken_over.id: 1, finished.id: 1, "pk_shared_missing": 1},
        worker_id=WORKER,
        lease_seconds=90,
    )

    assert outcomes == {
        held.id: lease.LeaseRenewal.RENEWED,
        taken_over.id: lease.LeaseRenewal.LOST,
        finished.id: lease.LeaseRenewal.TERMINAL,
        "pk_shared_missing": lease.LeaseRenewal.LOST,
    }
    await async_db.refresh(held)
    renewed_until = held.lease_expires_at
    if renewed_until.tzinfo is None:  # SQLite hands the column back naive
        renewed_until = renewed_until.replace(tzinfo=UTC)
    assert renewed_until > before


@pytest.mark.asyncio
async def test_one_round_renews_every_tracked_lease_in_one_update(async_db, statements) -> None:
    rows = [_claimed(i) for i in range(10, 16)]
    for row in rows:
        async_db.add(row)
    await async_db.commit()
    heartbeat = SharedLeaseHeartbeat(
        lambda: async_db, worker_id=WORKER, lease_seconds=90, interval_seconds=60
    )
    lost_events = [heartbeat.track(row.id, 1) for row in rows]
    statements.clear()

    await heartbeat.renew_once()

    updates = [s for s in statements if s.lstrip().upper().startswith("UPDATE")]
    assert len(updates) == 1
    assert not any(e.is_set() for e in lost_events)
    for row in rows:
        heartbeat.untrack(row.id)


@pytest.mark.asyncio
async def test_a_reclaimed_lease_is_signalled_and_dropped(async_db) -> None:
    row = _claimed(20)
    async_db.add(row)
    await async_db.commit()
    heartbeat = SharedLeaseHeartbeat(
        lambda: async_db, worker_id=WORKER, lease_seconds=90, interval_seconds=0.01
    )
    lost = heartbeat.track(row.id, 1)

    row.lease_owner = "worker-replacement"
    row.attempt_count = 2
    async_db.add(row)
    await async_db.commit()

    await asyncio.wait_for(lost.wait(), timeout=1)
    assert row.id not in heartbeat._claims
