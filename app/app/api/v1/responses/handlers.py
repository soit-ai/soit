"""Thin request handlers for Responses resource/projection endpoints."""

from __future__ import annotations

from typing import Optional

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.kernel.responses.schemas import (
    ResponseCancelResult,
    ResponseCreateRequest,
    ResponseDetailRead,
    ResponseEventRead,
    ResponseRead,
    ResponseTimelineItemRead,
    RunResponseTimelineRead,
    ToolCallRead,
)
from app.kernel.responses.service import ResponseService


class ResponseHandlers:
    """HTTP-facing handling for response resources and semantic projections."""

    def __init__(self, service: ResponseService) -> None:
        self.service = service

    async def create_response(self, ctx: RequestContext, payload: ResponseCreateRequest) -> ResponseRead:
        del ctx
        return ResponseRead.model_validate(self.service.create_response(payload))

    async def get_response(self, ctx: RequestContext, response_id: str) -> ResponseRead:
        del ctx
        return ResponseRead.model_validate(self.service.get_response(response_id))

    async def get_response_detail(self, ctx: RequestContext, response_id: str) -> ResponseDetailRead:
        del ctx
        response, events, tool_calls = self.service.get_response_detail(response_id)
        return ResponseDetailRead(
            response=ResponseRead.model_validate(response),
            events=[ResponseEventRead.model_validate(item) for item in events],
            tool_calls=[ToolCallRead.model_validate(item) for item in tool_calls],
        )

    async def get_run_timeline(self, ctx: RequestContext, run_id: str) -> RunResponseTimelineRead:
        del ctx
        timeline = self.service.get_run_timeline(run_id)
        return RunResponseTimelineRead(
            run_id=timeline["run_id"],
            items=[
                ResponseTimelineItemRead(
                    response=ResponseRead.model_validate(item["response"]),
                    events=[ResponseEventRead.model_validate(event) for event in item["events"]],
                    tool_calls=[ToolCallRead.model_validate(tool_call) for tool_call in item["tool_calls"]],
                )
                for item in timeline["items"]
            ],
        )

    async def list_response_events(
        self,
        ctx: RequestContext,
        response_id: str,
        *,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[ResponseEventRead]:
        del ctx
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        limit_plus = limit + 1
        events = self.service.list_response_events(response_id, limit=limit_plus, offset=offset)
        has_next = len(events) > limit
        items = [ResponseEventRead.model_validate(item) for item in events[:limit]]
        next_offset = offset + len(items) if has_next else None
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def cancel_response(self, ctx: RequestContext, response_id: str) -> ResponseCancelResult:
        del ctx
        response = self.service.cancel_response(response_id)
        return ResponseCancelResult(
            response=ResponseRead.model_validate(response),
            action="cancel",
        )
