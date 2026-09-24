"""A stopping worker lets in-flight executions finish, then releases what did not.

Before this a cancelled execution kept its claim until the lease expired,
so a deploy left interactions untouched for the lease length; releasing the
claim hands them to the next replica at once.
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


def _worker(backlog: list[_Claimed], durations: dict[str, float]):
    worker = GlobalResponseInteractionWorker(db_factory=lambda: None)  # type: ignore[arg-type,return-value]
    done: list[str] = []
    released: list[str] = []
    active = {"count": 0}

    async def claim() -> _Claimed | None:
        return backlog.pop(0) if backlog else None

    async def execute_claimed(interaction: _Claimed) -> _Claimed:
        active["count"] += 1
        try:
            await asyncio.sleep(durations[interaction.id])
        finally:
            active["count"] -= 1
        done.append(interaction.interaction_id)
        return interaction

    async def release(interactions) -> None:
        released.extend(i.id for i in interactions)

    worker.claim = claim  # type: ignore[method-assign]
    worker.execute_claimed = execute_claimed  # type: ignore[method-assign]
    worker._release_claims = release  # type: ignore[method-assign]
    return worker, done, released, active


@pytest.mark.asyncio
async def test_stopping_lets_executions_finish_within_the_grace_and_releases_the_rest() -> None:
    worker, done, released, active = _worker([_Claimed(1), _Claimed(2)], {"pk_1": 0.05, "pk_2": 10.0})
    task = asyncio.create_task(worker.run_loop(poll_interval=0.01, concurrency=2, drain_seconds=0.5))
    await asyncio.sleep(0.02)
    assert active["count"] == 2

    started = time.perf_counter()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # The short one finished inside the grace; the long one was cut and released.
    assert done == ["interaction_1"]
    assert released == ["pk_2"]
    assert active["count"] == 0
    assert 0.4 < time.perf_counter() - started < 2.0


@pytest.mark.asyncio
async def test_a_zero_grace_releases_everything_at_once() -> None:
    worker, done, released, _ = _worker([_Claimed(3)], {"pk_3": 10.0})
    task = asyncio.create_task(worker.run_loop(poll_interval=0.01, concurrency=1, drain_seconds=0))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert released == ["pk_3"]
    assert done == []
