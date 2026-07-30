""" sandbox

Dry-run isolation for tool invocation.

Pre-release regression runs real agents against real tool bindings. Without
isolation, rehearsing the release creates tickets, sends notifications and
charges third parties for work nobody asked for. This wrapper lets the run
exercise the full decision path while stopping the side effect at the boundary.
"""

from __future__ import annotations

from typing import Any

from app.kernel.ports.tools.interface import ToolPort, ToolResponse

DRY_RUN_METADATA_KEY = "sandbox_dry_run"


class SandboxToolPort(ToolPort):
    """Answer tool calls without performing them.

    Read-only tools can be allowed through by listing them, so a rehearsal can
    still retrieve the data it reasons over.
    """

    def __init__(
        self,
        inner: ToolPort,
        *,
        passthrough_tool_refs: frozenset[str] | None = None,
    ) -> None:
        self.inner = inner
        self.passthrough_tool_refs = passthrough_tool_refs or frozenset()

    async def invoke(
        self,
        tool_ref: str,
        parameters: dict[str, Any],
        **kwargs: Any,
    ) -> ToolResponse:
        """Return a synthetic result unless the tool is explicitly passed through."""
        if tool_ref in self.passthrough_tool_refs:
            return await self.inner.invoke(tool_ref, parameters, **kwargs)

        return ToolResponse(
            result={
                "sandbox": True,
                "tool_ref": tool_ref,
                "message": "Tool call was not executed: this run is a rehearsal",
            },
            success=True,
            metadata={
                DRY_RUN_METADATA_KEY: True,
                "tool_ref": tool_ref,
                # Parameter names are recorded so evidence shows what would
                # have been sent; values are not, because they may carry the
                # very data the rehearsal must not leak outward.
                "parameter_names": sorted(parameters or {}),
            },
        )
