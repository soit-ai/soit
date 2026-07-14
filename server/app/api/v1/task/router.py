"""Runtime task API routes."""

from typing import Optional

from fastapi import APIRouter, Depends

from app.api.v1.permissions import require_workspace_read_ctx, require_workspace_write_ctx
from app.api.v1.task.dependencies import get_task_runtime_service, get_task_service
from app.api.v1.task.handlers import TaskHandlers
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.core.service import RuntimeCoreService
from app.kernel.runtime.query_service import RuntimeQueryService
from app.kernel.runtime.schemas import (
    TaskControlResponse,
    TaskDetailResponse,
    TaskHandlingResponse,
    TaskResponse,
    TaskWorkbenchItemsResponse,
    TaskWorkbenchResponse,
)


router = APIRouter()


@router.get("", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    agent_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RuntimeQueryService = Depends(get_task_service),
):
    """List runtime tasks."""

    handlers = TaskHandlers(service)
    return await handlers.list_tasks(
        ctx,
        status=status,
        task_type=task_type,
        agent_id=agent_id,
        thread_id=thread_id,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/workbench", response_model=TaskWorkbenchResponse)
async def get_task_workbench(
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RuntimeQueryService = Depends(get_task_service),
):
    """Get runtime task workbench metrics and rows."""

    handlers = TaskHandlers(service)
    return await handlers.get_workbench(ctx, page_token=page_token, page_size=page_size)


@router.get("/workbench/items", response_model=TaskWorkbenchItemsResponse)
async def get_task_workbench_items(
    tab: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RuntimeQueryService = Depends(get_task_service),
):
    """Get filtered runtime task workbench rows."""

    handlers = TaskHandlers(service)
    return await handlers.get_workbench_items(
        ctx,
        tab=tab,
        keyword=keyword,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/{task_id}/handling", response_model=TaskHandlingResponse)
async def get_task_handling(
    task_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RuntimeQueryService = Depends(get_task_service),
):
    """Get task handling drawer read model."""

    handlers = TaskHandlers(service)
    return await handlers.get_task_handling(ctx, task_id)


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RuntimeQueryService = Depends(get_task_service),
):
    """Get task detail."""

    handlers = TaskHandlers(service)
    return await handlers.get_task(ctx, task_id)


@router.post("/{task_id}/cancel", response_model=TaskControlResponse)
async def cancel_task(
    task_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: RuntimeQueryService = Depends(get_task_service),
    runtime_service: RuntimeCoreService = Depends(get_task_runtime_service),
):
    """Cancel a task."""

    handlers = TaskHandlers(service, runtime_service)
    return await handlers.cancel_task(ctx, task_id)


@router.post("/{task_id}/resume", response_model=TaskControlResponse)
async def resume_task(
    task_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: RuntimeQueryService = Depends(get_task_service),
    runtime_service: RuntimeCoreService = Depends(get_task_runtime_service),
):
    """Resume a paused or waiting task."""

    handlers = TaskHandlers(service, runtime_service)
    return await handlers.resume_task(ctx, task_id)


@router.post("/{task_id}/retry", response_model=TaskControlResponse)
async def retry_task(
    task_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: RuntimeQueryService = Depends(get_task_service),
    runtime_service: RuntimeCoreService = Depends(get_task_runtime_service),
):
    """Retry a failed task."""

    handlers = TaskHandlers(service, runtime_service)
    return await handlers.retry_task(ctx, task_id)
