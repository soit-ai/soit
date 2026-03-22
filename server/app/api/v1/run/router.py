""" router

Run API routes (FastAPI).
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Response

from app.kernel.contracts.context import RequestContext
from app.api.v1.permissions import require_workspace_read_ctx
from app.infra.db.pagination import PaginatedResponse
from app.kernel.trace.schemas import (
    RunResponse,
    RunDetailResponse,
    RunCostSummaryResponse,
    RunCostDailyResponse,
    RunCostBySubjectResponse,
    RunCostByModeResponse,
    RunCostByProviderResponse,
    RunCostByModelResponse,
    RunStepResponse,
    RunStepMetricsSummaryResponse,
    RunAuditLogResponse,
)
from app.kernel.trace.service import RunService
from app.api.v1.run.dependencies import get_run_service
from app.api.v1.run.handlers import RunHandlers


router = APIRouter()


@router.get("/costs/summary", response_model=RunCostSummaryResponse)
async def summarize_costs(
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    workflow_id: Optional[str] = None,
    subject_kind: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_version_id: Optional[str] = None,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs(
        ctx,
        mode=mode,
        kind=kind,
        workflow_id=workflow_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/costs/by-day", response_model=list[RunCostDailyResponse])
async def summarize_costs_by_day(
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    workflow_id: Optional[str] = None,
    subject_kind: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_version_id: Optional[str] = None,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs by day."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs_by_day(
        ctx,
        mode=mode,
        kind=kind,
        workflow_id=workflow_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/costs/by-subject", response_model=list[RunCostBySubjectResponse])
async def summarize_costs_by_subject(
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    workflow_id: Optional[str] = None,
    subject_kind: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_version_id: Optional[str] = None,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs by subject version."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs_by_subject(
        ctx,
        mode=mode,
        kind=kind,
        workflow_id=workflow_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/costs/by-mode", response_model=list[RunCostByModeResponse])
async def summarize_costs_by_mode(
    mode: Optional[str] = None,
    workflow_id: Optional[str] = None,
    subject_kind: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_version_id: Optional[str] = None,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    kind: Optional[str] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs by mode."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs_by_mode(
        ctx,
        mode=mode,
        workflow_id=workflow_id,
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
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    workflow_id: Optional[str] = None,
    subject_kind: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_version_id: Optional[str] = None,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs by provider."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs_by_provider(
        ctx,
        mode=mode,
        kind=kind,
        workflow_id=workflow_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/costs/by-model", response_model=list[RunCostByModelResponse])
async def summarize_costs_by_model(
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    workflow_id: Optional[str] = None,
    subject_kind: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_version_id: Optional[str] = None,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RunService = Depends(get_run_service),
):
    """Summarize run costs by model."""
    handlers = RunHandlers(service)
    return await handlers.summarize_costs_by_model(
        ctx,
        mode=mode,
        kind=kind,
        workflow_id=workflow_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("", response_model=PaginatedResponse[RunResponse])
async def list_runs(
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    workflow_id: Optional[str] = None,
    subject_kind: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_version_id: Optional[str] = None,
    status: Optional[str] = None,
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    page_token: Optional[str] = None,
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
        workflow_id=workflow_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
        status=status,
        trace_id=trace_id,
        user_id=user_id,
        started_after=started_after,
        started_before=started_before,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/export", response_class=Response)
async def export_runs_csv(
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    workflow_id: Optional[str] = None,
    subject_kind: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_version_id: Optional[str] = None,
    status: Optional[str] = None,
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
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
        workflow_id=workflow_id,
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
    run_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    step_id: Optional[str] = None,
    step_type: Optional[str] = None,
    status: Optional[str] = None,
    node_id: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ended_after: Optional[datetime] = None,
    ended_before: Optional[datetime] = None,
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
    run_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    step_id: Optional[str] = None,
    step_type: Optional[str] = None,
    status: Optional[str] = None,
    node_id: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ended_after: Optional[datetime] = None,
    ended_before: Optional[datetime] = None,
    page_token: Optional[str] = None,
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
    run_id: str,
    step_id: Optional[str] = None,
    page_token: Optional[str] = None,
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
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/trace/{trace_id}", response_model=PaginatedResponse[RunResponse])
async def list_runs_by_trace(
    trace_id: str,
    page_token: Optional[str] = None,
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
