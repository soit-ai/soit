"""Server-sent event tailing for persisted response interactions.

Any endpoint that hands execution to the durable interaction worker tails the
persisted event stream instead of producing events itself. Keeping one tailer
here stops the agent and response transports from drifting apart.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from app.kernel.commons.errors import ValidationError
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.responses.streaming import tail_response_events

CLAIM_POLL_INTERVAL_SECONDS = 0.1


def format_agui_sse(event_id: str, payload: dict) -> str:
    """Render one AG-UI event as an SSE frame."""
    return f"id: {event_id}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_persisted_response(
    response_service: ResponseService,
    response_id: str,
    *,
    interaction_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames for a response's persisted events until it terminates."""
    async for item in tail_response_events(
        response_service,
        response_id,
        interaction_id=interaction_id,
    ):
        if item["kind"] == "heartbeat":
            yield ": heartbeat\n\n"
        elif item["kind"] == "done":
            return
        else:
            event = item["event"]
            yield format_agui_sse(
                f"{event.response_id}:{event.sequence}",
                event.payload_json,
            )


async def stream_claimed_interaction(
    response_service: ResponseService,
    interaction_id: str,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames for an interaction the durable worker owns.

    The interaction is claimed before any execution happens, so this waits for
    the worker to bind a response and then tails it. A worker that fails before
    binding leaves a terminal interaction status, which ends the stream.
    """
    while True:
        response_service.db.expire_all()
        interaction = response_service.get_interaction(interaction_id)
        if interaction is None:
            raise ValidationError("Claimed interaction no longer exists")
        if interaction.response_id:
            async for chunk in stream_persisted_response(
                response_service,
                interaction.response_id,
                interaction_id=interaction.interaction_id,
            ):
                yield chunk
            return
        if interaction.status in {"failed", "canceled"}:
            if interaction.status == "failed":
                yield format_agui_sse(
                    "",
                    {
                        "type": "RUN_ERROR",
                        "code": "interaction_execution_failed",
                        "message": "Response execution failed",
                    },
                )
            return
        yield ": heartbeat\n\n"
        await asyncio.sleep(CLAIM_POLL_INTERVAL_SECONDS)
