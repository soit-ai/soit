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
    ) -> str:  # pragma: no cover - interface only
        raise NotImplementedError

    async def unsubscribe(self, subscription_id: str) -> None:  # pragma: no cover - interface only
        raise NotImplementedError


@dataclass
class _Subscription:
    handler: EventHandler
    event_type: str | None
    predicate: EventPredicate | None


class InMemoryEventBus(EventBus):
    """In-memory event bus implementation."""

    def __init__(self) -> None:
        self._subs: dict[str, _Subscription] = {}
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> int:
        """Publish event to matching subscribers."""
        async with self._lock:
            subs = list(self._subs.values())

        delivered = 0
        for sub in subs:
            if sub.event_type and sub.event_type != event.type:
                continue
            if sub.predicate and not sub.predicate(event):
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
    ) -> str:
        """Register a handler and return subscription id."""
        subscription_id = f"sub_{generate_ulid()}"
        async with self._lock:
            self._subs[subscription_id] = _Subscription(
                handler=handler,
                event_type=event_type,
                predicate=predicate,
            )
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove subscription if present."""
        async with self._lock:
            self._subs.pop(subscription_id, None)

    def create_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any] | None = None,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        run_id: str | None = None,
        trace_id: str | None = None,
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
