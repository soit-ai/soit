"""Handlers for runtime task APIs."""

from __future__ import annotations

from datetime import datetime

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.runs.knowledge_redaction import (
    KnowledgeRedactor,
    redact_task_payload,
)
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

_TASK_FIELDS = ("input_json", "output_json", "progress_json")


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
        since: datetime | None = None,
        until: datetime | None = None,
        with_total: bool = False,
    ) -> PaginatedResponse[TaskResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        tasks = await self.service.list_tasks(
            limit=limit,
            offset=offset,
            status=status,
            task_type=task_type,
            agent_id=agent_id,
            thread_id=thread_id,
            since=since,
            until=until,
        )
        redactor = self._redactor(ctx)
        items = [await self._readable(redactor, TaskResponse.model_validate(task), _TASK_FIELDS) for task in tasks]
        has_next = len(tasks) == limit
        next_offset = offset + len(tasks) if has_next else None
        total = (
            await self.service.count_tasks(
                status=status,
                task_type=task_type,
                agent_id=agent_id,
                thread_id=thread_id,
                since=since,
                until=until,
            )
            if with_total
            else None
        )
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
            total=total,
        )

    async def get_workbench(
        self,
        ctx: RequestContext,
        *,
        page_token: str | None,
        page_size: int,
    ) -> TaskWorkbenchResponse:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        return await self.service.get_task_workbench(limit=limit, offset=offset)

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
        return await self.service.get_task_workbench_items(
            limit=limit,
            offset=offset,
            tab=tab,
            keyword=keyword,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

    def _redactor(self, ctx: RequestContext) -> KnowledgeRedactor:
        return KnowledgeRedactor(getattr(self.service, "db", None), ctx)

    @staticmethod
    async def _readable(redactor: KnowledgeRedactor, model, fields: tuple[str, ...]):
        """A task read model with knowledge its reader may not read left out."""
        update = {}
        for field in fields:
            value = getattr(model, field, None)
            redacted = await redact_task_payload(redactor, value)
            if redacted is not value:
                update[field] = redacted
        return model.model_copy(update=update) if update else model

    async def get_task(self, ctx: RequestContext, task_id: str) -> TaskDetailResponse:
        task = await self.service.get_task(task_id)
        checkpoints = await self.service.list_task_checkpoints(task_id)
        events = await self.service.list_task_events(task_id)
        redactor = self._redactor(ctx)
        return TaskDetailResponse(
            task=await self._readable(redactor, TaskResponse.model_validate(task), _TASK_FIELDS),
            checkpoints=[
                await self._readable(redactor, TaskCheckpointResponse.model_validate(item), ("payload_json",))
                for item in checkpoints
            ],
            events=[
                await self._readable(redactor, TaskEventResponse.model_validate(item), ("payload_json",))
                for item in events
            ],
            available_actions=self.service.available_actions(task),
        )

    async def get_task_handling(self, ctx: RequestContext, task_id: str) -> TaskHandlingResponse:
        handling = await self.service.get_task_handling(task_id)
        redactor = self._redactor(ctx)
        return handling.model_copy(
            update={
                "task": await self._readable(redactor, handling.task, _TASK_FIELDS),
                "events": [await self._readable(redactor, item, ("payload_json",)) for item in handling.events],
                "checkpoints": [
                    await self._readable(redactor, item, ("payload_json",)) for item in handling.checkpoints
                ],
            }
        )

    async def cancel_task(self, ctx: RequestContext, task_id: str) -> TaskControlResponse:
        if not self.runtime_service:
            raise RuntimeError("Task runtime service is not configured")
        task = await self.runtime_service.cancel_task(task_id=task_id)
        return TaskControlResponse(task=TaskResponse.model_validate(task), action="cancel")

    async def resume_task(self, ctx: RequestContext, task_id: str) -> TaskControlResponse:
        if not self.runtime_service:
            raise RuntimeError("Task runtime service is not configured")
        task = await self.runtime_service.resume_task(task_id=task_id)
        return TaskControlResponse(task=TaskResponse.model_validate(task), action="resume")

    async def retry_task(self, ctx: RequestContext, task_id: str) -> TaskControlResponse:
        if not self.runtime_service:
            raise RuntimeError("Task runtime service is not configured")
        task = await self.runtime_service.retry_task(task_id=task_id)
        return TaskControlResponse(task=TaskResponse.model_validate(task), action="retry")
