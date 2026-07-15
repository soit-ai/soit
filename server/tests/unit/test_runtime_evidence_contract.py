"""Runtime lineage, artifact, audit, usage, and charge contract tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlmodel import select

from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.runs.service import RunService
from app.kernel.runtime.runs.writer import TraceWriter


def test_run_writer_persists_lineage_and_request_identity(db, ctx):
    writer = TraceWriter(db, ctx)
    parent = writer.create_run("agent", request_id="request-parent")

    child = writer.create_run(
        "tool",
        parent_run_id=parent.id,
        source_run_id="run_previous_attempt",
        attempt_no=2,
        request_id="request-child",
    )

    assert child.parent_run_id == parent.id
    assert child.source_run_id == "run_previous_attempt"
    assert child.attempt_no == 2
    assert child.request_id == "request-child"


def test_artifact_registration_requires_scoped_key_and_evidence(db, ctx):
    writer = TraceWriter(db, ctx)
    run = writer.create_run("agent")

    with pytest.raises(ValueError, match="canonical run prefix"):
        writer.create_artifact(
            run_id=run.id,
            artifact_type="json",
            storage_key=f"audit/{run.id}/evidence.json",
            size_bytes=2,
            sha256="a" * 64,
        )

    with pytest.raises(ValueError, match="SHA256"):
        writer.create_artifact(
            run_id=run.id,
            artifact_type="json",
            storage_key=(
                f"tenants/{ctx.tenant_id}/workspaces/{ctx.workspace_id}/runs/{run.id}/evidence.json"
            ),
            size_bytes=2,
            sha256=None,
        )

    artifact = writer.create_artifact(
        run_id=run.id,
        artifact_type="json",
        storage_key=f"tenants/{ctx.tenant_id}/workspaces/{ctx.workspace_id}/runs/{run.id}/evidence.json",
        size_bytes=2,
        sha256="a" * 64,
    )
    assert artifact.size_bytes == 2


def test_usage_and_charge_entries_have_distinct_money_semantics(db, ctx):
    writer = TraceWriter(db, ctx)
    run = writer.create_run("agent")

    usage = writer.record_cost(
        run_id=run.id,
        step_id=None,
        unit="tokens",
        quantity=15,
        prompt_tokens=10,
        completion_tokens=5,
    )
    charge = writer.record_cost(
        run_id=run.id,
        step_id=None,
        entry_type="charge",
        unit="prompt_tokens",
        quantity=10,
        currency="USD",
        amount=Decimal("0.0025"),
    )

    assert usage.entry_type == "usage"
    assert usage.amount is None
    assert usage.currency is None
    assert charge.entry_type == "charge"
    assert charge.amount == Decimal("0.0025")
    assert charge.currency == "USD"

    detail = RunService(db, ctx).get_run(run.id)
    assert detail.usage_summary is not None
    assert detail.usage_summary.tokens_prompt == 10
    assert detail.charge_summary is not None
    assert detail.charge_summary.amounts == {"USD": Decimal("0.0025")}


@pytest.mark.asyncio
async def test_gateway_audit_is_authoritative_audit_event(db, ctx):
    writer = TraceWriter(db, ctx)
    run = writer.create_run("agent")
    step = writer.create_step(run.id, "tool")

    await log_gateway_request(
        writer,
        run.id,
        step.id,
        "tool",
        {"url": "https://example.test", "authorization": "Bearer secret"},
        {"status_code": 200},
    )

    event = db.exec(select(AuditEvent).where(AuditEvent.run_id == run.id)).one()
    assert event.step_id == step.id
    assert event.trace_id == ctx.trace_id
    assert event.outcome == "succeeded"
    assert event.payload_json["request"]["authorization"] == "***REDACTED***"

    db.refresh(step)
    assert "audit_json" not in (step.metrics_json or {})
    audits = RunService(db, ctx).list_audits(run_id=run.id)
    assert len(audits) == 1
    assert audits[0].gateway_type == "tool"
