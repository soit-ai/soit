""" tool

Tool node executor.
"""

from typing import Dict, Any
from app.modules.workflow.runtime.executors.base import NodeExecutor, ExecutionContext
from app.kernel.commons.errors import ValidationError


class ToolNodeExecutor(NodeExecutor):
    """Executor for tool nodes."""
    
    async def execute(
        self,
        node: Dict[str, Any],
        context: ExecutionContext,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute tool node.
        
        Args:
            node: Node definition.
            context: Execution context.
            inputs: Resolved inputs.
            
        Returns:
            Output dictionary with tool result.
        """
        if not context.tool_port:
            raise ValidationError("Tool port not available")
        
        # Extract tool reference
        registry_only = bool(context.workflow_policy.get("registry_only_tools"))
        tool_ref = inputs.get("tool_ref") or inputs.get("tool")
        if not tool_ref:
            raise ValidationError("Tool node requires 'tool_ref' or 'tool' input")
        if registry_only and not inputs.get("tool_ref"):
            raise ValidationError("Tool node requires 'tool_ref' when registry_only_tools is enabled")
        
        # Extract parameters (everything except tool_ref)
        parameters = {k: v for k, v in inputs.items() if k not in ("tool_ref", "tool")}
        
        # Call tool gateway
        response = await context.tool_port.invoke(
            tool_ref=tool_ref,
            parameters=parameters,
            run_id=context.run_id,
            ctx=context.ctx,
            strict_registry=registry_only,
        )
        
        if not response.success:
            raise ValidationError(f"Tool execution failed: {response.error}")
        
        return {
            "result": response.result,
            "metadata": response.metadata,
        }
