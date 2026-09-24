"""Replay-and-tail helpers for persisted response event streams."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from app.kernel.events.bus import Event

_TERMINAL_RESPONSE_STATUSES = frozenset({"succeeded", "failed", "canceled"})


def response_event_key(response_id: str) -> str:
    """Routing key under which one response's appended events travel."""
    return f"response:{response_id}"


async def release_read_transaction(db: Any) -> None:
    """End a tailer's read transaction before it waits.

    Every poll's SELECT begins a transaction that pins one pooled connection
    until it ends; a stream waiting on the worker with that transaction open
    would hold the connection for the whole execution, and the pool caps how
    many streams can wait at once. Rolling back returns the connection and
    costs nothing: the tailer never writes.
    """
    if db is not None:
        await db.rollback()


async def tail_response_events(
    service: Any,
    response_id: str,
    *,
    after_sequence: int = 0,
    interaction_id: str | None = None,
    heartbeat_seconds: float = 15.0,
    poll_interval_seconds: float = 1.0,
) -> AsyncIterator[dict[str, Any]]:
    """Replay persisted events, then tail notifications until the response is terminal."""

    cursor = max(0, after_sequence)
    signal = asyncio.Event()
    event_bus = getattr(service.trace_writer, "event_bus", None)
    subscription_id: str | None = None

    async def wake(_: Event) -> None:
        signal.set()

    if event_bus is not None:
        subscription_id = await event_bus.subscribe(
            wake,
            event_type="response.event.appended",
            key=response_event_key(response_id),
            predicate=lambda event: (
                event.tenant_id == service.ctx.tenant_id
                and event.workspace_id == service.ctx.workspace_id
                and event.payload.get("response_id") == response_id
            ),
        )

    last_heartbeat = time.monotonic()
    try:
        while True:
            signal.clear()
            if service.db is not None:
                service.db.expire_all()
            list_kwargs = {
                "limit": 1000,
                "offset": 0,
                "after_sequence": cursor,
            }
            if interaction_id is not None:
                list_kwargs["interaction_id"] = interaction_id
            events = await service.list_response_events(response_id, **list_kwargs)
            for event in events:
                cursor = max(cursor, event.sequence)
                yield {"kind": "event", "event": event}
            if len(events) >= 1000:
                continue

            response = await service.get_response(response_id)
            active_interaction_id = interaction_id or str(
                (getattr(response, "metadata_json", None) or {}).get("interaction_id")
                or ""
            )
            interaction = (
                await service.get_interaction(active_interaction_id)
                if active_interaction_id and hasattr(service, "get_interaction")
                else None
            )
            terminal = (
                interaction.status in _TERMINAL_RESPONSE_STATUSES
                or interaction.status == "waiting_approval"
                if interaction is not None
                else response.status in _TERMINAL_RESPONSE_STATUSES
            )
            if terminal:
                # The status was read after the events; anything the worker
                # committed between the two reads (typically RUN_FINISHED
                # itself) would otherwise never reach the client.
                for event in await service.list_response_events(response_id, **list_kwargs):
                    if event.sequence > cursor:
                        cursor = event.sequence
                        yield {"kind": "event", "event": event}
                yield {"kind": "done", "sequence": cursor}
                return

            now = time.monotonic()
            if now - last_heartbeat >= heartbeat_seconds:
                yield {"kind": "heartbeat", "sequence": cursor}
                last_heartbeat = now

            timeout = max(0.0, poll_interval_seconds)
            await release_read_transaction(service.db)
            if event_bus is None:
                await asyncio.sleep(timeout)
                continue
            try:
                await asyncio.wait_for(signal.wait(), timeout=timeout)
            except TimeoutError:
                pass
    finally:
        if event_bus is not None and subscription_id is not None:
            await event_bus.unsubscribe(subscription_id)
