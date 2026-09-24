"""The worker reports queue wait, in-flight count, execution time and claim kind.

These are the numbers a capacity decision needs in production: how long
accepted interactions wait for a slot, how many slots are busy, and how
often a claim is a recovery of an expired lease rather than fresh work.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from prometheus_client import REGISTRY

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.responses import ResponseInteraction
from app.wiring.response_interaction_worker import GlobalResponseInteractionWorker


def _sample(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels or None) or 0.0


def _interaction(*, age_seconds: float, attempt_count: int) -> ResponseInteraction:
    return ResponseInteraction(
        id=f"pk_{attempt_count}",
        tenant_id="t",
        workspace_id="w",
        interaction_id=f"interaction_{attempt_count}",
        thread_id="thread",
        request_hash=f"hash_{attempt_count}",
        status="running",
        attempt_count=attempt_count,
        created_at=utc_now() - timedelta(seconds=age_seconds),
    )


@pytest.mark.asyncio
async def test_a_completed_execution_reports_wait_duration_and_a_fresh_claim(async_db, monkeypatch) -> None:
    worker = GlobalResponseInteractionWorker(db_factory=lambda: async_db, heartbeat_interval_seconds=60)
    seen_in_flight: list[float] = []

    async def fake_execute(_db, _interaction) -> None:
        seen_in_flight.append(_sample("soit_interactions_in_flight"))

    monkeypatch.setattr(worker, "_execute", fake_execute)
    waits_before = _sample("soit_interaction_queue_wait_seconds_count")
    wait_sum_before = _sample("soit_interaction_queue_wait_seconds_sum")
    done_before = _sample("soit_interaction_execution_seconds_count", outcome="succeeded")
    fresh_before = _sample("soit_interaction_claims_total", kind="fresh")

    await worker.execute_claimed(_interaction(age_seconds=3.0, attempt_count=1))

    assert _sample("soit_interaction_queue_wait_seconds_count") == waits_before + 1
    assert _sample("soit_interaction_queue_wait_seconds_sum") - wait_sum_before == pytest.approx(3.0, abs=1.0)
    assert seen_in_flight == [1.0]
    assert _sample("soit_interactions_in_flight") == 0.0
    assert _sample("soit_interaction_execution_seconds_count", outcome="succeeded") == done_before + 1
    assert _sample("soit_interaction_claims_total", kind="fresh") == fresh_before + 1


@pytest.mark.asyncio
async def test_a_failing_execution_and_a_reclaim_are_reported_as_such(async_db, monkeypatch) -> None:
    worker = GlobalResponseInteractionWorker(db_factory=lambda: async_db, heartbeat_interval_seconds=60)

    async def failing_execute(_db, _interaction) -> None:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(worker, "_execute", failing_execute)
    failed_before = _sample("soit_interaction_execution_seconds_count", outcome="failed")
    reclaimed_before = _sample("soit_interaction_claims_total", kind="reclaimed")

    await worker.execute_claimed(_interaction(age_seconds=0.0, attempt_count=2))

    assert _sample("soit_interaction_execution_seconds_count", outcome="failed") == failed_before + 1
    assert _sample("soit_interaction_claims_total", kind="reclaimed") == reclaimed_before + 1
    assert _sample("soit_interactions_in_flight") == 0.0
