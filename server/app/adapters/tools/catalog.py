"""The workspace tool catalog: registry tools, built-ins and MCP server tools.

A ref is invocable when the tool router can resolve it: a tool registered in
the runtime registry for the workspace (plugin tools, and built-ins once
registered), one of the listed built-ins, or a tool an enabled MCP server of
the workspace advertised when its plugin was installed.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.tools.catalog import CatalogTool, ToolCatalogPort
from app.kernel.registry.deps import get_registry
from app.kernel.runtime.tools.resolver import BuiltinToolRegistrationPort
from app.modules.plugin.domain.models import PluginInstalledArtifact

LISTED_BUILTIN_TOOL_REFS: tuple[str, ...] = (
    "tool:function:knowledge_query",
    "tool:function:random_int",
    "tool:function:time_now",
    "tool:http:request",
)
"""Built-ins every workspace lists; others resolve when referenced."""

_OPEN_SCHEMA: dict[str, Any] = {"type": "object"}


def _source_kind(ref: str, payload: dict[str, Any]) -> str:
    if payload.get("plugin"):
        return "plugin"
    if payload.get("mcp"):
        return "mcp"
    if payload.get("builtin") or ref in LISTED_BUILTIN_TOOL_REFS or ref.startswith("builtin."):
        return "builtin"
    return "native"


def _registry_tool(ref: str, payload: dict[str, Any]) -> CatalogTool:
    spec = payload.get("tool_spec") or {}
    return CatalogTool(
        ref=ref,
        name=str(spec.get("name") or ref.split(":")[-1]),
        description=str(spec.get("description") or spec.get("name") or ref),
        input_schema=dict(spec.get("input_schema") or _OPEN_SCHEMA),
        source_kind=_source_kind(ref, payload),
        policy=dict(spec.get("policy") or {}),
    )


class WorkspaceToolCatalog(ToolCatalogPort):
    """Tools of the caller's workspace, read from the registry and the database."""

    def __init__(self, db: AsyncSession, registration: BuiltinToolRegistrationPort | None = None) -> None:
        self.db = db
        self.registration = registration

    def _register_builtin(self, ref: str, ctx: RequestContext) -> bool:
        if self.registration is None:
            return False
        return bool(self.registration.register_builtin(ref, ctx))

    def _registry_tools(self, ctx: RequestContext) -> dict[str, CatalogTool]:
        registry = get_registry()
        names = {
            key.name
            for key, _ in registry.list(kind="tool", tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id)
        }
        tools: dict[str, CatalogTool] = {}
        for name in names:
            found = registry.get_latest(
                kind="tool", tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, name=name
            )
            if found is not None:
                _, payload = found
                tools[name] = _registry_tool(name, payload if isinstance(payload, dict) else {})
        return tools

    async def _mcp_tools(self, ctx: RequestContext) -> dict[str, CatalogTool]:
        rows = (
            await self.db.exec(
                select(PluginInstalledArtifact).where(
                    and_(
                        PluginInstalledArtifact.tenant_id == ctx.tenant_id,
                        PluginInstalledArtifact.workspace_id == ctx.workspace_id,
                        PluginInstalledArtifact.artifact_kind == "mcp_server",
                        PluginInstalledArtifact.enabled.is_(True),
                        PluginInstalledArtifact.state == "enabled",
                    )
                )
            )
        ).scalars().all()
        tools: dict[str, CatalogTool] = {}
        for artifact in rows:
            server = (artifact.metadata_json or {}).get("mcp_server") or {}
            server_name = str(server.get("name") or artifact.artifact_ref.split(":", 1)[-1])
            for capability in (server.get("capabilities_json") or {}).get("tools") or []:
                if not isinstance(capability, dict):
                    continue
                tool_name = str(capability.get("name") or capability.get("id") or "").strip()
                if not tool_name:
                    continue
                ref = f"mcp_tool:{server_name}:{tool_name}"
                schema = (
                    capability.get("inputSchema")
                    or capability.get("input_schema")
                    or capability.get("parameters")
                    or _OPEN_SCHEMA
                )
                tools[ref] = CatalogTool(
                    ref=ref,
                    name=tool_name,
                    description=str(capability.get("description") or f"MCP tool {tool_name} of {server_name}"),
                    input_schema=dict(schema) if isinstance(schema, dict) else dict(_OPEN_SCHEMA),
                    source_kind="mcp",
                    policy=dict(capability.get("policy") or {}),
                )
        return tools

    async def list_tools(self, ctx: RequestContext) -> list[CatalogTool]:
        for ref in LISTED_BUILTIN_TOOL_REFS:
            self._register_builtin(ref, ctx)
        tools = {**self._registry_tools(ctx), **await self._mcp_tools(ctx)}
        return [tools[ref] for ref in sorted(tools)]

    async def get_tool(self, ctx: RequestContext, tool_ref: str) -> CatalogTool | None:
        if tool_ref.startswith("mcp_tool:"):
            return (await self._mcp_tools(ctx)).get(tool_ref)
        registry = get_registry()
        found = registry.get_latest(
            kind="tool", tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, name=tool_ref
        )
        if found is None and self._register_builtin(tool_ref, ctx):
            found = registry.get_latest(
                kind="tool", tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, name=tool_ref
            )
        if found is None:
            return None
        _, payload = found
        return _registry_tool(tool_ref, payload if isinstance(payload, dict) else {})
