"""Resolve governed tool references without depending on concrete adapters."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ToolDefinition
from app.kernel.registry.deps import get_registry

logger = logging.getLogger(__name__)


@runtime_checkable
class BuiltinToolRegistrationPort(Protocol):
    """Capability exposed by tool routers that can register builtin specs."""

    def register_builtin(self, tool_ref: str, ctx: RequestContext) -> bool: ...


class ToolResolver:
    """Resolve tool references through registry and injected registration ports."""

    def __init__(
        self,
        tool_port: BuiltinToolRegistrationPort,
        mcp_tool_resolver: Callable | None = None,
    ) -> None:
        self.tool_port = tool_port
        self.mcp_tool_resolver = mcp_tool_resolver

    async def resolve(
        self,
        tool_refs: list[str] | None,
        ctx: RequestContext,
    ) -> list[ToolDefinition]:
        if not tool_refs:
            return []

        definitions: list[ToolDefinition] = []
        registry = get_registry()
        for ref in tool_refs:
            found = registry.get_latest(
                kind="tool",
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                name=ref,
            )
            if not found and self.tool_port.register_builtin(ref, ctx):
                found = registry.get_latest(
                    kind="tool",
                    tenant_id=ctx.tenant_id,
                    workspace_id=ctx.workspace_id,
                    name=ref,
                )

            if not found and (ref.startswith("mcp_tool:") or ref.startswith("tool:mcp:")):
                if self.mcp_tool_resolver:
                    try:
                        resolved = await self.mcp_tool_resolver(ref, ctx)
                        if resolved:
                            definitions.append(resolved)
                            continue
                    except Exception:
                        logger.warning("MCP tool resolution failed for %s", ref, exc_info=True)
                elif ref.startswith("mcp_tool:"):
                    parts = ref.split(":", 2)
                    tool_name = parts[2] if len(parts) == 3 else ref
                    definitions.append(
                        ToolDefinition(
                            name=ref,
                            description=f"MCP tool: {tool_name}",
                            parameters={"type": "object"},
                        )
                    )
                    continue

            if not found:
                logger.warning("Tool ref not found, skipping: %s", ref)
                continue

            _, payload = found
            spec = (payload or {}).get("tool_spec") or {}
            definitions.append(
                ToolDefinition(
                    name=ref,
                    description=spec.get("description") or spec.get("name") or ref,
                    parameters=spec.get("input_schema") or {"type": "object"},
                    policy=spec.get("policy") or {},
                )
            )
        return definitions
