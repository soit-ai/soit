""" http_tools

HTTP tools port adapter implementation.
"""

from typing import Any

import httpx

from app.kernel.ports.tools.interface import ToolPort, ToolResponse


class HTTPToolsPort(ToolPort):
    """HTTP tool gateway adapter."""

    def __init__(self):
        """Initialize HTTP tool gateway."""
        self.client = httpx.AsyncClient(timeout=30.0)

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
        headers = parameters.get("headers", {})
        body = parameters.get("body", {})
        query = parameters.get("query", {})
        timeout_s = kwargs.get("timeout_s")

        if not url:
            return ToolResponse(
                result=None,
                success=False,
                error="Missing URL parameter",
            )

        try:
            # Make HTTP request
            method_upper = method.upper()
            if method_upper in {"GET", "DELETE"}:
                response = await self.client.request(
                    method_upper,
                    url,
                    headers=headers,
                    params=query or body,
                    timeout=timeout_s,
                )
            elif method_upper in {"POST", "PUT", "PATCH"}:
                response = await self.client.request(
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
