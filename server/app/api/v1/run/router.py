""" router

Run API routes (FastAPI).
"""

from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from app.api.v1.permissions import require_workspace_read_ctx
from app.api.v1.run.dependencies import get_run_artifact_storage, get_run_service
from app.api.v1.run.handlers import RunHandlers
from app.api.v1.workflow.dependencies import get_workflow_service
from app.api.v1.workflow.streaming import SSEHandlers
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.runtime.runs.schemas import (
    RunAuditLogResponse,
    RunCostByModelResponse,
    RunCostByModeResponse,
    RunCostByProviderResponse,
    RunCostBySubjectResponse,
    RunCostDailyResponse,
    RunCostEntryResponse,
    RunCostSummaryResponse,
    RunDetailResponse,
    RunResponse,
    RunStepMetricsSummaryResponse,
    RunStepResponse,
)
from app.kernel.runtime.runs.service import RunService
from app.modules.workflow.application.service import WorkflowService

router = APIRouter()


@router.get("/costs/entries", response_model=PaginatedResponse[RunCostEntryResponse])
async def list_cost_entries(
    since: datetime | None = None,
    until: datetime | None = None,
    entry_type: str | None = None,
    run_id: str | None = None,
    page_token: str | None = None,
    page_size: int = 200,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """List per-run cost entries for incremental billing sync."""
    handlers = RunHandlers(service)
    return await handlers.list_cost_entries(
        ctx,
        since=since,
        until=until,
        entry_type=entry_type,
        run_id=run_id,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/costs/summary", response_model=RunCostSummaryResponse)
async def summarize_costs(
    mode: str | None = None,
    kind: str | None = None,
    subject_kind: str | None = None,
    subject_id: str | None = None,
    subject_version_id: str | None = None,
    status: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs(
        ctx,
        mode=mode,
        kind=kind,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/costs/by-day", response_model=list[RunCostDailyResponse])
async def summarize_costs_by_day(
    mode: str | None = None,
    kind: str | None = None,
    subject_kind: str | None = None,
    subject_id: str | None = None,
    subject_version_id: str | None = None,
    status: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs by day."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs_by_day(
        ctx,
        mode=mode,
        kind=kind,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/costs/by-subject", response_model=list[RunCostBySubjectResponse])
async def summarize_costs_by_subject(
    mode: str | None = None,
    kind: str | None = None,
    subject_kind: str | None = None,
    subject_id: str | None = None,
    subject_version_id: str | None = None,
    status: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs by subject version."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs_by_subject(
        ctx,
        mode=mode,
        kind=kind,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/costs/by-mode", response_model=list[RunCostByModeResponse])
async def summarize_costs_by_mode(
    mode: str | None = None,
    subject_kind: str | None = None,
    subject_id: str | None = None,
    subject_version_id: str | None = None,
    status: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    kind: str | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs by mode."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs_by_mode(
        ctx,
        mode=mode,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
        kind=kind,
    )


@router.get("/costs/by-provider", response_model=list[RunCostByProviderResponse])
async def summarize_costs_by_provider(
    mode: str | None = None,
    kind: str | None = None,
    subject_kind: str | None = None,
    subject_id: str | None = None,
    subject_version_id: str | None = None,
    status: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs by provider."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs_by_provider(
        ctx,
        mode=mode,
        kind=kind,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/costs/by-model", response_model=list[RunCostByModelResponse])
async def summarize_costs_by_model(
    mode: str | None = None,
    kind: str | None = None,
    subject_kind: str | None = None,
    subject_id: str | None = None,
    subject_version_id: str | None = None,
    status: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs by model."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs_by_model(
        ctx,
        mode=mode,
        kind=kind,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("", response_model=PaginatedResponse[RunResponse])
async def list_runs(
    mode: str | None = None,
    kind: str | None = None,
    subject_kind: str | None = None,
    subject_id: str | None = None,
    subject_version_id: str | None = None,
    status: str | None = None,
    trace_id: str | None = None,
    user_id: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    include_observe_summary: bool = False,
    has_tool_call: bool | None = None,
    has_citation: bool | None = None,
    has_audit: bool | None = None,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """List runs."""
    handlers = RunHandlers(service)
    return await handlers.list_runs(
        ctx,
        mode=mode,
        kind=kind,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        trace_id=trace_id,
        user_id=user_id,
        started_after=started_after,
        started_before=started_before,
        include_observe_summary=include_observe_summary,
        has_tool_call=has_tool_call,
        has_citation=has_citation,
        has_audit=has_audit,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/export", response_class=Response)
async def export_runs_csv(
    mode: str | None = None,
    kind: str | None = None,
    subject_kind: str | None = None,
    subject_id: str | None = None,
    subject_version_id: str | None = None,
    status: str | None = None,
    trace_id: str | None = None,
    user_id: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    limit: int = 1000,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
) -> Response:
    """Export runs as CSV."""
    handlers = RunHandlers(service)
    csv_content = await handlers.export_runs_csv(
        ctx,
        mode=mode,
        kind=kind,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        trace_id=trace_id,
        user_id=user_id,
        started_after=started_after,
        started_before=started_before,
        limit=limit,
    )
    headers = {"Content-Disposition": "attachment; filename=runs.csv"}
    return Response(content=csv_content, media_type="text/csv", headers=headers)


@router.get("/steps/metrics", response_model=list[RunStepMetricsSummaryResponse])
async def summarize_step_metrics(
    run_id: str | None = None,
    trace_id: str | None = None,
    step_id: str | None = None,
    step_type: str | None = None,
    status: str | None = None,
    node_id: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    ended_after: datetime | None = None,
    ended_before: datetime | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run step metrics by type and status."""
    handlers = RunHandlers(service)
    return await handlers.summarize_step_metrics(
        ctx,
        run_id=run_id,
        trace_id=trace_id,
        step_id=step_id,
        step_type=step_type,
        status=status,
        node_id=node_id,
        started_after=started_after,
        started_before=started_before,
        ended_after=ended_after,
        ended_before=ended_before,
    )


@router.get("/steps", response_model=PaginatedResponse[RunStepResponse])
async def list_steps(
    run_id: str | None = None,
    trace_id: str | None = None,
    step_id: str | None = None,
    step_type: str | None = None,
    status: str | None = None,
    node_id: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    ended_after: datetime | None = None,
    ended_before: datetime | None = None,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """List run steps."""
    handlers = RunHandlers(service)
    return await handlers.list_steps(
        ctx,
        run_id=run_id,
        trace_id=trace_id,
        step_id=step_id,
        step_type=step_type,
        status=status,
        node_id=node_id,
        started_after=started_after,
        started_before=started_before,
        ended_after=ended_after,
        ended_before=ended_before,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/audits", response_model=PaginatedResponse[RunAuditLogResponse])
async def list_audits(
    run_id: str | None = None,
    step_id: str | None = None,
    step_type: str | None = None,
    gateway_type: str | None = None,
    page_token: str | None = None,
    page_size: int = 50,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """List audit logs derived from run steps."""
    handlers = RunHandlers(service)
    return await handlers.list_audits(
        ctx,
        run_id=run_id,
        step_id=step_id,
        step_type=step_type,
        gateway_type=gateway_type,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/trace/{trace_id}", response_model=PaginatedResponse[RunResponse])
async def list_runs_by_trace(
    trace_id: str,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """List runs by trace id."""
    handlers = RunHandlers(service)
    return await handlers.list_runs(
        ctx,
        trace_id=trace_id,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    last_event_id: str | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Stream run events and replay missed steps when possible."""
    handlers = SSEHandlers(service)

    async def generate():
        async for chunk in handlers.stream_run(ctx, run_id, last_event_id=last_event_id):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{run_id}/artifacts/{artifact_id}/content", response_class=Response)
async def download_run_artifact(
    run_id: str,
    artifact_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
    storage: StoragePort = Depends(get_run_artifact_storage),
):
    """Download governed Run artifact content without exposing its storage key."""

    del ctx
    artifact = service.get_artifact(run_id, artifact_id)
    content = await storage.get(artifact.storage_key)
    metadata = artifact.meta_json or {}
    filename = str(metadata.get("name") or metadata.get("filename") or artifact.id)
    encoded_filename = quote(filename, safe="")
    return Response(
        content=content,
        media_type=artifact.mime or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: str,
    include_steps: bool = True,
    include_artifacts: bool = True,
    include_cost: bool = True,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Get run detail."""
    handlers = RunHandlers(service)
    return await handlers.get_run(
        ctx,
        run_id,
        include_steps=include_steps,
        include_artifacts=include_artifacts,
        include_cost=include_cost,
    )
