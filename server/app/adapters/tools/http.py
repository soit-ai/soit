""" http_tools

HTTP tools port adapter implementation.
"""

from typing import Any

import httpx

from app.adapters.http.governed_client import governed_httpx_client
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.security.egress import GovernedEgressGuard


class HTTPToolsPort(ToolPort):
    """HTTP tool gateway adapter."""

    def __init__(self, egress_guard: GovernedEgressGuard | None = None):
        """Initialize HTTP tool gateway."""
        self.egress_guard = egress_guard or GovernedEgressGuard()

    async def invoke(
        self,
        tool_ref: str,
        parameters: dict[str, Any],
        **kwargs,
    ) -> ToolResponse:
        """Invoke HTTP tool."""
        # Extract HTTP parameters
        url = parameters.get("url")
        method = parameters.get("method", "POST")
        headers = dict(parameters.get("headers", {}) or {})
        idempotency_key = kwargs.get("idempotency_key")
        if idempotency_key and method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            headers.setdefault("Idempotency-Key", str(idempotency_key))
        body = parameters.get("body", {})
        query = parameters.get("query", {})
        timeout_s = kwargs.get("timeout_s")
        ctx: RequestContext | None = kwargs.get("ctx")

        if not url:
            return ToolResponse(
                result=None,
                success=False,
                error="Missing URL parameter",
            )
        if ctx is None:
            return ToolResponse(
                result=None,
                success=False,
                error="HTTP tool invocation requires ctx",
            )

        try:
            async with governed_httpx_client(
                ctx=ctx,
                resource_ref=tool_ref,
                egress_guard=self.egress_guard,
                timeout=30.0,
            ) as client:
                method_upper = method.upper()
                if method_upper in {"GET", "DELETE"}:
                    response = await client.request(
                        method_upper,
                        url,
                        headers=headers,
                        params=query or body,
                        timeout=timeout_s,
                    )
                elif method_upper in {"POST", "PUT", "PATCH"}:
                    response = await client.request(
                        method_upper,
                        url,
                        headers=headers,
                        params=query or None,
                        json=body,
                        timeout=timeout_s,
                    )
                else:
                    return ToolResponse(
                        result=None,
                        success=False,
                        error=f"Unsupported method: {method}",
                    )

                response.raise_for_status()

            return ToolResponse(
                result=response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                success=True,
                metadata={
                    "http_status": response.status_code,
                    "latency_ms": int(response.elapsed.total_seconds() * 1000),
                },
            )
        except httpx.HTTPError as e:
            return ToolResponse(
                result=None,
                success=False,
                error=str(e),
            )
