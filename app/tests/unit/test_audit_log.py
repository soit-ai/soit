"""Unit tests for gateway audit logging."""

import pytest

from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.trace.writer import TraceWriter
from app.kernel.trace.models import RunStep


@pytest.mark.asyncio
async def test_log_gateway_request_inline(db, ctx):
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="tool",
        app_id="app_tool",
        app_version_id="app_v1",
        app_type="tool",
    )
    step = trace_writer.create_step(run_id=run.id, step_type="tool", step_id="step_a")

    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=run.id,
        step_id=step.id,
        gateway_type="tool",
        request_data={"url": "https://api.example.com"},
        response_data={"success": True},
    )

    refreshed = db.get(RunStep, step.id)
    assert refreshed.metrics_json is not None
    assert "audit_json" in refreshed.metrics_json


@pytest.mark.asyncio
async def test_log_gateway_request_truncates_without_storage(db, ctx):
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="tool",
        app_id="app_tool",
        app_version_id="app_v1",
        app_type="tool",
    )
    step = trace_writer.create_step(run_id=run.id, step_type="tool", step_id="step_b")

    large_payload = "x" * 9000
    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=run.id,
        step_id=step.id,
        gateway_type="tool",
        request_data={"payload": large_payload},
        response_data={"success": True},
    )

    refreshed = db.get(RunStep, step.id)
    assert refreshed.metrics_json is not None
    assert refreshed.metrics_json.get("audit_truncated") is True
    assert "audit_preview" in refreshed.metrics_json


@pytest.mark.asyncio
async def test_log_gateway_request_redacts_sensitive_fields(db, ctx):
    """Audit log redacts sensitive fields before storage."""
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="tool",
        app_id="app_tool",
        app_version_id="app_v1",
        app_type="tool",
    )
    step = trace_writer.create_step(run_id=run.id, step_type="tool", step_id="step_redact")

    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=run.id,
        step_id=step.id,
        gateway_type="tool",
        request_data={
            "authorization": "Bearer supersecret",
            "api_key": "supersecret",
            "payload": {"password": "supersecret"},
        },
        response_data={"token": "supersecret"},
    )

    refreshed = db.get(RunStep, step.id)
    audit_json = (refreshed.metrics_json or {}).get("audit_json", "")
    assert "supersecret" not in audit_json
    assert "***REDACTED***" in audit_json
