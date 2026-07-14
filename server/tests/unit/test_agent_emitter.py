"""Tests for EventEmitter protocol and noop implementation."""

import pytest

from app.modules.agent.runtime.emitter import CollectingEmitter, noop_emitter


@pytest.mark.asyncio
async def test_noop_emitter_does_nothing():
    """noop_emitter should not raise."""
    await noop_emitter("test.event", {"key": "value"})


@pytest.mark.asyncio
async def test_collecting_emitter():
    """CollectingEmitter records events for testing."""
    emitter = CollectingEmitter()
    await emitter("event.one", {"a": 1})
    await emitter("event.two", {"b": 2})
    assert len(emitter.events) == 2
    assert emitter.events[0] == ("event.one", {"a": 1})
    assert emitter.events[1] == ("event.two", {"b": 2})
