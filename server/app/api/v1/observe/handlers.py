"""Handlers for observe governance APIs."""

from __future__ import annotations

from typing import Optional

from app.infra.db.pagination import PaginatedResponse, parse_page_params
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


class ObserveHandlers:
    def __init__(self, service: ObserveService) -> None:
        self.service = service

    async def create_approval(self, ctx: RequestContext, payload: ApprovalCreate) -> ApprovalResponse:
        return ApprovalResponse.model_validate(await self.service.create_approval(payload))

    async def list_approvals(
        self,
        ctx: RequestContext,
        *,
        status: Optional[str],
        run_id: Optional[str],
        task_id: Optional[str],
        page_token: Optional[str],
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
        payload = [ApprovalResponse.model_validate(item) for item in items]
        has_next = len(items) == limit
        next_offset = offset + len(items) if has_next else None
        return PaginatedResponse.create(items=payload, page_size=len(payload), has_next=has_next, next_offset=next_offset)

    async def get_approval(self, ctx: RequestContext, approval_id: str) -> ApprovalResponse:
        return ApprovalResponse.model_validate(await self.service.get_approval(approval_id))

    async def resolve_approval(
        self,
        ctx: RequestContext,
        approval_id: str,
        payload: ApprovalResolve,
    ) -> ApprovalResponse:
        return ApprovalResponse.model_validate(await self.service.resolve_approval(approval_id, payload))

    async def create_feedback(self, ctx: RequestContext, payload: FeedbackCreate) -> FeedbackResponse:
        return FeedbackResponse.model_validate(await self.service.create_feedback(payload))

    async def list_feedback(
        self,
        ctx: RequestContext,
        *,
        run_id: Optional[str],
        agent_id: Optional[str],
        thread_id: Optional[str],
        page_token: Optional[str],
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
        q: Optional[str],
        workspace_scope: str,
        page_token: Optional[str],
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
