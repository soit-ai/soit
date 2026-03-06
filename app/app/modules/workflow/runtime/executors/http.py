""" http

HTTP node executor.
"""

from typing import Dict, Any
from app.modules.workflow.runtime.executors.base import NodeExecutor, ExecutionContext
from app.kernel.commons.errors import ValidationError


class HttpNodeExecutor(NodeExecutor):
    """Executor for HTTP request nodes."""

    async def execute(
        self,
        node: Dict[str, Any],
        context: ExecutionContext,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute HTTP node."""
        if not context.tool_port:
            raise ValidationError("Tool port not available")

        url = inputs.get("url")
        if not url:
            raise ValidationError("HTTP node requires 'url' input")

        method = inputs.get("method", "GET")
        headers = inputs.get("headers", {})
        query = inputs.get("query", {})
        body = inputs.get("body", {})

        registry_only = bool(context.workflow_policy.get("registry_only_tools"))
        response = await context.tool_port.invoke(
            tool_ref="tool:http:request",
            parameters={
                "url": url,
                "method": method,
                "headers": headers,
                "query": query,
                "body": body,
            },
            run_id=context.run_id,
            ctx=context.ctx,
            strict_registry=registry_only,
        )

        if not response.success:
            raise ValidationError(f"HTTP request failed: {response.error}")

        return {
            "result": response.result,
            "metadata": response.metadata,
        }
