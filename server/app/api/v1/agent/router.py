""" router

Agent API routes (FastAPI).
"""

from dataclasses import asdict

from fastapi import APIRouter, Body, Depends, status
from fastapi.responses import StreamingResponse

from app.api.v1.agent.dependencies import (
    get_agent_application_service,
    get_agent_service,
)
from app.api.v1.agent.handlers import AgentAppHandlers, AgentHandlers
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.api.v1.responses.dependencies import get_response_projection_coordinator
from app.api.v1.responses.interaction_stream import stream_claimed_interaction
from app.infra.db.pagination import PaginatedResponse
from app.kernel.commons.errors import ConflictError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import RESOURCE_AGENT, require_resource_run_async
from app.kernel.runtime.db.models.responses import generate_response_interaction_id
from app.kernel.runtime.db.models.threads import generate_thread_message_id
from app.kernel.runtime.responses.orchestrator import ResponseProjectionCoordinator
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.schemas import (
    AgentBindingResponse,
    AgentCancelResponse,
    AgentCapabilityResponse,
    AgentCreate,
    AgentPublishRequest,
    AgentReleaseResponse,
    AgentResponse,
    AgentRollbackRequest,
    AgentRunRequest,
    AgentRunResponse,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionResponse,
    AgentWorkbenchItemsResponse,
    AgentWorkbenchResponse,
)
from app.modules.agent.application.service import AgentService
from app.settings.settings import settings

router = APIRouter()


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(
    data: AgentRunRequest = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AgentService = Depends(get_agent_service),
):
    handlers = AgentHandlers(service)
    return await handlers.run(ctx, data)


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_in: AgentCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.create_agent(ctx, agent_in)


@router.get("", response_model=PaginatedResponse[AgentResponse])
async def list_agents(
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.list_agents(ctx, page_token=page_token, page_size=page_size)


@router.get("/workbench", response_model=AgentWorkbenchResponse)
async def get_agent_workbench(
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.get_workbench(ctx, page_token=page_token, page_size=page_size)


@router.get("/workbench/items", response_model=AgentWorkbenchItemsResponse)
async def list_agent_workbench_items(
    tab: str | None = None,
    keyword: str | None = None,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.get_workbench_items(
        ctx,
        page_token=page_token,
        page_size=page_size,
        tab=tab,
        keyword=keyword,
    )


@router.get("/capabilities", response_model=PaginatedResponse[AgentCapabilityResponse])
async def list_agent_capabilities(
    kind: str | None = None,
    source_kind: str | None = None,
    page_token: str | None = None,
    page_size: int = 200,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.list_capabilities(
        ctx,
        kind=kind,
        source_kind=source_kind,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.get_agent(ctx, agent_id)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent_in: AgentUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.update_agent(ctx, agent_id, agent_in)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    await handlers.delete_agent(ctx, agent_id)


@router.post("/{agent_id}/versions", response_model=AgentVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_version(
    agent_id: str,
    version_in: AgentVersionCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.create_version(ctx, agent_id, version_in)


@router.get("/{agent_id}/versions", response_model=PaginatedResponse[AgentVersionResponse])
async def list_versions(
    agent_id: str,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.list_versions(ctx, agent_id, page_token=page_token, page_size=page_size)


@router.get("/{agent_id}/releases", response_model=PaginatedResponse[AgentReleaseResponse])
async def list_releases(
    agent_id: str,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.list_releases(ctx, agent_id, page_token=page_token, page_size=page_size)


@router.get("/{agent_id}/bindings", response_model=list[AgentBindingResponse])
async def list_bindings(
    agent_id: str,
    version_id: str | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.list_bindings(ctx, agent_id, version_id)


@router.post("/{agent_id}/publish", response_model=AgentResponse)
async def publish_version(
    agent_id: str,
    data: AgentPublishRequest = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.publish_version(ctx, agent_id, data)


@router.post("/{agent_id}/rollback", response_model=AgentResponse)
async def rollback_version(
    agent_id: str,
    data: AgentRollbackRequest = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.rollback_version(ctx, agent_id, data)


@router.post("/{agent_id}/execute", response_model=AgentRunResponse)
async def execute_agent(
    agent_id: str,
    data: AgentRunRequest = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.execute_agent(ctx, agent_id, data)


@router.post(
    "/{agent_id}/stream",
    deprecated=True,
    summary="Deprecated: stream agent execution (use POST /v1/responses)",
)
async def stream_agent(
    agent_id: str,
    data: AgentRunRequest = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    projection_coordinator: ResponseProjectionCoordinator = Depends(
        get_response_projection_coordinator
    ),
):
    """Stream agent execution events via SSE.

    Deprecated in favour of `POST /v1/responses`, which is the supported
    transport for agent streaming. This route now shares that path's durable
    machinery: execution is claimed and persisted before it starts, the
    interaction worker runs it, and this response tails the persisted events.
    Consequently it emits AG-UI events rather than the former `agent.*` frames.
    """
    await require_resource_run_async(ctx, RESOURCE_AGENT, agent_id)
    if not settings.response_interaction_worker_enabled:
        # Without the worker nothing would execute the claim and this stream
        # would heartbeat indefinitely. Say so instead of hanging.
        raise ConflictError(
            "Deprecated agent streaming requires the durable interaction worker; "
            "use POST /v1/responses instead"
        )

    interaction_id = generate_response_interaction_id()
    agent_inputs = data.model_dump(exclude_none=True, exclude_unset=True)
    response_service = projection_coordinator.response_service
    response_service.claim_interaction(
        interaction_id=interaction_id,
        parent_interaction_id=None,
        thread_id="",
        request_hash=interaction_id,
        execution_json={
            "mode": "agent",
            "agent_id": agent_id,
            "agent_inputs": agent_inputs,
            "assistant_message_id": generate_thread_message_id(),
        },
        request_context_json=asdict(ctx),
    )

    return StreamingResponse(
        stream_claimed_interaction(response_service, interaction_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Deprecation": "true",
            "Link": '</api/v1/responses>; rel="successor-version"',
        },
    )


@router.post(
    "/{agent_id}/runs/{run_id}/cancel",
    response_model=AgentCancelResponse,
)
async def cancel_agent_execution(
    agent_id: str,
    run_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    """Explicitly cancel an active Agent execution."""

    handlers = AgentAppHandlers(service)
    return await handlers.cancel_agent_execution(ctx, agent_id, run_id)
