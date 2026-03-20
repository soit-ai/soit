"""test_run_handlers

Tests for run handlers CSV export.
"""

import pytest

from app.kernel.commons.ids import generate_run_id
from app.kernel.commons.time import utc_now
from app.kernel.trace.models import Run
from app.kernel.trace.service import RunService
from app.api.v1.run.handlers import RunHandlers
from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.trace.writer import TraceWriter


@pytest.mark.asyncio
async def test_export_runs_csv_returns_rows(db, ctx):
    """CSV export includes header and run row."""
    run = Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        trace_id="trace_csv",
        mode="chat",
        kind="chat",
        subject_kind="thread",
        subject_id="thr_chat",
        subject_version_id="app_v1",
        status="succeeded",
        started_at=utc_now(),
    )
    db.add(run)
    db.commit()

    service = RunService(db, ctx)
    handlers = RunHandlers(service)

    csv_text = await handlers.export_runs_csv(ctx, limit=10)
    lines = [line for line in csv_text.splitlines() if line.strip()]

    assert lines[0].startswith("run_id,mode,kind,status")
    assert run.id in lines[1]


@pytest.mark.asyncio
async def test_list_runs_accepts_workflow_id_alias(db, ctx):
    """workflow_id resolves to workflow subject filters."""
    run = Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        trace_id="trace_workflow",
        mode="workflow",
        kind="workflow",
        subject_kind="workflow",
        subject_id="wf_workflow",
        subject_version_id="app_v1",
        status="succeeded",
        started_at=utc_now(),
    )
    db.add(run)
    db.commit()

    service = RunService(db, ctx)
    handlers = RunHandlers(service)

    response = await handlers.list_runs(ctx, workflow_id="wf_workflow", page_size=10)
    assert response.items
    assert response.items[0].id == run.id


@pytest.mark.asyncio
async def test_list_audits_returns_entries(db, ctx):
    """Audit entries can be queried by run_id."""
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="tool",
        subject_kind="tool",
        subject_id="tool_runtime",
        subject_version_id="app_v1",
    )
    step = trace_writer.create_step(run_id=run.id, step_type="tool", step_id="step_audit")

    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=run.id,
        step_id=step.id,
        gateway_type="tool",
        request_data={"headers": {"authorization": "Bearer secret"}},
        response_data={"success": True},
    )

    service = RunService(db, ctx)
    handlers = RunHandlers(service)
    response = await handlers.list_audits(ctx, run_id=run.id, page_size=10)

    assert response.items
    assert response.items[0].run_id == run.id


