""" executor

Agent executor.
"""

from typing import Any

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.tools.interface import ToolPort, ToolResponse


class AgentExecutor:
    """Execute tool actions for agent."""

    def __init__(self, tool_port: ToolPort):
        self.tool_port = tool_port

    async def execute_tool(
        self,
        tool_ref: str,
        parameters: dict[str, Any],
        ctx: RequestContext,
        run_id: str,
    ) -> ToolResponse:
        """Execute tool call."""
        return await self.tool_port.invoke(
            tool_ref=tool_ref,
            parameters=parameters,
            run_id=run_id,
            ctx=ctx,
            strict_registry=True,
        )
