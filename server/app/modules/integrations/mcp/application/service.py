"""MCP application service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import workspace_guard
from app.modules.integrations.mcp.application.schemas import MCPBindingTargetResponse, MCPServerCreate, MCPServerUpdate
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

    @staticmethod
    def is_enabled_status(status: str) -> bool:
        return (status or "").strip().lower() == "active"

    def _normalize_server_status(
        self,
        *,
        status: str | None = None,
        enabled: bool | None = None,
        current: str = "active",
    ) -> str:
        if status is not None:
            normalized = status.strip().lower()
        elif enabled is not None:
            normalized = "active" if enabled else "disabled"
        else:
            normalized = current
        if normalized not in {"active", "disabled", "archived"}:
            raise ValidationError(f"Invalid MCP server status: {normalized}")
        return normalized

    def build_server_ref(self, server: MCPServer) -> str:
        selector = server.name or server.id
        return f"mcp_server:{selector}"

    def _server_ref_aliases(self, server: MCPServer) -> set[str]:
        aliases = {self.build_server_ref(server), f"mcp_server:{server.id}"}
        if server.name:
            aliases.add(f"mcp_server:{server.name}")
        return aliases

    def _capability_key(self, item: dict, *, fallback_fields: tuple[str, ...]) -> str | None:
        for field in fallback_fields:
            value = item.get(field)
            if value is not None:
                normalized = str(value).strip()
                if normalized:
                    return normalized
        return None

    def _binding_ref_aliases(self, prefix: str, server: MCPServer, capability_key: str) -> set[str]:
        aliases = {
            f"{prefix}:{server.id}:{capability_key}",
            f"{prefix}:{server.name}:{capability_key}",
        }
        return {alias for alias in aliases if alias}

    def _binding_target(
        self,
        *,
        binding_type: str,
        server: MCPServer,
        capability_key: str | None = None,
        capability_name: str | None = None,
        description: str | None = None,
        uri: str | None = None,
        metadata_json: dict | None = None,
    ) -> dict:
        server_ref = self.build_server_ref(server)
        binding_ref = server_ref
        aliases = list(self._server_ref_aliases(server))
        if binding_type == "mcp_tool" and capability_key:
            binding_ref = f"mcp_tool:{server.name}:{capability_key}"
            aliases = list(self._binding_ref_aliases("mcp_tool", server, capability_key))
        elif binding_type == "mcp_resource" and capability_key:
            binding_ref = f"mcp_resource:{server.name}:{capability_key}"
            aliases = list(self._binding_ref_aliases("mcp_resource", server, capability_key))
        return {
            "binding_type": binding_type,
            "binding_ref": binding_ref,
            "server_ref": server_ref,
            "server_id": server.id,
            "server_name": server.name,
            "capability_key": capability_key,
            "capability_name": capability_name,
            "description": description,
            "uri": uri,
            "metadata_json": metadata_json or {},
            "_aliases": aliases,
        }

    def _normalize_catalog_entry(self, server: MCPServer, category: str, item: dict) -> dict:
        normalized = {"server_id": server.id, "server_name": server.name, "server_ref": self.build_server_ref(server), **item}
        if category == "tools":
            capability_key = self._capability_key(item, fallback_fields=("name", "id"))
            if capability_key:
                normalized["binding_type"] = "mcp_tool"
                normalized["binding_ref"] = f"mcp_tool:{server.name}:{capability_key}"
        elif category == "resources":
            capability_key = self._capability_key(item, fallback_fields=("name", "id"))
            if capability_key:
                normalized["binding_type"] = "mcp_resource"
                normalized["binding_ref"] = f"mcp_resource:{server.name}:{capability_key}"
        return normalized

    def _server_binding_targets(self, server: MCPServer) -> list[dict]:
        capabilities = server.capabilities_json or {}
        targets = [
            self._binding_target(
                binding_type="mcp_server",
                server=server,
                description=server.description,
                metadata_json={"transport": server.transport, "endpoint": server.endpoint},
            )
        ]
        for item in list(capabilities.get("tools") or []):
            if not isinstance(item, dict):
                continue
            capability_key = self._capability_key(item, fallback_fields=("name", "id"))
            if not capability_key:
                continue
            targets.append(
                self._binding_target(
                    binding_type="mcp_tool",
                    server=server,
                    capability_key=capability_key,
                    capability_name=str(item.get("name") or capability_key),
                    description=item.get("description"),
                    metadata_json=item,
                )
            )
        for item in list(capabilities.get("resources") or []):
            if not isinstance(item, dict):
                continue
            capability_key = self._capability_key(item, fallback_fields=("name", "id"))
            if not capability_key:
                continue
            targets.append(
                self._binding_target(
                    binding_type="mcp_resource",
                    server=server,
                    capability_key=capability_key,
                    capability_name=str(item.get("name") or capability_key),
                    description=item.get("description"),
                    uri=item.get("uri"),
                    metadata_json=item,
                )
            )
        return targets

    def _binding_target_index(self, servers: list[MCPServer]) -> dict[str, dict]:
        index: dict[str, dict] = {}
        for server in servers:
            for target in self._server_binding_targets(server):
                aliases = target.pop("_aliases", [])
                resolved = dict(target)
                for alias in aliases:
                    index[alias] = resolved
        return index

    @workspace_guard("write")
    async def create_server(self, data: MCPServerCreate) -> MCPServer:
        existing = self.repo.get_by_name(data.name)
        if existing:
            raise ValidationError(f"MCP server with name '{data.name}' already exists")
        normalized_status = self._normalize_server_status(status=data.status, enabled=data.enabled, current="active")
        return self.repo.create(
            MCPServer(
                name=data.name,
                description=data.description,
                transport=data.transport,
                endpoint=data.endpoint,
                enabled=self.is_enabled_status(normalized_status),
                status=normalized_status,
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
        server.status = self._normalize_server_status(
            status=data.status,
            enabled=data.enabled,
            current=server.status,
        )
        server.enabled = self.is_enabled_status(server.status)
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
            "tools": [self._normalize_catalog_entry(server, "tools", item) for item in list(capabilities.get("tools") or []) if isinstance(item, dict)],
            "resources": [self._normalize_catalog_entry(server, "resources", item) for item in list(capabilities.get("resources") or []) if isinstance(item, dict)],
            "templates": [self._normalize_catalog_entry(server, "templates", item) for item in list(capabilities.get("templates") or []) if isinstance(item, dict)],
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
                        target.append(self._normalize_catalog_entry(server, key, item))
        return {"tools": tools, "resources": resources, "templates": templates}

    @workspace_guard("read")
    async def list_binding_targets(self, *, server_id: str | None = None) -> list[dict]:
        servers = [self._get_server(server_id)] if server_id else self.repo.list(limit=500, offset=0, enabled_only=True)
        targets: list[dict] = []
        for server in servers:
            for target in self._server_binding_targets(server):
                target.pop("_aliases", None)
                targets.append(target)
        return targets

    @workspace_guard("read")
    async def resolve_binding_refs(
        self,
        *,
        mcp_server_refs: list[str] | None = None,
        mcp_tool_refs: list[str] | None = None,
        mcp_resource_refs: list[str] | None = None,
    ) -> dict[str, dict]:
        servers = self.repo.list(limit=500, offset=0, enabled_only=True)
        index = self._binding_target_index(servers)
        resolved: dict[str, dict] = {}
        for ref in [*(mcp_server_refs or []), *(mcp_tool_refs or []), *(mcp_resource_refs or [])]:
            if not ref:
                continue
            target = index.get(ref)
            if not target:
                raise ValidationError(f"MCP binding target not found or disabled: {ref}")
            resolved[ref] = dict(target)
        return resolved
