"""Response lifecycle and semantic event contract tests."""

from __future__ import annotations

import pytest

from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.status import RuntimeTransitionError

pytestmark = pytest.mark.asyncio


def _service(db, ctx) -> ResponseService:
    return ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )


async def test_response_success_uses_runtime_status_and_event_names(async_db, ctx):
    service = _service(async_db, ctx)
    run = await service.trace_writer.create_run("response", kind="response")
    response = await service.create_linked_response(run_id=run.id)

    assert response.request_id == ctx.request_id

    running = await service.mark_running(response)
    succeeded = await service.complete_response(response=running, output_json={"text": "ok"})
    events = await service.list_response_events(response.id, limit=20, offset=0)

    assert succeeded.status == "succeeded"
    assert [event.type for event in events][-2:] == [
        "response.output_text.done",
        "response.succeeded",
    ]
    assert events[-1].payload_json["status"] == "succeeded"


async def test_response_terminal_status_cannot_be_overwritten(async_db, ctx):
    service = _service(async_db, ctx)
    run = await service.trace_writer.create_run("response", kind="response")
    response = await service.create_linked_response(run_id=run.id)
    await service.mark_running(response)
    await service.complete_response(response=response, output_json={"text": "ok"})

    with pytest.raises(RuntimeTransitionError, match="Invalid response transition"):
        await service.fail_response(
            response=response, error_code="late_error", error_message="late"
        )

    assert (await service.get_response(response.id)).status == "succeeded"


async def test_response_cancel_is_idempotent_after_first_transition(async_db, ctx):
    service = _service(async_db, ctx)
    run = await service.trace_writer.create_run("response", kind="response")
    response = await service.create_linked_response(run_id=run.id)
    await service.trace_writer.update_run_status(run.id, "running")
    await service.mark_running(response)

    first = await service.cancel_response(response.id)
    second = await service.cancel_response(response.id)

    assert first.status == "canceled"
    assert second.status == "canceled"
    events = await service.list_response_events(response.id, limit=20, offset=0)
    assert [event.type for event in events].count("response.canceled") == 1
