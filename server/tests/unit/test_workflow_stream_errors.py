"""Workflow SSE error events do not carry the text of internal failures."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from app.api.v1.workflow.streaming import SSEHandlers, stream_error_payload
from app.kernel.commons.errors import KernelError, NotFoundError
from app.kernel.contracts.context import RequestContext

SECRET = "postgresql://soit:hunter2@db.internal:5432/soit"


def _ctx() -> RequestContext:
    return RequestContext(
        tenant_id="tenant_1",
        workspace_id="ws_1",
        user_id="user_1",
        request_id="req_1",
    )


def test_an_internal_failure_is_reported_by_request_id_only(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="app.api.v1.workflow.streaming"):
        payload = stream_error_payload(
            RuntimeError(f"could not connect to {SECRET}"),
            run_id="run_1",
            request_id="req_1",
            default="Workflow execution failed",
        )

    assert payload == {"run_id": "run_1", "request_id": "req_1", "error": "Workflow execution failed"}
    assert SECRET in caplog.text  # kept for the operator, with its traceback


def test_an_unmapped_kernel_error_keeps_its_code_but_not_its_text() -> None:
    payload = stream_error_payload(
        KernelError("VECTOR_COLLECTION_ERROR", f"collection failed at {SECRET}"),
        run_id="run_1",
        request_id="req_1",
        default="Workflow execution failed",
    )

    assert payload["error_code"] == "VECTOR_COLLECTION_ERROR"
    assert SECRET not in json.dumps(payload)


def test_a_callers_error_keeps_its_message() -> None:
    payload = stream_error_payload(
        NotFoundError("Workflow not found"),
        run_id="run_1",
        request_id="req_1",
        default="Workflow execution failed",
    )

    assert payload["error"] == "Workflow not found"
    assert payload["error_code"] == "NOT_FOUND"


def test_a_budget_refusal_says_which_budget() -> None:
    payload = stream_error_payload(
        KernelError("BUDGET_EXHAUSTED", "Budget 'Team' is spent: 10 of 10 USD this month"),
        run_id="run_1",
        request_id="req_1",
        default="Workflow execution failed",
    )

    assert "Budget 'Team' is spent" in payload["error"]


class _FailingCompiler:
    async def compile_workflow(self, workflow_id: str, inputs: dict[str, Any], run_id: str) -> Any:
        raise RuntimeError(f"template engine crashed reading {SECRET}")


@pytest.mark.asyncio
async def test_a_failed_compile_streams_a_masked_error_event() -> None:
    handlers = SSEHandlers(_FailingCompiler())  # type: ignore[arg-type]

    chunks = [chunk async for chunk in handlers.stream_execution(_ctx(), "wf_1", {})]
    body = "".join(chunks)

    assert "event: error" in body
    assert SECRET not in body
    error_data = json.loads(body.split("event: error\n", 1)[1].split("data: ", 1)[1].split("\n", 1)[0])
    assert error_data["error"] == "Workflow execution failed"
    assert error_data["request_id"] == "req_1"
