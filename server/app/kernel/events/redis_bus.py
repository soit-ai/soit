"""redis_bus

Redis-backed event bus for cross-instance propagation.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import redis.asyncio as redis

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.events.bus import Event, EventBus, _Subscription


logger = logging.getLogger(__name__)


class RedisEventBus(EventBus):
    """Redis pubsub event bus implementation."""

    def __init__(self, redis_url: str, channel: str) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=False)
        self._channel = channel
        self._subs: Dict[str, _Subscription] = {}
        self._lock = asyncio.Lock()
        self._listener_task: Optional[asyncio.Task] = None
        self._closed = False

    async def publish(self, event: Event) -> int:
        """Publish event to Redis channel."""
        payload = {
            "id": event.id,
            "type": event.type,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
            "tenant_id": event.tenant_id,
            "workspace_id": event.workspace_id,
            "run_id": event.run_id,
            "trace_id": event.trace_id,
        }
        try:
            await self._redis.publish(self._channel, json.dumps(payload))
        except Exception:
            logger.exception("eventbus.redis.publish_failed", extra={"channel": self._channel})
        return 1

    async def subscribe(
        self,
        handler,
        *,
        event_type: Optional[str] = None,
        predicate=None,
    ) -> str:
        """Register a handler and return subscription id."""
        subscription_id = f"sub_{generate_ulid()}"
        async with self._lock:
            self._subs[subscription_id] = _Subscription(
                handler=handler,
                event_type=event_type,
                predicate=predicate,
            )
        await self._ensure_listener()
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove subscription if present."""
        async with self._lock:
            self._subs.pop(subscription_id, None)

    async def close(self) -> None:
        """Close listener and Redis connection."""
        self._closed = True
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
        try:
            await self._redis.close()
        except Exception:
            pass

    async def _ensure_listener(self) -> None:
        if self._listener_task and not self._listener_task.done():
            return
        self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self._channel)
        try:
            async for message in pubsub.listen():
                if self._closed:
                    break
                if not message or message.get("type") != "message":
                    continue
                raw = message.get("data")
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                event = self._decode_event(raw)
                if not event:
                    continue
                await self._dispatch(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("eventbus.redis.listen_failed", extra={"channel": self._channel})
        finally:
            try:
                await pubsub.unsubscribe(self._channel)
                await pubsub.close()
            except Exception:
                pass

    async def _dispatch(self, event: Event) -> None:
        async with self._lock:
            subs = list(self._subs.values())
        for sub in subs:
            if sub.event_type and sub.event_type != event.type:
                continue
            if sub.predicate and not sub.predicate(event):
                continue
            result = sub.handler(event)
            if asyncio.iscoroutine(result):
                await result

    def _decode_event(self, raw: str) -> Optional[Event]:
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
        )
