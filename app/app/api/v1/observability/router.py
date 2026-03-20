"""Observability governance routes."""

from typing import Optional

from fastapi import APIRouter, Depends, status

from app.api.v1.observability.dependencies import get_observability_service
from app.api.v1.observability.handlers import ObservabilityHandlers
from app.api.v1.permissions import require_workspace_read_ctx, require_workspace_write_ctx
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.modules.observability.application.schemas import (
    ApprovalCreate,
    ApprovalResolve,
    ApprovalResponse,
    FeedbackCreate,
    FeedbackResponse,
    RunReplayResponse,
)
from app.modules.observability.application.service import ObservabilityService


router = APIRouter()


@router.post("/approvals", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
async def create_approval(
    payload: ApprovalCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ObservabilityService = Depends(get_observability_service),
):
    return await ObservabilityHandlers(service).create_approval(ctx, payload)


@router.get("/approvals", response_model=PaginatedResponse[ApprovalResponse])
async def list_approvals(
    status: Optional[str] = None,
    run_id: Optional[str] = None,
    task_id: Optional[str] = None,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ObservabilityService = Depends(get_observability_service),
):
    return await ObservabilityHandlers(service).list_approvals(
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
    service: ObservabilityService = Depends(get_observability_service),
):
    return await ObservabilityHandlers(service).get_approval(ctx, approval_id)


@router.post("/approvals/{approval_id}/resolve", response_model=ApprovalResponse)
async def resolve_approval(
    approval_id: str,
    payload: ApprovalResolve,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ObservabilityService = Depends(get_observability_service),
):
    return await ObservabilityHandlers(service).resolve_approval(ctx, approval_id, payload)


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ObservabilityService = Depends(get_observability_service),
):
    return await ObservabilityHandlers(service).create_feedback(ctx, payload)


@router.get("/feedback", response_model=PaginatedResponse[FeedbackResponse])
async def list_feedback(
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ObservabilityService = Depends(get_observability_service),
):
    return await ObservabilityHandlers(service).list_feedback(
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
    service: ObservabilityService = Depends(get_observability_service),
):
    return await ObservabilityHandlers(service).get_run_replay(ctx, run_id)
