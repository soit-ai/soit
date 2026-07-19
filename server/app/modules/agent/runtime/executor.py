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
        tool_call_id: str,
        idempotency_key: str,
        run_step_id: str | None = None,
        resume_approval: bool = False,
        lease_owner: str | None = None,
    ) -> ToolResponse:
        """Execute tool call."""
        return await self.tool_port.invoke(
            tool_ref=tool_ref,
            parameters=parameters,
            run_id=run_id,
            tool_call_id=tool_call_id,
            idempotency_key=idempotency_key,
            run_step_id=run_step_id,
            resume_approval=resume_approval,
            lease_owner=lease_owner,
            ctx=ctx,
            strict_registry=True,
        )
