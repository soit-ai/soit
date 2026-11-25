""" http_tools

HTTP tools port adapter implementation.
"""

import json
import time
from typing import Any

import httpx

from app.adapters.http.capped_body import (
    ResponseTooLargeError,
    decode_body,
    read_capped,
)
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

        method_upper = method.upper()
        if method_upper in {"GET", "DELETE"}:
            request_kwargs: dict[str, Any] = {"params": query or body}
        elif method_upper in {"POST", "PUT", "PATCH"}:
            request_kwargs = {"params": query or None, "json": body}
        else:
            return ToolResponse(
                result=None,
                success=False,
                error=f"Unsupported method: {method}",
            )

        from app.settings.settings import settings

        started = time.monotonic()
        try:
            async with governed_httpx_client(
                ctx=ctx,
                resource_ref=tool_ref,
                egress_guard=self.egress_guard,
                timeout=30.0,
            ) as client:
                async with client.stream(
                    method_upper,
                    url,
                    headers=headers,
                    timeout=timeout_s,
                    **request_kwargs,
                ) as response:
                    response.raise_for_status()
                    content = await read_capped(response, settings.tool_max_response_bytes)
                    result = decode_body(response, content)

            return ToolResponse(
                result=result,
                success=True,
                metadata={
                    "http_status": response.status_code,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                },
            )
        except (httpx.HTTPError, ResponseTooLargeError, json.JSONDecodeError) as e:
            return ToolResponse(
                result=None,
                success=False,
                error=str(e),
            )
