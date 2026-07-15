"""Observe governance routes."""


from fastapi import APIRouter, Depends, status

from app.api.v1.observe.dependencies import get_observe_service
from app.api.v1.observe.handlers import ObserveHandlers
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.modules.observe.application.dashboard_schemas import WorkspaceObserveDashboard
from app.modules.observe.application.schemas import (
    ApprovalCreate,
    ApprovalResolve,
    ApprovalResponse,
    FeedbackCreate,
    FeedbackResponse,
    RunReplayResponse,
)
from app.modules.observe.application.service import ObserveService

router = APIRouter()


@router.get("/dashboard", response_model=WorkspaceObserveDashboard)
async def get_dashboard(
    tab: str = "agent_health",
    range: str = "24h",
    bucket: str = "10m",
    q: str | None = None,
    workspace_scope: str = "all",
    page_token: str | None = None,
    page_size: int = 10,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ObserveService = Depends(get_observe_service),
):
    return await ObserveHandlers(service).get_dashboard(
        ctx,
        tab=tab,
        range_label=range,
        bucket_label=bucket,
        q=q,
        workspace_scope=workspace_scope,
        page_token=page_token,
        page_size=page_size,
    )


@router.post("/approvals", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
async def create_approval(
    payload: ApprovalCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ObserveService = Depends(get_observe_service),
):
    return await ObserveHandlers(service).create_approval(ctx, payload)


@router.get("/approvals", response_model=PaginatedResponse[ApprovalResponse])
async def list_approvals(
    status: str | None = None,
    run_id: str | None = None,
    task_id: str | None = None,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ObserveService = Depends(get_observe_service),
):
    return await ObserveHandlers(service).list_approvals(
        ctx,
        status=status,
        run_id=run_id,
        task_id=task_id,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/approvals/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ObserveService = Depends(get_observe_service),
):
    return await ObserveHandlers(service).get_approval(ctx, approval_id)


@router.post("/approvals/{approval_id}/resolve", response_model=ApprovalResponse)
async def resolve_approval(
    approval_id: str,
    payload: ApprovalResolve,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ObserveService = Depends(get_observe_service),
):
    return await ObserveHandlers(service).resolve_approval(ctx, approval_id, payload)


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ObserveService = Depends(get_observe_service),
):
    return await ObserveHandlers(service).create_feedback(ctx, payload)


@router.get("/feedback", response_model=PaginatedResponse[FeedbackResponse])
async def list_feedback(
    run_id: str | None = None,
    agent_id: str | None = None,
    thread_id: str | None = None,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ObserveService = Depends(get_observe_service),
):
    return await ObserveHandlers(service).list_feedback(
        ctx,
        run_id=run_id,
        agent_id=agent_id,
        thread_id=thread_id,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/runs/{run_id}/replay", response_model=RunReplayResponse)
async def get_run_replay(
    run_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ObserveService = Depends(get_observe_service),
):
    return await ObserveHandlers(service).get_run_replay(ctx, run_id)
