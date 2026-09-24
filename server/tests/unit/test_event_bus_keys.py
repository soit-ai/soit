"""Keyed subscriptions are found by lookup, not by testing every subscription.

In memory the key selects a bucket; over Redis it selects a channel, so a
process only receives the keyed events it asked for and dispatches each by
lookup. Keyless subscriptions keep seeing everything, as before.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app.kernel.events.bus import InMemoryEventBus
from app.kernel.events.redis_bus import RedisEventBus


@pytest.mark.asyncio
async def test_in_memory_keyed_subscriptions_only_see_their_key() -> None:
    bus = InMemoryEventBus()
    mine: list[str] = []
    everything: list[str] = []

    async def take_mine(event) -> None:
        mine.append(event.id)

    async def take_all(event) -> None:
        everything.append(event.id)

    keyed = await bus.subscribe(take_mine, event_type="response.event.appended", key="response:a")
    await bus.subscribe(take_all, event_type="response.event.appended")

    for key in ("response:a", "response:b", None):
        await bus.publish(bus.create_event(event_type="response.event.appended", key=key))

    assert len(mine) == 1
    assert len(everything) == 3

    await bus.unsubscribe(keyed)
    await bus.publish(bus.create_event(event_type="response.event.appended", key="response:a"))
    assert len(mine) == 1


class _FakePubSub:
    def __init__(self) -> None:
        self.channels: set[str] = set()
        self.subscribed_calls: list[str] = []
        self.unsubscribed_calls: list[str] = []
        self.inbox: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def subscribe(self, channel: str) -> None:
        self.channels.add(channel)
        self.subscribed_calls.append(channel)

    async def unsubscribe(self, channel: str) -> None:
        self.channels.discard(channel)
        self.unsubscribed_calls.append(channel)

    async def listen(self):
        while True:
            message = await self.inbox.get()
            if message is None:
                return
            yield message

    async def close(self) -> None:
        await self.inbox.put(None)


class _FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []
        self.pubsub_instance = _FakePubSub()

    async def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, message))
        return 1

    def pubsub(self) -> _FakePubSub:
        return self.pubsub_instance

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_redis_keyed_subscriptions_use_their_own_channel_and_dispatch_by_lookup() -> None:
    client = _FakeRedis()
    bus = RedisEventBus("redis://unused", "soit:events", client=client)
    mine: list[str] = []
    everything: list[str] = []

    async def take_mine(event) -> None:
        mine.append(event.id)

    async def take_all(event) -> None:
        everything.append(event.id)

    keyed = await bus.subscribe(take_mine, key="response:a")
    assert client.pubsub_instance.subscribed_calls == ["soit:events:response:a"]
    await bus.subscribe(take_all)
    assert client.pubsub_instance.subscribed_calls == ["soit:events:response:a", "soit:events"]

    # Publishing a keyed event writes it to the base channel and the key's channel.
    event = bus_event = InMemoryEventBus().create_event(event_type="response.event.appended", key="response:a")
    await bus.publish(event)
    assert [channel for channel, _ in client.published] == ["soit:events", "soit:events:response:a"]

    # Delivering what Redis would fan back: each channel reaches its own kind of subscriber.
    wire = json.loads(client.published[0][1])
    for channel in ("soit:events", "soit:events:response:a"):
        await client.pubsub_instance.inbox.put({"type": "message", "channel": channel.encode(), "data": json.dumps(wire).encode()})
    await asyncio.sleep(0.05)
    assert mine == [bus_event.id]
    assert everything == [bus_event.id]

    # The last keyed subscription for a key drops that key's channel.
    await bus.unsubscribe(keyed)
    assert client.pubsub_instance.unsubscribed_calls == ["soit:events:response:a"]
    await bus.close()
