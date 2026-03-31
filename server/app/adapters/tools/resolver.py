"""resolver

Resolve tool_refs into ToolDefinition list for LLM function calling.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ToolDefinition
from app.kernel.registry.deps import get_registry
from app.adapters.tools.router import RegistryToolRouterPort

logger = logging.getLogger(__name__)


class ToolResolver:
    """Resolve tool_refs into ToolDefinition list for LLM function calling.

    Resolution chain:
    1. Check kernel registry (in-memory cache)
    2. Try builtin registration (tool:function:*, tool:http:*)
    3. Try MCP resolution via mcp_tool_resolver callable (lazy DB fallback)
    4. Skip unknown refs with a warning
    """

    def __init__(
        self,
        tool_port: RegistryToolRouterPort,
        mcp_tool_resolver: Optional[Callable] = None,
    ):
        self.tool_port = tool_port
        self.mcp_tool_resolver = mcp_tool_resolver

    async def resolve(
        self,
        tool_refs: Optional[List[str]],
        ctx: RequestContext,
    ) -> List[ToolDefinition]:
        """Resolve tool refs into ToolDefinition list."""
        if not tool_refs:
            return []

        definitions: List[ToolDefinition] = []
        reg = get_registry()

        for ref in tool_refs:
            # 1. Check registry cache
            found = reg.get_latest(
                kind="tool",
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                name=ref,
            )

            # 2. Try builtin registration
            if not found:
                if self.tool_port._register_builtin(ref, ctx):
                    found = reg.get_latest(
                        kind="tool",
                        tenant_id=ctx.tenant_id,
                        workspace_id=ctx.workspace_id,
                        name=ref,
                    )

            # 3. Try MCP resolution for mcp_tool:* or tool:mcp:* refs
            if not found and (ref.startswith("mcp_tool:") or ref.startswith("tool:mcp:")):
                if self.mcp_tool_resolver:
                    try:
                        mcp_def = await self.mcp_tool_resolver(ref, ctx)
                        if mcp_def:
                            definitions.append(mcp_def)
                            continue
                    except Exception:
                        logger.warning("MCP tool resolution failed for %s", ref, exc_info=True)
                elif ref.startswith("mcp_tool:"):
                    # Fallback: create a basic ToolDefinition from the ref name
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

            # 4. Skip if still not found
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
                )
            )

        return definitions
