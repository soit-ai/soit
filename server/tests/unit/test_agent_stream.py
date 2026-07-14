"""Tests for Agent streaming SSE support."""

import pytest

from app.modules.agent.runtime.emitter import QueueEmitter


@pytest.mark.asyncio
async def test_queue_emitter_collects_events():
    """QueueEmitter pushes events to an asyncio queue."""
    emitter = QueueEmitter()

    await emitter("agent.run.started", {"run_id": "r1"})
    await emitter("agent.plan.started", {"iteration": 1})
    await emitter.done()

    events = []
    while True:
        item = await emitter.queue.get()
        if item is None:
            break
        events.append(item)

    assert len(events) == 2
    assert events[0] == ("agent.run.started", {"run_id": "r1"})
    assert events[1] == ("agent.plan.started", {"iteration": 1})


@pytest.mark.asyncio
async def test_queue_emitter_done_signal():
    """done() signals the consumer to stop."""
    emitter = QueueEmitter()
    await emitter.done()

    item = await emitter.queue.get()
    assert item is None
