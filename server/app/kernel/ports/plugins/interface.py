"""interface

Plugin runtime port.

A plugin may expose one or more tools (declared in its spec/manifest). The runtime invokes those tools
through this port. Adapters decide how to execute plugins (subprocess, container, HTTP, wasm, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.kernel.contracts.context import RequestContext


class PluginRuntimePort(ABC):
    """Plugin runtime port interface."""

    @abstractmethod
    def list_tools(
        self,
        *,
        plugin_name: str,
        version: str,
        ctx: RequestContext,
    ) -> list[dict[str, Any]]:
        """Return tool specs (tool_spec-compatible dicts)."""

    @abstractmethod
    async def invoke(
        self,
        *,
        plugin_name: str,
        version: str,
        tool_name: str,
        input_json: dict[str, Any],
        ctx: RequestContext,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        """Invoke a plugin tool and return output JSON."""

    def resolve_skill_context(
        self,
        *,
        skill_refs: list[str],
        ctx: RequestContext,
    ) -> str | None:
        """Render installed plugin skill refs into runtime context."""
        raise NotImplementedError("Plugin runtime does not support skill context resolution")
