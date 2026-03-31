"""mcp

MCP tool adapter implementation.

Invokes tools on remote MCP servers using the MCP protocol over HTTP.
Parses mcp_tool:{server_name}:{tool_name} refs, resolves the server
endpoint from the DB, and sends a tools/call JSON-RPC request.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.modules.integrations.mcp.infra.repository import MCPServerRepository

logger = logging.getLogger(__name__)


def parse_mcp_tool_ref(tool_ref: str) -> tuple[str, str]:
    """Parse mcp_tool:{server}:{tool} into (server_key, tool_name).

    Raises ValueError if the ref is not in the expected format.
    """
    parts = tool_ref.split(":", 2)
    if len(parts) != 3 or parts[0] != "mcp_tool":
        raise ValueError(f"Invalid MCP tool ref format: {tool_ref}")
    return parts[1], parts[2]


class MCPToolAdapter(ToolPort):
    """Invoke tools on remote MCP servers via HTTP JSON-RPC."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self._timeout = timeout
        self._client = client or httpx.AsyncClient(timeout=timeout)

    def _resolve_server(
        self,
        server_key: str,
        db: Any,
        ctx: RequestContext,
    ):
        """Resolve MCP server by name or ID."""
        repo = MCPServerRepository(db, ctx)
        server = repo.get_by_name(server_key)
        if not server:
            server = repo.get_by_id(server_key)
        return server

    def _build_auth_headers(self, server) -> Dict[str, str]:
        """Build authentication headers from server config."""
        headers: Dict[str, str] = {}
        auth_cfg = server.auth_config_json or {}
        auth_type = auth_cfg.get("type")
        if auth_type == "bearer":
            token = auth_cfg.get("token")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key":
            api_key_cfg = auth_cfg.get("api_key") or {}
            key_name = api_key_cfg.get("name", "X-API-Key")
            key_value = api_key_cfg.get("value")
            key_in = api_key_cfg.get("in", "header")
            if key_value and key_in == "header":
                headers[key_name] = key_value
        return headers

    async def invoke(
        self,
        tool_ref: str,
        parameters: Dict[str, Any],
        **kwargs: Any,
    ) -> ToolResponse:
        """Invoke an MCP tool on a remote server.

        Args:
            tool_ref: MCP tool reference (mcp_tool:{server}:{tool}).
            parameters: Tool input arguments.
            **kwargs: Must include 'db' and 'ctx' for server resolution.

        Returns:
            ToolResponse with the tool result or error.
        """
        db = kwargs.get("db")
        ctx: Optional[RequestContext] = kwargs.get("ctx")
        if not db or not ctx:
            return ToolResponse(
                result=None,
                success=False,
                error="MCP tool invocation requires db and ctx",
            )

        try:
            server_key, tool_name = parse_mcp_tool_ref(tool_ref)
        except ValueError as exc:
            return ToolResponse(result=None, success=False, error=str(exc))

        server = self._resolve_server(server_key, db, ctx)
        if not server:
            return ToolResponse(
                result=None,
                success=False,
                error=f"MCP server not found: {server_key}",
            )

        if not server.enabled or server.status != "active":
            return ToolResponse(
                result=None,
                success=False,
                error=f"MCP server is not active: {server_key}",
            )

        endpoint = server.endpoint.rstrip("/")
        auth_headers = self._build_auth_headers(server)

        # MCP protocol: JSON-RPC style tools/call
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": parameters,
            },
            "id": kwargs.get("call_id", "1"),
        }

        try:
            response = await self._client.post(
                endpoint,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    **auth_headers,
                },
                timeout=kwargs.get("timeout_s", self._timeout),
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return ToolResponse(
                result=None,
                success=False,
                error=f"MCP server returned {exc.response.status_code}: {exc.response.text[:500]}",
                metadata={"http_status": exc.response.status_code},
            )
        except httpx.HTTPError as exc:
            return ToolResponse(
                result=None,
                success=False,
                error=f"MCP server connection error: {exc}",
            )

        try:
            body = response.json()
        except Exception:
            return ToolResponse(
                result=response.text,
                success=True,
                metadata={"http_status": response.status_code, "raw": True},
            )

        # Handle JSON-RPC error
        if "error" in body:
            error_obj = body["error"]
            error_msg = error_obj.get("message", str(error_obj)) if isinstance(error_obj, dict) else str(error_obj)
            return ToolResponse(
                result=None,
                success=False,
                error=f"MCP tool error: {error_msg}",
                metadata={"http_status": response.status_code},
            )

        # Extract result from JSON-RPC response
        result = body.get("result", body)

        # MCP content array format: extract text content
        if isinstance(result, dict) and "content" in result:
            content_items = result["content"]
            if isinstance(content_items, list):
                text_parts = []
                for item in content_items:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                if text_parts:
                    result = {"text": "\n".join(text_parts), "content": content_items}

        return ToolResponse(
            result=result,
            success=True,
            metadata={
                "http_status": response.status_code,
                "server_id": server.id,
                "server_name": server.name,
                "tool_name": tool_name,
            },
        )
