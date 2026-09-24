"""redis_bus

Redis-backed event bus for cross-instance propagation.

Keyless events travel on the base channel and reach every process that
holds a keyless subscription. Keyed events travel on ``<base>:<key>`` and
reach only the processes that subscribed to that key, where they are
dispatched by lookup. A process tailing two hundred conversations neither
receives every other process's events nor tests two hundred predicates per
event.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import redis.asyncio as redis

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.events.bus import (
    Event,
    EventBus,
    SubscriptionIndex,
    _Subscription,
    matches,
)

logger = logging.getLogger(__name__)


class RedisEventBus(EventBus):
    """Redis pubsub event bus implementation."""

    def __init__(self, redis_url: str, channel: str, *, client: Any | None = None) -> None:
        self._redis = client if client is not None else redis.from_url(redis_url, decode_responses=False)
        self._channel = channel
        self._index = SubscriptionIndex()
        self._lock = asyncio.Lock()
        self._pubsub: Any | None = None
        self._listener_task: asyncio.Task | None = None
        self._closed = False

    def _keyed_channel(self, key: str) -> str:
        return f"{self._channel}:{key}"

    async def publish(self, event: Event) -> int:
        """Publish event to Redis: the base channel, plus the key's channel when it has one."""
        payload = {
            "id": event.id,
            "type": event.type,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
            "tenant_id": event.tenant_id,
            "workspace_id": event.workspace_id,
            "run_id": event.run_id,
            "trace_id": event.trace_id,
            "key": event.key,
        }
        message = json.dumps(payload)
        try:
            await self._redis.publish(self._channel, message)
            if event.key is not None:
                await self._redis.publish(self._keyed_channel(event.key), message)
        except Exception:
            logger.exception("eventbus.redis.publish_failed", extra={"channel": self._channel})
        return 1

    async def subscribe(
        self,
        handler,
        *,
        event_type: str | None = None,
        predicate=None,
        key: str | None = None,
    ) -> str:
        """Register a handler and return subscription id."""
        subscription_id = f"sub_{generate_ulid()}"
        async with self._lock:
            first_for_key = key is not None and key not in self._index.keyed
            first_unkeyed = key is None and not self._index.unkeyed
            self._index.add(
                subscription_id,
                _Subscription(handler=handler, event_type=event_type, predicate=predicate, key=key),
            )
            pubsub = await self._ensure_pubsub()
            if first_for_key:
                await pubsub.subscribe(self._keyed_channel(key))  # type: ignore[arg-type]
            if first_unkeyed:
                await pubsub.subscribe(self._channel)
        await self._ensure_listener()
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove subscription if present, dropping its channel when it was the last."""
        async with self._lock:
            had_unkeyed = bool(self._index.unkeyed)
            released_key = self._index.remove(subscription_id)
            if self._pubsub is None:
                return
            try:
                if released_key is not None:
                    await self._pubsub.unsubscribe(self._keyed_channel(released_key))
                if had_unkeyed and not self._index.unkeyed:
                    await self._pubsub.unsubscribe(self._channel)
            except Exception:
                logger.exception("eventbus.redis.unsubscribe_failed")

    async def close(self) -> None:
        """Close listener and Redis connection."""
        self._closed = True
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
        try:
            if self._pubsub is not None:
                await self._pubsub.close()
            await self._redis.close()
        except Exception:
            pass

    async def _ensure_pubsub(self) -> Any:
        if self._pubsub is None:
            self._pubsub = self._redis.pubsub()
        return self._pubsub

    async def _ensure_listener(self) -> None:
        if self._listener_task and not self._listener_task.done():
            return
        self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        pubsub = await self._ensure_pubsub()
        try:
            async for message in pubsub.listen():
                if self._closed:
                    break
                if not message or message.get("type") != "message":
                    continue
                raw = message.get("data")
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                channel = message.get("channel")
                if isinstance(channel, bytes):
                    channel = channel.decode("utf-8")
                event = self._decode_event(raw)
                if not event:
                    continue
                await self._dispatch(event, from_base_channel=channel == self._channel)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("eventbus.redis.listen_failed", extra={"channel": self._channel})

    async def _dispatch(self, event: Event, *, from_base_channel: bool) -> None:
        # A message on the base channel is for keyless subscriptions; one on a
        # key's channel is for that key's subscriptions. A process holding both
        # kinds sees a keyed event twice on the wire and delivers each once.
        async with self._lock:
            subs = self._index.candidates(
                event,
                include_unkeyed=from_base_channel,
                include_keyed=not from_base_channel,
            )
        for sub in subs:
            if not matches(sub, event):
                continue
            result = sub.handler(event)
            if asyncio.iscoroutine(result):
                await result

    def _decode_event(self, raw: str) -> Event | None:
        try:
            payload = json.loads(raw)
        except Exception:
            return None
        created_at = payload.get("created_at")
        ts = utc_now()
        if isinstance(created_at, str):
            try:
                ts = datetime.fromisoformat(created_at)
            except Exception:
                ts = utc_now()
        return Event(
            id=str(payload.get("id") or generate_ulid()),
            type=str(payload.get("type") or ""),
            payload=payload.get("payload") or {},
            created_at=ts,
            tenant_id=payload.get("tenant_id"),
            workspace_id=payload.get("workspace_id"),
            run_id=payload.get("run_id"),
            trace_id=payload.get("trace_id"),
            key=payload.get("key"),
        )
