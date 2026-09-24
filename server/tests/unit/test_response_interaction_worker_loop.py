"""One poller feeds up to ``concurrency`` executions at once.

The loop is measured through stubbed ``claim`` / ``execute_claimed`` so the
tests are about scheduling: how many executions overlap, how fast a backlog
drains, how often an idle loop polls, and what cancellation leaves behind.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.wiring.response_interaction_worker import GlobalResponseInteractionWorker


class _Claimed:
    def __init__(self, index: int) -> None:
        self.id = f"pk_{index}"
        self.interaction_id = f"interaction_{index}"


class _Stats:
    def __init__(self) -> None:
        self.active = 0
        self.peak = 0
        self.claims = 0
        self.done: list[str] = []


def _stubbed_worker(backlog: list[_Claimed], *, execute_seconds: float) -> tuple[GlobalResponseInteractionWorker, _Stats]:
    worker = GlobalResponseInteractionWorker(db_factory=lambda: None)  # type: ignore[arg-type,return-value]
    stats = _Stats()

    async def claim() -> _Claimed | None:
        stats.claims += 1
        return backlog.pop(0) if backlog else None

    async def execute_claimed(interaction: _Claimed) -> _Claimed:
        stats.active += 1
        stats.peak = max(stats.peak, stats.active)
        try:
            await asyncio.sleep(execute_seconds)
        finally:
            stats.active -= 1
        stats.done.append(interaction.interaction_id)
        return interaction

    worker.claim = claim  # type: ignore[method-assign]
    worker.execute_claimed = execute_claimed  # type: ignore[method-assign]
    return worker, stats


async def _no_release(_interactions) -> None:
    return None


async def _run_for(worker: GlobalResponseInteractionWorker, seconds: float, **kwargs) -> None:
    task = asyncio.create_task(worker.run_loop(**kwargs))
    await asyncio.sleep(seconds)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_executions_overlap_up_to_the_concurrency_bound() -> None:
    worker, stats = _stubbed_worker([_Claimed(i) for i in range(6)], execute_seconds=0.05)

    await _run_for(worker, 0.4, poll_interval=0.01, concurrency=3)

    assert len(stats.done) == 6
    assert stats.peak == 3


@pytest.mark.asyncio
async def test_the_default_runs_one_execution_at_a_time() -> None:
    worker, stats = _stubbed_worker([_Claimed(i) for i in range(4)], execute_seconds=0.02)

    await _run_for(worker, 0.3, poll_interval=0.01)

    assert len(stats.done) == 4
    assert stats.peak == 1


@pytest.mark.asyncio
async def test_a_backlog_drains_without_waiting_out_the_poll_interval() -> None:
    # Six rows, three slots, 50ms each: two rounds, so ~100ms. A loop that
    # slept the interval between claims would need six seconds.
    worker, stats = _stubbed_worker([_Claimed(i) for i in range(6)], execute_seconds=0.05)
    started = time.perf_counter()
    task = asyncio.create_task(worker.run_loop(poll_interval=1.0, concurrency=3))
    while len(stats.done) < 6 and time.perf_counter() - started < 2.0:
        await asyncio.sleep(0.01)
    elapsed = time.perf_counter() - started
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(stats.done) == 6
    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_an_idle_loop_polls_once_per_interval_regardless_of_slots() -> None:
    worker, stats = _stubbed_worker([], execute_seconds=0.0)

    await _run_for(worker, 0.3, poll_interval=0.05, concurrency=8)

    # ~6 polls in 300ms at one per 50ms; eight slots must not mean eight polls each.
    assert 3 <= stats.claims <= 10


@pytest.mark.asyncio
async def test_cancelling_the_loop_cancels_in_flight_executions() -> None:
    worker, stats = _stubbed_worker([_Claimed(i) for i in range(3)], execute_seconds=10.0)
    worker._release_claims = _no_release  # type: ignore[method-assign]
    # No grace: this test is about cancellation reaching the executions.
    task = asyncio.create_task(worker.run_loop(poll_interval=0.01, concurrency=3, drain_seconds=0))
    await asyncio.sleep(0.1)
    assert stats.active == 3

    task.cancel()
    started = time.perf_counter()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert time.perf_counter() - started < 1.0
    assert stats.active == 0
    assert stats.done == []


def test_concurrency_is_capped_below_the_connection_pool(monkeypatch) -> None:
    from app.wiring import response_interaction_worker as module

    monkeypatch.setattr(module.settings, "database_pool_size", 10)
    monkeypatch.setattr(module.settings, "database_max_overflow", 20)

    assert module.bounded_concurrency(16) == 16
    assert module.bounded_concurrency(64) == 26
    assert module.bounded_concurrency(0) == 1


@pytest.mark.asyncio
async def test_a_claim_announcement_cuts_the_idle_wait_short() -> None:
    # Ten seconds between polls; the wake-up must make the loop claim now.
    worker, stats = _stubbed_worker([], execute_seconds=0.0)
    wake = asyncio.Event()
    task = asyncio.create_task(worker.run_loop(poll_interval=10.0, concurrency=2, wake=wake))
    await asyncio.sleep(0.05)
    claims_before = stats.claims

    wake.set()
    await asyncio.sleep(0.05)

    assert stats.claims == claims_before + 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
