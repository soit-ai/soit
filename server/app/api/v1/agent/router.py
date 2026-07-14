""" router

Agent API routes (FastAPI).
"""

import asyncio
import json
from typing import Optional
from fastapi import APIRouter, Depends, Body, status
from fastapi.responses import StreamingResponse

from app.kernel.contracts.context import RequestContext
from app.api.v1.permissions import require_workspace_write_ctx, require_workspace_read_ctx
from app.modules.agent.application.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentCapabilityResponse,
    AgentVersionCreate,
    AgentVersionResponse,
    AgentReleaseResponse,
    AgentBindingResponse,
    AgentWorkbenchItemsResponse,
    AgentWorkbenchResponse,
    AgentPublishRequest,
    AgentRollbackRequest,
)
from app.modules.agent.application.service import AgentService
from app.modules.agent.application.application_service import AgentApplicationService
from app.api.v1.agent.dependencies import get_agent_service, get_agent_application_service
from app.api.v1.agent.handlers import AgentHandlers, AgentAppHandlers
from app.infra.db.pagination import PaginatedResponse


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
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.list_agents(ctx, page_token=page_token, page_size=page_size)


@router.get("/workbench", response_model=AgentWorkbenchResponse)
async def get_agent_workbench(
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.get_workbench(ctx, page_token=page_token, page_size=page_size)


@router.get("/workbench/items", response_model=AgentWorkbenchItemsResponse)
async def list_agent_workbench_items(
    tab: Optional[str] = None,
    keyword: Optional[str] = None,
    page_token: Optional[str] = None,
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
    kind: Optional[str] = None,
    source_kind: Optional[str] = None,
    page_token: Optional[str] = None,
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
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.list_versions(ctx, agent_id, page_token=page_token, page_size=page_size)


@router.get("/{agent_id}/releases", response_model=PaginatedResponse[AgentReleaseResponse])
async def list_releases(
    agent_id: str,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.list_releases(ctx, agent_id, page_token=page_token, page_size=page_size)


@router.get("/{agent_id}/bindings", response_model=list[AgentBindingResponse])
async def list_bindings(
    agent_id: str,
    version_id: Optional[str] = None,
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


@router.post("/{agent_id}/stream")
async def stream_agent(
    agent_id: str,
    data: AgentRunRequest = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    """Stream agent execution events via SSE."""
    from app.modules.agent.runtime.emitter import QueueEmitter

    emitter = QueueEmitter()

    async def run_agent():
        try:
            result = await service.execute_agent_streaming(agent_id, data.model_dump(exclude_none=True, exclude_unset=True), emitter)
            await emitter.queue.put(("agent.result", result))
        except Exception as exc:
            await emitter.queue.put(("agent.error", {"error": str(exc)}))
        finally:
            await emitter.done()

    async def generate():
        task = asyncio.create_task(run_agent())
        try:
            while True:
                item = await emitter.queue.get()
                if item is None:
                    break
                event_name, event_data = item
                yield f"event: {event_name}\ndata: {json.dumps(event_data)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
