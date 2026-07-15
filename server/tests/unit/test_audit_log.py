"""Unit tests for gateway audit logging."""

import json

import pytest
from sqlmodel import select

from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.runs import RunStep
from app.kernel.runtime.runs.writer import TraceWriter


@pytest.mark.asyncio
async def test_log_gateway_request_inline(db, ctx):
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="tool",
        subject_kind="tool",
        subject_id="tool_inline",
        subject_version_id="app_v1",
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

    audit = db.exec(select(AuditEvent).where(AuditEvent.step_id == step.id)).one()
    assert audit.payload_json["request"]["url"] == "https://api.example.com"
    assert (db.get(RunStep, step.id).metrics_json or {}).get("audit_json") is None


@pytest.mark.asyncio
async def test_log_gateway_request_truncates_without_storage(db, ctx):
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="tool",
        subject_kind="tool",
        subject_id="tool_truncate",
        subject_version_id="app_v1",
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

    audit = db.exec(select(AuditEvent).where(AuditEvent.step_id == step.id)).one()
    assert audit.payload_json["truncated"] is True
    assert "preview" in audit.payload_json


@pytest.mark.asyncio
async def test_log_gateway_request_redacts_sensitive_fields(db, ctx):
    """Audit log redacts sensitive fields before storage."""
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="tool",
        subject_kind="tool",
        subject_id="tool_redact",
        subject_version_id="app_v1",
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

    audit = db.exec(select(AuditEvent).where(AuditEvent.step_id == step.id)).one()
    audit_json = json.dumps(audit.payload_json)
    assert "supersecret" not in audit_json
    assert "***REDACTED***" in audit_json


