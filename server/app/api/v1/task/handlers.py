"""Handlers for runtime task APIs."""

from __future__ import annotations

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.tasks.query_service import TaskQueryService
from app.kernel.runtime.tasks.schemas import (
    TaskCheckpointResponse,
    TaskControlResponse,
    TaskDetailResponse,
    TaskEventResponse,
    TaskHandlingResponse,
    TaskResponse,
    TaskWorkbenchItemsResponse,
    TaskWorkbenchResponse,
)
from app.kernel.runtime.tasks.service import TaskService


class TaskHandlers:
    """Thin orchestration for task endpoints."""

    def __init__(
        self,
        service: TaskQueryService,
        runtime_service: TaskService | None = None,
    ) -> None:
        self.service = service
        self.runtime_service = runtime_service

    async def list_tasks(
        self,
        ctx: RequestContext,
        *,
        status: str | None,
        task_type: str | None,
        agent_id: str | None,
        thread_id: str | None,
        page_token: str | None,
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

    async def get_workbench(
        self,
        ctx: RequestContext,
        *,
        page_token: str | None,
        page_size: int,
    ) -> TaskWorkbenchResponse:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        return self.service.get_task_workbench(limit=limit, offset=offset)

    async def get_workbench_items(
        self,
        ctx: RequestContext,
        *,
        tab: str | None,
        keyword: str | None,
        status: str | None,
        date_from: str | None,
        date_to: str | None,
        page_token: str | None,
        page_size: int,
    ) -> TaskWorkbenchItemsResponse:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        return self.service.get_task_workbench_items(
            limit=limit,
            offset=offset,
            tab=tab,
            keyword=keyword,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

    async def get_task(self, ctx: RequestContext, task_id: str) -> TaskDetailResponse:
        task = self.service.get_task(task_id)
        checkpoints = self.service.list_task_checkpoints(task_id)
        events = self.service.list_task_events(task_id)
        return TaskDetailResponse(
            task=TaskResponse.model_validate(task),
            checkpoints=[TaskCheckpointResponse.model_validate(item) for item in checkpoints],
            events=[TaskEventResponse.model_validate(item) for item in events],
            available_actions=self.service.available_actions(task),
        )

    async def get_task_handling(self, ctx: RequestContext, task_id: str) -> TaskHandlingResponse:
        return self.service.get_task_handling(task_id)

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
