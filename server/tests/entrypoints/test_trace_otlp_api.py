"""A trace leaves as an OTLP/JSON document a collector can ingest."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.runs import Run, RunStep
from app.kernel.runtime.runs.otlp import OTLP_TRACE_SPEC
from app.kernel.specs import validate_spec
from app.main import app
from app.middleware.auth import get_current_context

pytestmark = pytest.mark.asyncio

TRACE_ID = "trace_01J9KD84QF"
T0 = datetime(2026, 9, 29, 8, 0, 0, tzinfo=UTC)
PROMPT = "Please refund order 4412"


async def _trace(async_db, ctx: RequestContext) -> None:
    async_db.add(
        Run(
            id="run_root",
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            trace_id=TRACE_ID,
            mode="agent",
            kind="agent",
            status="succeeded",
            input_summary=PROMPT,
            started_at=T0,
            ended_at=T0 + timedelta(seconds=3),
        )
    )
    async_db.add(
        Run(
            id="run_child",
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            trace_id=TRACE_ID,
            parent_run_id="run_root",
            mode="tool",
            kind="tool",
            status="failed",
            error_code="tool.timeout",
            error_message="Provider answered 503",
            started_at=T0 + timedelta(seconds=1),
            ended_at=T0 + timedelta(seconds=2),
        )
    )
    async_db.add(
        RunStep(
            id="st_answer",
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            trace_id=TRACE_ID,
            run_id="run_root",
            step_type="llm",
            status="succeeded",
            input_summary=PROMPT,
            metrics_json={"prompt_tokens": 12, "latency_ms": 640.25},
            started_at=T0 + timedelta(milliseconds=100),
            ended_at=T0 + timedelta(milliseconds=800),
        )
    )
    await async_db.commit()


async def test_a_trace_downloads_as_otlp_json(async_client, async_db, ctx) -> None:
    await _trace(async_db, ctx)

    response = await async_client.get(f"/api/v1/runs/trace/{TRACE_ID}/otlp")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="trace-{TRACE_ID}.otlp.json"'
    )
    document = response.json()
    assert validate_spec(document, OTLP_TRACE_SPEC) is True
    spans = {
        span["name"]: span
        for span in document["resourceSpans"][0]["scopeSpans"][0]["spans"]
    }
    assert set(spans) == {"run agent", "run tool", "llm"}
    assert spans["run tool"]["parentSpanId"] == spans["run agent"]["spanId"]
    assert spans["llm"]["parentSpanId"] == spans["run agent"]["spanId"]
    assert spans["run tool"]["status"] == {"code": 2, "message": "tool.timeout"}
    assert PROMPT not in response.text
    assert "503" not in response.text

    audits = list(
        (
            await async_db.exec(
                select(AuditEvent).where(AuditEvent.event_type == "trace.otlp_exported")
            )
        ).all()
    )
    assert [audit.resource_id for audit in audits] == [TRACE_ID]
    assert audits[0].payload_json == {"runs": 2, "spans": 3}


async def test_a_trace_with_no_run_in_the_workspace_is_not_found(
    async_client, async_db, ctx
) -> None:
    await _trace(async_db, ctx)

    assert (
        await async_client.get("/api/v1/runs/trace/trace_missing/otlp")
    ).status_code == 404

    outsider = dataclasses.replace(ctx, workspace_id="another-workspace")
    app.dependency_overrides[get_current_context] = lambda: outsider
    try:
        response = await async_client.get(f"/api/v1/runs/trace/{TRACE_ID}/otlp")
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx
    assert response.status_code == 404
