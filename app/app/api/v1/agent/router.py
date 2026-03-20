""" router

Agent API routes (FastAPI).
"""

from typing import Optional
from fastapi import APIRouter, Depends, Body, status

from app.kernel.contracts.context import RequestContext
from app.api.v1.permissions import require_workspace_write_ctx, require_workspace_read_ctx
from app.modules.agent.application.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentVersionCreate,
    AgentVersionResponse,
    AgentBindingResponse,
    AgentPublishRequest,
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


@router.post("/{agent_id}/execute", response_model=AgentRunResponse)
async def execute_agent(
    agent_id: str,
    data: AgentRunRequest = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AgentApplicationService = Depends(get_agent_application_service),
):
    handlers = AgentAppHandlers(service)
    return await handlers.execute_agent(ctx, agent_id, data)
