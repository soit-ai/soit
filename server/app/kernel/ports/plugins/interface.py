"""interface

Plugin runtime port.

A plugin may expose one or more tools (declared in its spec/manifest). The runtime invokes those tools
through this port. Adapters decide how to execute plugins (subprocess, container, HTTP, wasm, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

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
    ) -> List[Dict[str, Any]]:
        """Return tool specs (tool_spec-compatible dicts)."""

    @abstractmethod
    async def invoke(
        self,
        *,
        plugin_name: str,
        version: str,
        tool_name: str,
        input_json: Dict[str, Any],
        ctx: RequestContext,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Invoke a plugin tool and return output JSON."""
