"""test_event_bus

Unit tests for in-memory event bus.
"""

import pytest

from app.kernel.events import InMemoryEventBus


@pytest.mark.asyncio
async def test_event_bus_filters_and_unsubscribe():
    """Event bus dispatches by type and predicate, and supports unsubscribe."""
    bus = InMemoryEventBus()
    received = []

    async def handler(event):
        received.append(event)

    sub_id = await bus.subscribe(
        handler,
        event_type="run.updated",
        predicate=lambda e: e.payload.get("status") == "succeeded",
    )

    await bus.publish(bus.create_event(event_type="run.created", payload={"status": "queued"}))
    await bus.publish(bus.create_event(event_type="run.updated", payload={"status": "failed"}))
    await bus.publish(bus.create_event(event_type="run.updated", payload={"status": "succeeded"}))

    assert len(received) == 1
    assert received[0].payload["status"] == "succeeded"

    await bus.unsubscribe(sub_id)
    await bus.publish(bus.create_event(event_type="run.updated", payload={"status": "succeeded"}))
    assert len(received) == 1


def test_event_bus_publish_sync():
    """publish_sync works in sync contexts."""
    bus = InMemoryEventBus()
    received = []

    def handler(event):
        received.append(event)

    import asyncio
    asyncio.run(bus.subscribe(handler, event_type="run.updated"))

    event = bus.create_event(event_type="run.updated", payload={"status": "succeeded"})
    bus.publish_sync(event)
    assert len(received) == 1
