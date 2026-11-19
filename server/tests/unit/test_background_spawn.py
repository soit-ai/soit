"""spawn keeps fire-and-forget tasks alive and reports their failures."""

from __future__ import annotations

import asyncio
import gc
import logging

import pytest

from app.kernel.commons import background


@pytest.mark.asyncio
async def test_a_spawned_task_survives_garbage_collection_and_finishes() -> None:
    done = asyncio.Event()

    async def work() -> None:
        await asyncio.sleep(0.01)
        done.set()

    background.spawn(work())
    gc.collect()

    await asyncio.wait_for(done.wait(), timeout=1)
    await asyncio.sleep(0)
    assert not background._running


@pytest.mark.asyncio
async def test_a_failure_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    async def fail() -> None:
        raise RuntimeError("boom")

    with caplog.at_level(logging.WARNING, logger="app.kernel.commons.background"):
        task = background.spawn(fail())
        with pytest.raises(RuntimeError):
            await task
        await asyncio.sleep(0)

    assert "Background task failed" in caplog.text
