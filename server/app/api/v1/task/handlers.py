"""Handlers for runtime task APIs."""

from __future__ import annotations

from typing import Optional

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.core.service import RuntimeCoreService
from app.kernel.runtime.query_service import RuntimeQueryService
from app.kernel.runtime.schemas import (
    TaskCheckpointResponse,
    TaskControlResponse,
    TaskDetailResponse,
    TaskEventResponse,
    TaskResponse,
)


class TaskHandlers:
    """Thin orchestration for task endpoints."""

    def __init__(
        self,
        service: RuntimeQueryService,
        runtime_service: RuntimeCoreService | None = None,
    ) -> None:
        self.service = service
        self.runtime_service = runtime_service

    async def list_tasks(
        self,
        ctx: RequestContext,
        *,
        status: Optional[str],
        task_type: Optional[str],
        agent_id: Optional[str],
        thread_id: Optional[str],
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[TaskResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        tasks = self.service.list_tasks(
            limit=limit,
            offset=offset,
            status=status,
            task_type=task_type,
            agent_id=agent_id,
            thread_id=thread_id,
        )
        items = [TaskResponse.model_validate(task) for task in tasks]
        has_next = len(tasks) == limit
        next_offset = offset + len(tasks) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def get_task(self, ctx: RequestContext, task_id: str) -> TaskDetailResponse:
        task = self.service.get_task(task_id)
        checkpoints = self.service.list_task_checkpoints(task_id)
        events = self.service.list_task_events(task_id)
        return TaskDetailResponse(
            task=TaskResponse.model_validate(task),
            checkpoints=[TaskCheckpointResponse.model_validate(item) for item in checkpoints],
            events=[TaskEventResponse.model_validate(item) for item in events],
        )

    async def cancel_task(self, ctx: RequestContext, task_id: str) -> TaskControlResponse:
        if not self.runtime_service:
            raise RuntimeError("Task runtime service is not configured")
        task = self.runtime_service.cancel_task(task_id=task_id)
        return TaskControlResponse(task=TaskResponse.model_validate(task), action="cancel")

    async def resume_task(self, ctx: RequestContext, task_id: str) -> TaskControlResponse:
        if not self.runtime_service:
            raise RuntimeError("Task runtime service is not configured")
        task = self.runtime_service.resume_task(task_id=task_id)
        return TaskControlResponse(task=TaskResponse.model_validate(task), action="resume")

    async def retry_task(self, ctx: RequestContext, task_id: str) -> TaskControlResponse:
        if not self.runtime_service:
            raise RuntimeError("Task runtime service is not configured")
        task = self.runtime_service.retry_task(task_id=task_id)
        return TaskControlResponse(task=TaskResponse.model_validate(task), action="retry")
