""" http

HTTP node executor.
"""

from typing import Any

from app.kernel.commons.errors import ValidationError
from app.modules.workflow.runtime.executors.base import ExecutionContext, NodeExecutor


class HttpNodeExecutor(NodeExecutor):
    """Executor for HTTP request nodes."""

    async def execute(
        self,
        node: dict[str, Any],
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
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
        # Attempt-stable identity: a retry or crash-resume must replay a
        # completed request from the ledger instead of reissuing it.
        tool_call_id = (
            f"workflow:{context.workflow_run_id or context.run_id}:"
            f"{node.get('id') or 'http'}:0"
        )
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
            tool_call_id=tool_call_id,
            idempotency_key=f"tool:{context.run_id}:{tool_call_id}",
            retry_failed=True,
        )

        if not response.success:
            raise ValidationError(f"HTTP request failed: {response.error}")

        return {
            "result": response.result,
            "metadata": response.metadata,
        }
