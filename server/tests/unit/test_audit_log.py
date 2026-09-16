"""Unit tests for gateway audit logging."""

import json

import pytest
from sqlmodel import select

from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.runs import RunStep
from app.kernel.runtime.runs.writer import TraceWriter

pytestmark = pytest.mark.asyncio


async def _audit_for_step(db, step_id: str) -> AuditEvent:
    return (await db.exec(select(AuditEvent).where(AuditEvent.step_id == step_id))).one()


async def test_log_gateway_request_inline(async_db, ctx):
    trace_writer = TraceWriter(async_db, ctx)
    run = await trace_writer.create_run(
        mode="tool",
        subject_kind="tool",
        subject_id="tool_inline",
        subject_version_id="app_v1",
    )
    step = await trace_writer.create_step(run_id=run.id, step_type="tool", step_id="step_a")

    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=run.id,
        step_id=step.id,
        gateway_type="tool",
        request_data={"url": "https://api.example.com"},
        response_data={"success": True},
    )

    audit = await _audit_for_step(async_db, step.id)
    assert audit.payload_json["request"]["url"] == "https://api.example.com"
    stored = await async_db.get(RunStep, step.id)
    assert stored is not None
    assert (stored.metrics_json or {}).get("audit_json") is None


async def test_log_gateway_request_truncates_without_storage(async_db, ctx):
    trace_writer = TraceWriter(async_db, ctx)
    run = await trace_writer.create_run(
        mode="tool",
        subject_kind="tool",
        subject_id="tool_truncate",
        subject_version_id="app_v1",
    )
    step = await trace_writer.create_step(run_id=run.id, step_type="tool", step_id="step_b")

    large_payload = "x" * 9000
    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=run.id,
        step_id=step.id,
        gateway_type="tool",
        request_data={"payload": large_payload},
        response_data={"success": True},
    )

    audit = await _audit_for_step(async_db, step.id)
    assert audit.payload_json["truncated"] is True
    assert "preview" in audit.payload_json


async def test_log_gateway_request_redacts_sensitive_fields(async_db, ctx):
    """Audit log redacts sensitive fields before storage."""
    trace_writer = TraceWriter(async_db, ctx)
    run = await trace_writer.create_run(
        mode="tool",
        subject_kind="tool",
        subject_id="tool_redact",
        subject_version_id="app_v1",
    )
    step = await trace_writer.create_step(run_id=run.id, step_type="tool", step_id="step_redact")

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

    audit = await _audit_for_step(async_db, step.id)
    audit_json = json.dumps(audit.payload_json)
    assert "supersecret" not in audit_json
    assert "***REDACTED***" in audit_json
