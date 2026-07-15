"""Agent thread API routes."""


from fastapi import APIRouter, Depends, status

from app.api.v1.agent.thread_dependencies import (
    get_thread_query_service,
    get_thread_runtime_service,
)
from app.api.v1.agent.thread_handlers import ThreadHandlers
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.threads.schemas import (
    ThreadCreateRequest,
    ThreadDetailResponse,
    ThreadResponse,
    ThreadUpdateRequest,
)
from app.kernel.runtime.threads.service import ThreadService
from app.modules.agent.application.thread_query_service import AgentThreadQueryService

router = APIRouter()


@router.post("", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    payload: ThreadCreateRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    runtime_service: ThreadService = Depends(get_thread_runtime_service),
    query_service: AgentThreadQueryService = Depends(get_thread_query_service),
):
    """Create an agent thread."""

    handlers = ThreadHandlers(query_service=query_service, runtime_service=runtime_service)
    return await handlers.create_thread(ctx, payload)


@router.get("", response_model=PaginatedResponse[ThreadResponse])
async def list_threads(
    status: str | None = None,
    agent_id: str | None = None,
    search: str | None = None,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentThreadQueryService = Depends(get_thread_query_service),
):
    """List agent threads."""

    handlers = ThreadHandlers(query_service=service)
    return await handlers.list_threads(
        ctx,
        status=status,
        agent_id=agent_id,
        search=search,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(
    thread_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentThreadQueryService = Depends(get_thread_query_service),
):
    """Get thread detail."""

    handlers = ThreadHandlers(query_service=service)
    return await handlers.get_thread(ctx, thread_id)


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: str,
    payload: ThreadUpdateRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    query_service: AgentThreadQueryService = Depends(get_thread_query_service),
    runtime_service: ThreadService = Depends(get_thread_runtime_service),
):
    """Update a runtime thread."""

    handlers = ThreadHandlers(query_service=query_service, runtime_service=runtime_service)
    return await handlers.update_thread(ctx, thread_id, payload)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    query_service: AgentThreadQueryService = Depends(get_thread_query_service),
    runtime_service: ThreadService = Depends(get_thread_runtime_service),
):
    """Soft-delete a runtime thread."""

    handlers = ThreadHandlers(query_service=query_service, runtime_service=runtime_service)
    await handlers.delete_thread(ctx, thread_id)
