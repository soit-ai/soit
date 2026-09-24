"""A durable claim is announced on the event bus so an idle worker can start at once."""

from __future__ import annotations

import pytest

from app.kernel.events.bus import InMemoryEventBus
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import (
    INTERACTION_CLAIMED_EVENT,
    ResponseService,
)
from app.kernel.runtime.runs.writer import TraceWriter


@pytest.mark.asyncio
async def test_claiming_an_interaction_announces_it_after_the_commit(async_db, ctx) -> None:
    bus = InMemoryEventBus()
    seen: list[str] = []

    async def on_claim(event) -> None:
        seen.append(event.payload["interaction_id"])

    await bus.subscribe(on_claim, event_type=INTERACTION_CLAIMED_EVENT)
    service = ResponseService(
        db=async_db,
        ctx=ctx,
        response_repo=ResponseRepository(async_db, ctx),
        event_repo=ResponseEventRepository(async_db, ctx),
        trace_writer=TraceWriter(async_db, ctx, event_bus=bus),
    )

    _, owns_claim = await service.claim_interaction(
        interaction_id="interaction_announced",
        parent_interaction_id=None,
        thread_id="thread_announced",
        request_hash="hash_announced",
        execution_json={"mode": "direct", "payload": {}},
        request_context_json={"tenant_id": ctx.tenant_id, "workspace_id": ctx.workspace_id, "user_id": ctx.user_id},
    )
    # publish_sync schedules the delivery on the running loop; let it run.
    import asyncio

    await asyncio.sleep(0)

    assert owns_claim is True
    assert seen == ["interaction_announced"]

    # A repeated claim of the same interaction is not a new announcement.
    _, owns_claim = await service.claim_interaction(
        interaction_id="interaction_announced",
        parent_interaction_id=None,
        thread_id="thread_announced",
        request_hash="hash_announced",
        execution_json={"mode": "direct", "payload": {}},
        request_context_json={"tenant_id": ctx.tenant_id, "workspace_id": ctx.workspace_id, "user_id": ctx.user_id},
    )
    await asyncio.sleep(0)
    assert owns_claim is False
    assert seen == ["interaction_announced"]
