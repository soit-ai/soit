"""Port for the tools a workspace can invoke by reference.

Agents reach tools through their bindings. The tool invocation API and the MCP
endpoint reach them by reference, so they need the list itself: which refs
resolve in this workspace, what each one takes, and the policy it runs under.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.kernel.contracts.context import RequestContext


@dataclass(frozen=True)
class CatalogTool:
    """One tool a workspace can invoke, as a caller sees it."""

    ref: str
    name: str
    description: str
    input_schema: dict[str, Any]
    source_kind: str
    """``builtin``, ``plugin``, ``mcp`` or ``native``."""
    policy: dict[str, Any] = field(default_factory=dict)
    """The ToolSpec policy: approval, egress allowlist, secrets, timeouts."""


class ToolCatalogPort(Protocol):
    """List and resolve the tools of one workspace."""

    async def list_tools(self, ctx: RequestContext) -> list[CatalogTool]:
        """Every tool the workspace can invoke, sorted by ref."""

    async def get_tool(self, ctx: RequestContext, tool_ref: str) -> CatalogTool | None:
        """The tool behind ``tool_ref``, or None when the workspace has none."""
