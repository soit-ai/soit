"""Routes for the northbound Responses resource and semantic event API."""

import json

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.api.v1.responses.dependencies import (
    get_response_projection_coordinator,
    get_response_service,
)
from app.api.v1.responses.handlers import ResponseHandlers
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.responses.orchestrator import ResponseProjectionCoordinator
from app.kernel.runtime.responses.schemas import (
    ResponseCancelResult,
    ResponseCreateRequest,
    ResponseDetailRead,
    ResponseEventRead,
    ResponseRead,
    RunResponseTimelineRead,
)
from app.kernel.runtime.responses.service import ResponseService

router = APIRouter()


def _format_sse(event_type: str, payload: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("", response_model=ResponseRead, status_code=status.HTTP_201_CREATED)
async def create_response(
    payload: ResponseCreateRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    projection_coordinator: ResponseProjectionCoordinator = Depends(get_response_projection_coordinator),
):
    """Create a response resource and expose semantics for the underlying run."""

    del ctx
    if payload.stream:
        async def generate():
            async for item in projection_coordinator.execute_stream(payload):
                yield _format_sse(item["event"], item["data"])
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    response = await projection_coordinator.execute(payload)
    return ResponseRead.model_validate(response)


@router.get("/by-run/{run_id}", response_model=RunResponseTimelineRead)
async def get_run_response_timeline(
    run_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """Read response semantic projections grouped under a run."""

    handlers = ResponseHandlers(service)
    return await handlers.get_run_timeline(ctx, run_id)


@router.get("/{response_id}", response_model=ResponseRead)
async def get_response(
    response_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """Read a response resource projection."""

    handlers = ResponseHandlers(service)
    return await handlers.get_response(ctx, response_id)


@router.get("/{response_id}/detail", response_model=ResponseDetailRead)
async def get_response_detail(
    response_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """Read a response projection with semantic events and tool-call projections."""

    handlers = ResponseHandlers(service)
    return await handlers.get_response_detail(ctx, response_id)


@router.get("/{response_id}/events", response_model=PaginatedResponse[ResponseEventRead])
async def list_response_events(
    response_id: str,
    page_token: str | None = None,
    page_size: int = 100,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """List persisted response semantic events."""

    handlers = ResponseHandlers(service)
    return await handlers.list_response_events(
        ctx,
        response_id,
        page_token=page_token,
        page_size=page_size,
    )


@router.get(
    "/{response_id}/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "text/event-stream": {"schema": {"type": "string"}},
            }
        }
    },
)
async def stream_response_events(
    response_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """Replay persisted response events as SSE."""

    del ctx

    async def generate():
        events = service.list_response_events(response_id, limit=1000, offset=0)
        for event in events:
            yield _format_sse(event.type, event.payload_json)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{response_id}/cancel", response_model=ResponseCancelResult)
async def cancel_response(
    response_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """Cancel a response resource projection."""

    handlers = ResponseHandlers(service)
    return await handlers.cancel_response(ctx, response_id)
