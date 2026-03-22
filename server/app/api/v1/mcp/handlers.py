"""Handlers for MCP APIs."""

from __future__ import annotations

from typing import Optional

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.modules.integrations.mcp.application.schemas import (
    MCPCatalogResponse,
    MCPServerCreate,
    MCPServerResponse,
    MCPServerUpdate,
)
from app.modules.integrations.mcp.application.service import MCPService


class MCPHandlers:
    def __init__(self, service: MCPService) -> None:
        self.service = service

    async def create_server(self, ctx: RequestContext, payload: MCPServerCreate) -> MCPServerResponse:
        return MCPServerResponse.model_validate(await self.service.create_server(payload))

    async def list_servers(
        self,
        ctx: RequestContext,
        *,
        enabled_only: bool,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[MCPServerResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        servers = await self.service.list_servers(limit=limit, offset=offset, enabled_only=enabled_only)
        items = [MCPServerResponse.model_validate(item) for item in servers]
        has_next = len(servers) == limit
        next_offset = offset + len(servers) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def get_server(self, ctx: RequestContext, server_id: str) -> MCPServerResponse:
        return MCPServerResponse.model_validate(await self.service.get_server(server_id))

    async def update_server(self, ctx: RequestContext, server_id: str, payload: MCPServerUpdate) -> MCPServerResponse:
        return MCPServerResponse.model_validate(await self.service.update_server(server_id, payload))

    async def delete_server(self, ctx: RequestContext, server_id: str) -> None:
        await self.service.delete_server(server_id)

    async def get_server_catalog(self, ctx: RequestContext, server_id: str) -> MCPCatalogResponse:
        return MCPCatalogResponse.model_validate(await self.service.get_server_catalog(server_id))

    async def get_catalog(self, ctx: RequestContext) -> MCPCatalogResponse:
        return MCPCatalogResponse.model_validate(await self.service.get_catalog())
