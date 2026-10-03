"""Handlers for observe governance APIs."""

from __future__ import annotations

from typing import Any

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.modules.observe.application.dashboard_schemas import WorkspaceObserveDashboard
from app.modules.observe.application.schemas import (
    ApprovalCreate,
    ApprovalDecisionResponse,
    ApprovalDelegate,
    ApprovalResolve,
    ApprovalResponse,
    FeedbackCreate,
    FeedbackResponse,
    RunReplayResponse,
)
from app.modules.observe.application.service import ObserveService


async def _view(service: ObserveService, approval: Any) -> ApprovalResponse:
    """A request as the caller sees it, with what the caller may do with it."""

    return ApprovalResponse.model_validate(approval).model_copy(update=await service.caller_rights(approval))


class ObserveHandlers:
    def __init__(self, service: ObserveService) -> None:
        self.service = service

    async def create_approval(self, ctx: RequestContext, payload: ApprovalCreate) -> ApprovalResponse:
        return await _view(self.service, await self.service.create_approval(payload))

    async def list_approvals(
        self,
        ctx: RequestContext,
        *,
        status: str | None,
        run_id: str | None,
        task_id: str | None,
        page_token: str | None,
        page_size: int,
    ) -> PaginatedResponse[ApprovalResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        items = await self.service.list_approvals(
            limit=limit,
            offset=offset,
            status=status,
            run_id=run_id,
            task_id=task_id,
        )
        payload = [await _view(self.service, item) for item in items]
        has_next = len(items) == limit
        next_offset = offset + len(items) if has_next else None
        return PaginatedResponse.create(items=payload, page_size=len(payload), has_next=has_next, next_offset=next_offset)

    async def get_approval(self, ctx: RequestContext, approval_id: str) -> ApprovalResponse:
        return await _view(self.service, await self.service.get_approval(approval_id))

    async def resolve_approval(
        self,
        ctx: RequestContext,
        approval_id: str,
        payload: ApprovalResolve,
    ) -> ApprovalResponse:
        return await _view(self.service, await self.service.resolve_approval(approval_id, payload))

    async def delegate_approval(
        self,
        ctx: RequestContext,
        approval_id: str,
        payload: ApprovalDelegate,
    ) -> ApprovalResponse:
        return await _view(self.service, await self.service.delegate_approval(approval_id, payload))

    async def list_approval_decisions(self, ctx: RequestContext, approval_id: str) -> list[ApprovalDecisionResponse]:
        return [
            ApprovalDecisionResponse.model_validate(item)
            for item in await self.service.list_approval_decisions(approval_id)
        ]

    async def create_feedback(self, ctx: RequestContext, payload: FeedbackCreate) -> FeedbackResponse:
        return FeedbackResponse.model_validate(await self.service.create_feedback(payload))

    async def list_feedback(
        self,
        ctx: RequestContext,
        *,
        run_id: str | None,
        agent_id: str | None,
        thread_id: str | None,
        page_token: str | None,
        page_size: int,
    ) -> PaginatedResponse[FeedbackResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        items = await self.service.list_feedback(
            limit=limit,
            offset=offset,
            run_id=run_id,
            agent_id=agent_id,
            thread_id=thread_id,
        )
        payload = [FeedbackResponse.model_validate(item) for item in items]
        has_next = len(items) == limit
        next_offset = offset + len(items) if has_next else None
        return PaginatedResponse.create(items=payload, page_size=len(payload), has_next=has_next, next_offset=next_offset)

    async def get_run_replay(self, ctx: RequestContext, run_id: str) -> RunReplayResponse:
        return RunReplayResponse.model_validate(await self.service.get_run_replay(run_id))

    async def get_dashboard(
        self,
        ctx: RequestContext,
        *,
        tab: str,
        range_label: str,
        bucket_label: str,
        q: str | None,
        workspace_scope: str,
        page_token: str | None,
        page_size: int,
    ) -> WorkspaceObserveDashboard:
        return WorkspaceObserveDashboard.model_validate(
            await self.service.get_dashboard(
                tab=tab,
                range_label=range_label,
                bucket_label=bucket_label,
                q=q,
                workspace_scope=workspace_scope,
                page_token=page_token,
                page_size=page_size,
            )
        )
