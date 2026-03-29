"""MCP API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, status

from app.api.v1.mcp.dependencies import get_mcp_service
from app.api.v1.mcp.handlers import MCPHandlers
from app.api.v1.permissions import require_workspace_read_ctx, require_workspace_write_ctx
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.modules.integrations.mcp.application.schemas import (
    MCPBindingTargetResponse,
    MCPCatalogResponse,
    MCPServerCreate,
    MCPServerResponse,
    MCPServerUpdate,
)
from app.modules.integrations.mcp.application.service import MCPService


router = APIRouter()


@router.post("/servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: MCPServerCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: MCPService = Depends(get_mcp_service),
):
    return await MCPHandlers(service).create_server(ctx, payload)


@router.get("/servers", response_model=PaginatedResponse[MCPServerResponse])
async def list_servers(
    enabled_only: bool = False,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: MCPService = Depends(get_mcp_service),
):
    return await MCPHandlers(service).list_servers(
        ctx,
        enabled_only=enabled_only,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/servers/{server_id}", response_model=MCPServerResponse)
async def get_server(
    server_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: MCPService = Depends(get_mcp_service),
):
    return await MCPHandlers(service).get_server(ctx, server_id)


@router.put("/servers/{server_id}", response_model=MCPServerResponse)
async def update_server(
    server_id: str,
    payload: MCPServerUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: MCPService = Depends(get_mcp_service),
):
    return await MCPHandlers(service).update_server(ctx, server_id, payload)


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: MCPService = Depends(get_mcp_service),
):
    await MCPHandlers(service).delete_server(ctx, server_id)


@router.get("/servers/{server_id}/catalog", response_model=MCPCatalogResponse)
async def get_server_catalog(
    server_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: MCPService = Depends(get_mcp_service),
):
    return await MCPHandlers(service).get_server_catalog(ctx, server_id)


@router.get("/servers/{server_id}/binding-targets", response_model=list[MCPBindingTargetResponse])
async def list_server_binding_targets(
    server_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: MCPService = Depends(get_mcp_service),
):
    return await MCPHandlers(service).list_binding_targets(ctx, server_id)


@router.get("/catalog", response_model=MCPCatalogResponse)
async def get_catalog(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: MCPService = Depends(get_mcp_service),
):
    return await MCPHandlers(service).get_catalog(ctx)


@router.get("/binding-targets", response_model=list[MCPBindingTargetResponse])
async def list_binding_targets(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: MCPService = Depends(get_mcp_service),
):
    return await MCPHandlers(service).list_binding_targets(ctx)
