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


def _service(db, ctx) -> ResponseService:
    return ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )


def test_response_success_uses_runtime_status_and_event_names(db, ctx):
    service = _service(db, ctx)
    run = service.trace_writer.create_run("response", kind="response")
    response = service.create_linked_response(run_id=run.id)

    assert response.request_id == ctx.request_id

    running = service.mark_running(response)
    succeeded = service.complete_response(response=running, output_json={"text": "ok"})
    events = service.list_response_events(response.id, limit=20, offset=0)

    assert succeeded.status == "succeeded"
    assert [event.type for event in events][-2:] == [
        "response.output_text.done",
        "response.succeeded",
    ]
    assert events[-1].payload_json["status"] == "succeeded"


def test_response_terminal_status_cannot_be_overwritten(db, ctx):
    service = _service(db, ctx)
    run = service.trace_writer.create_run("response", kind="response")
    response = service.create_linked_response(run_id=run.id)
    service.mark_running(response)
    service.complete_response(response=response, output_json={"text": "ok"})

    with pytest.raises(RuntimeTransitionError, match="Invalid response transition"):
        service.fail_response(response=response, error_code="late_error", error_message="late")

    assert service.get_response(response.id).status == "succeeded"


def test_response_cancel_is_idempotent_after_first_transition(db, ctx):
    service = _service(db, ctx)
    run = service.trace_writer.create_run("response", kind="response")
    response = service.create_linked_response(run_id=run.id)
    service.trace_writer.update_run_status(run.id, "running")
    service.mark_running(response)

    first = service.cancel_response(response.id)
    second = service.cancel_response(response.id)

    assert first.status == "canceled"
    assert second.status == "canceled"
    events = service.list_response_events(response.id, limit=20, offset=0)
    assert [event.type for event in events].count("response.canceled") == 1
