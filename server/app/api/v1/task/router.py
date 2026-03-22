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
from app.kernel.runtime.schemas import TaskControlResponse, TaskDetailResponse, TaskResponse


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
