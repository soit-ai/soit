"""Registry mapping event_type to ordered outbox consumer handlers (Phase 1)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegisteredOutboxHandler:
    """Single consumer bound to an event type."""

    consumer_name: str
    handler: Callable[..., Any]


class OutboxHandlerRegistry:
    """Register handlers per event_type; iteration order matches registration order."""

    def __init__(self) -> None:
        self._by_type: dict[str, list[RegisteredOutboxHandler]] = {}

    def register(self, event_type: str, consumer_name: str, handler: Callable[..., Any]) -> None:
        """Append a handler for the given event_type."""
        entry = RegisteredOutboxHandler(consumer_name=consumer_name, handler=handler)
        if event_type not in self._by_type:
            self._by_type[event_type] = []
        self._by_type[event_type].append(entry)

    def get_handlers(self, event_type: str) -> list[RegisteredOutboxHandler]:
        """Copy of handlers for event_type (stable registration order)."""
        return list(self._by_type.get(event_type, []))

    def event_types(self) -> list[str]:
        """Registered event types (arbitrary order; for diagnostics)."""
        return list(self._by_type.keys())
