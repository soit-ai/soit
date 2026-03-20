"""MCP application service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import workspace_guard
from app.modules.integrations.mcp.application.schemas import MCPServerCreate, MCPServerUpdate
from app.modules.integrations.mcp.domain.models import MCPServer
from app.modules.integrations.mcp.infra.repository import MCPServerRepository


class MCPService:
    """Manage MCP server registrations and catalogs."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx
        self.repo = MCPServerRepository(db, ctx)

    def _get_server(self, server_id: str) -> MCPServer:
        server = self.repo.get_by_id(server_id)
        if not server:
            raise NotFoundError(f"MCP server not found: {server_id}")
        return server

    @workspace_guard("write")
    async def create_server(self, data: MCPServerCreate) -> MCPServer:
        existing = self.repo.get_by_name(data.name)
        if existing:
            raise ValidationError(f"MCP server with name '{data.name}' already exists")
        return self.repo.create(
            MCPServer(
                name=data.name,
                description=data.description,
                transport=data.transport,
                endpoint=data.endpoint,
                enabled=data.enabled,
                auth_config_json=data.auth_config_json,
                capabilities_json=data.capabilities_json,
                metadata_json=data.metadata_json,
            )
        )

    @workspace_guard("read")
    async def list_servers(self, limit: int = 20, offset: int = 0, enabled_only: bool = False) -> list[MCPServer]:
        return self.repo.list(limit=limit, offset=offset, enabled_only=enabled_only)

    @workspace_guard("read")
    async def get_server(self, server_id: str) -> MCPServer:
        return self._get_server(server_id)

    @workspace_guard("write")
    async def update_server(self, server_id: str, data: MCPServerUpdate) -> MCPServer:
        server = self._get_server(server_id)
        if data.name and data.name != server.name:
            existing = self.repo.get_by_name(data.name)
            if existing and existing.id != server.id:
                raise ValidationError(f"MCP server with name '{data.name}' already exists")
            server.name = data.name
        if data.description is not None:
            server.description = data.description
        if data.transport is not None:
            server.transport = data.transport
        if data.endpoint is not None:
            server.endpoint = data.endpoint
        if data.enabled is not None:
            server.enabled = data.enabled
        if data.status is not None:
            server.status = data.status
        if data.auth_config_json is not None:
            server.auth_config_json = data.auth_config_json
        if data.capabilities_json is not None:
            server.capabilities_json = data.capabilities_json
        if data.metadata_json is not None:
            server.metadata_json = data.metadata_json
        return self.repo.update(server)

    @workspace_guard("write")
    async def delete_server(self, server_id: str) -> None:
        server = self._get_server(server_id)
        server.status = "archived"
        server.enabled = False
        server.deleted_at = utc_now()
        self.repo.update(server)

    @workspace_guard("read")
    async def get_server_catalog(self, server_id: str) -> dict[str, list[dict]]:
        server = self._get_server(server_id)
        capabilities = server.capabilities_json or {}
        return {
            "tools": list(capabilities.get("tools") or []),
            "resources": list(capabilities.get("resources") or []),
            "templates": list(capabilities.get("templates") or []),
        }

    @workspace_guard("read")
    async def get_catalog(self) -> dict[str, list[dict]]:
        servers = self.repo.list(limit=500, offset=0, enabled_only=True)
        tools: list[dict] = []
        resources: list[dict] = []
        templates: list[dict] = []
        for server in servers:
            capabilities = server.capabilities_json or {}
            for key, target in (("tools", tools), ("resources", resources), ("templates", templates)):
                for item in list(capabilities.get(key) or []):
                    if isinstance(item, dict):
                        target.append({"server_id": server.id, "server_name": server.name, **item})
        return {"tools": tools, "resources": resources, "templates": templates}
