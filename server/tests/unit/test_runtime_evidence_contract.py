"""Runtime lineage, artifact, audit, usage, and charge contract tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlmodel import select

from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.runs.service import RunService
from app.kernel.runtime.runs.writer import TraceWriter

pytestmark = pytest.mark.asyncio


async def test_run_writer_persists_lineage_and_request_identity(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    parent = await writer.create_run("agent", request_id="request-parent")

    child = await writer.create_run(
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


async def test_artifact_registration_requires_scoped_key_and_evidence(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("agent")

    with pytest.raises(ValueError, match="canonical run prefix"):
        await writer.create_artifact(
            run_id=run.id,
            artifact_type="json",
            storage_key=f"audit/{run.id}/evidence.json",
            size_bytes=2,
            sha256="a" * 64,
        )

    with pytest.raises(ValueError, match="SHA256"):
        await writer.create_artifact(
            run_id=run.id,
            artifact_type="json",
            storage_key=(
                f"tenants/{ctx.tenant_id}/workspaces/{ctx.workspace_id}/runs/{run.id}/evidence.json"
            ),
            size_bytes=2,
            sha256=None,
        )

    artifact = await writer.create_artifact(
        run_id=run.id,
        artifact_type="json",
        storage_key=f"tenants/{ctx.tenant_id}/workspaces/{ctx.workspace_id}/runs/{run.id}/evidence.json",
        size_bytes=2,
        sha256="a" * 64,
    )
    assert artifact.size_bytes == 2


async def test_priced_usage_is_one_record_with_an_immutable_pricing_snapshot(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("agent")

    usage = await writer.record_cost(
        run_id=run.id,
        step_id=None,
        billing_basis="tokens",
        billed_quantity=15,
        currency="USD",
        amount=Decimal("0.0025"),
        model_ref="model:provider-a:model-a",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        pricing_snapshot_json={
            "source": "provider_model",
            "billing_basis": "tokens",
            "billing_unit": "mtok",
            "unit_size": 1_000_000,
            "rates": {
                "input": {
                    "price": "100",
                    "unit": "mtok",
                    "unit_size": 1_000_000,
                },
            },
            "configured_pricing": {
                "currency": "USD",
                "unit": "mtok",
                "input": 100,
            },
        },
    )

    assert usage.amount == Decimal("0.0025")
    assert usage.currency == "USD"
    assert usage.pricing_snapshot_json["model"]["resolved"] == "model:provider-a:model-a"
    assert usage.pricing_snapshot_json["unit_size"] == 1_000_000
    assert usage.pricing_snapshot_json["amount"] == "0.0025"

    detail = await RunService(async_db, ctx).get_run(run.id)
    assert len(detail.costs) == 1
    assert detail.usage_summary is not None
    assert detail.usage_summary.tokens_prompt == 10
    assert detail.usage_summary.tokens_completion == 5
    assert detail.charge_summary is not None
    assert detail.charge_summary.amounts == {"USD": Decimal("0.0025")}


async def test_usage_row_carries_dimension_columns_for_one_invocation(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("agent")

    usage = await writer.record_cost(
        run_id=run.id,
        step_id=None,
        billing_basis="tokens",
        billed_quantity=15,
        model_ref="model:provider-a:model-a",
        source_port="llm",
        operation="chat",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        latency_ms=120,
    )

    assert usage.source_port == "llm"
    assert usage.operation == "chat"
    assert usage.latency_ms == 120
    assert usage.pricing_snapshot_json["quantities"]["latency_ms"] == 120

    detail = await RunService(async_db, ctx).get_run(run.id)
    assert len(detail.costs) == 1
    assert detail.usage_summary is not None
    assert detail.usage_summary.ms_total == 120
    assert detail.usage_summary.tokens_prompt == 10


async def test_trace_writer_rejects_negative_dimension_values(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("agent")

    with pytest.raises(ValueError, match="latency_ms must not be negative"):
        await writer.record_cost(
            run_id=run.id,
            step_id=None,
            billing_basis="tokens",
            billed_quantity=10,
            latency_ms=-1,
        )


async def test_trace_writer_has_no_charge_entry_concept(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("agent")

    with pytest.raises(TypeError):
        await writer.record_cost(
            run_id=run.id,
            step_id=None,
            entry_type="charge",
            billing_basis="tokens",
            billed_quantity=10,
            currency="USD",
            amount=Decimal("0.0025"),
        )


async def test_gateway_audit_is_authoritative_audit_event(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("agent")
    step = await writer.create_step(run.id, "tool")

    await log_gateway_request(
        writer,
        run.id,
        step.id,
        "tool",
        {"url": "https://example.test", "authorization": "Bearer secret"},
        {"status_code": 200},
    )

    event = (await async_db.exec(select(AuditEvent).where(AuditEvent.run_id == run.id))).one()
    assert event.step_id == step.id
    assert event.trace_id == ctx.trace_id
    assert event.outcome == "succeeded"
    assert event.payload_json["request"]["authorization"] == "***REDACTED***"

    await async_db.refresh(step)
    assert "audit_json" not in (step.metrics_json or {})
    audits = await RunService(async_db, ctx).list_audits(run_id=run.id)
    assert len(audits) == 1
    assert audits[0].gateway_type == "tool"
