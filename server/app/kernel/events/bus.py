"""bus

In-process event bus for kernel-level signals.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now

EventHandler = Callable[["Event"], Any]
EventPredicate = Callable[["Event"], bool]


@dataclass(frozen=True)
class Event:
    """Event payload envelope."""

    id: str
    type: str
    payload: dict[str, Any]
    created_at: datetime
    tenant_id: str | None = None
    workspace_id: str | None = None
    run_id: str | None = None
    trace_id: str | None = None
    key: str | None = None
    """Routing key, e.g. ``response:<id>``; keyed subscriptions only see events with their key."""


class EventBus:
    """Event bus interface."""

    async def publish(self, event: Event) -> int:  # pragma: no cover - interface only
        raise NotImplementedError

    async def subscribe(
        self,
        handler: EventHandler,
        *,
        event_type: str | None = None,
        predicate: EventPredicate | None = None,
        key: str | None = None,
    ) -> str:  # pragma: no cover - interface only
        """Register a handler.

        A subscription with a ``key`` is only offered events published with
        that key, found by lookup rather than by testing every subscription:
        a process tailing hundreds of conversations pays for one, not all.
        """
        raise NotImplementedError

    async def unsubscribe(self, subscription_id: str) -> None:  # pragma: no cover - interface only
        raise NotImplementedError


@dataclass
class _Subscription:
    handler: EventHandler
    event_type: str | None
    predicate: EventPredicate | None
    key: str | None = None


class SubscriptionIndex:
    """Subscriptions split into keyless ones and a dict of keyed ones."""

    def __init__(self) -> None:
        self.unkeyed: dict[str, _Subscription] = {}
        self.keyed: dict[str, dict[str, _Subscription]] = {}
        self._key_of: dict[str, str | None] = {}

    def add(self, subscription_id: str, sub: _Subscription) -> None:
        self._key_of[subscription_id] = sub.key
        if sub.key is None:
            self.unkeyed[subscription_id] = sub
        else:
            self.keyed.setdefault(sub.key, {})[subscription_id] = sub

    def remove(self, subscription_id: str) -> str | None:
        """Remove a subscription; return its key if it was the last one for that key."""
        key = self._key_of.pop(subscription_id, None)
        if key is None:
            self.unkeyed.pop(subscription_id, None)
            return None
        bucket = self.keyed.get(key)
        if bucket is not None:
            bucket.pop(subscription_id, None)
            if not bucket:
                del self.keyed[key]
                return key
        return None

    def candidates(self, event: Event, *, include_unkeyed: bool = True, include_keyed: bool = True) -> list[_Subscription]:
        found: list[_Subscription] = []
        if include_unkeyed:
            found.extend(self.unkeyed.values())
        if include_keyed and event.key is not None:
            found.extend(self.keyed.get(event.key, {}).values())
        return found


def matches(sub: _Subscription, event: Event) -> bool:
    if sub.event_type and sub.event_type != event.type:
        return False
    return not (sub.predicate and not sub.predicate(event))


class InMemoryEventBus(EventBus):
    """In-memory event bus implementation."""

    def __init__(self) -> None:
        self._index = SubscriptionIndex()
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> int:
        """Publish event to matching subscribers."""
        async with self._lock:
            subs = self._index.candidates(event)

        delivered = 0
        for sub in subs:
            if not matches(sub, event):
                continue
            await self._invoke_handler(sub.handler, event)
            delivered += 1
        return delivered

    async def subscribe(
        self,
        handler: EventHandler,
        *,
        event_type: str | None = None,
        predicate: EventPredicate | None = None,
        key: str | None = None,
    ) -> str:
        """Register a handler and return subscription id."""
        subscription_id = f"sub_{generate_ulid()}"
        async with self._lock:
            self._index.add(
                subscription_id,
                _Subscription(handler=handler, event_type=event_type, predicate=predicate, key=key),
            )
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove subscription if present."""
        async with self._lock:
            self._index.remove(subscription_id)

    def create_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any] | None = None,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        run_id: str | None = None,
        trace_id: str | None = None,
        key: str | None = None,
    ) -> Event:
        """Create a new event with defaults."""
        return Event(
            id=generate_ulid(),
            type=event_type,
            payload=payload or {},
            created_at=utc_now(),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            run_id=run_id,
            trace_id=trace_id,
            key=key,
        )

    def publish_sync(self, event: Event) -> int:
        """Publish event from sync contexts."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.publish(event))
                return 0
            return loop.run_until_complete(self.publish(event))
        except RuntimeError:
            return asyncio.run(self.publish(event))

    async def _invoke_handler(self, handler: EventHandler, event: Event) -> None:
        """Invoke handler (sync or async)."""
        result = handler(event)
        if inspect.isawaitable(result):
            await result
