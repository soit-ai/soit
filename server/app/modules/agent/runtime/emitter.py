"""emitter

EventEmitter protocol for agent streaming.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Protocol, Tuple


class EventEmitter(Protocol):
    """Callable that emits agent lifecycle events."""

    async def __call__(self, event: str, data: Dict[str, Any]) -> None: ...


async def noop_emitter(event: str, data: Dict[str, Any]) -> None:
    """No-op emitter for non-streaming execution."""
    pass


class CollectingEmitter:
    """Test helper that collects emitted events."""

    def __init__(self) -> None:
        self.events: List[Tuple[str, Dict[str, Any]]] = []

    async def __call__(self, event: str, data: Dict[str, Any]) -> None:
        self.events.append((event, data))


class QueueEmitter:
    """Emitter that pushes events to an asyncio.Queue for SSE streaming."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[Tuple[str, Dict[str, Any]] | None] = asyncio.Queue()

    async def __call__(self, event: str, data: Dict[str, Any]) -> None:
        await self.queue.put((event, data))

    async def done(self) -> None:
        """Signal that no more events will be emitted."""
        await self.queue.put(None)
