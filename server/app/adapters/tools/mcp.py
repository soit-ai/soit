"""Official MCP SDK tool adapter."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from typing import Any, Protocol

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import and_, select

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.modules.plugin.domain.models import PluginInstalledArtifact

logger = logging.getLogger(__name__)


class MCPSession(Protocol):
    async def initialize(self) -> Any: ...

    async def list_tools(self) -> Any: ...

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any: ...


SessionFactory = Callable[..., AbstractAsyncContextManager[MCPSession]]


def parse_mcp_tool_ref(tool_ref: str) -> tuple[str, str]:
    """Parse ``mcp_tool:{server}:{tool}`` into server and tool names."""
    parts = tool_ref.split(":", 2)
    if len(parts) != 3 or parts[0] != "mcp_tool" or not parts[1] or not parts[2]:
        raise ValueError(f"Invalid MCP tool ref format: {tool_ref}")
    return parts[1], parts[2]


@asynccontextmanager
async def _official_session_factory(
    *, endpoint: str, headers: dict[str, str], timeout: float
) -> AsyncIterator[ClientSession]:
    """Create one official streamable HTTP MCP session per invocation."""
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as http_client:
        async with streamable_http_client(endpoint, http_client=http_client) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=timedelta(seconds=timeout),
            ) as session:
                yield session


def _dump_content_item(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump(by_alias=True, exclude_none=True)
    if isinstance(item, dict):
        return item
    data = vars(item) if hasattr(item, "__dict__") else {"value": str(item)}
    return {key: value for key, value in data.items() if value is not None}


def _content_result(call_result: Any) -> tuple[Any, str | None]:
    structured = getattr(call_result, "structuredContent", None)
    if structured is not None:
        return structured, None

    content = list(getattr(call_result, "content", None) or [])
    serialized = [_dump_content_item(item) for item in content]
    text = "\n".join(
        str(item.get("text", ""))
        for item in serialized
        if item.get("type") == "text" and item.get("text") is not None
    )
    result: Any = {"content": serialized}
    if text:
        result["text"] = text
    error = text or "MCP tool returned an error"
    return result, error


class MCPToolAdapter(ToolPort):
    """Invoke remote tools through the official MCP Python SDK."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        session_factory: SessionFactory | None = None,
    ) -> None:
        self._timeout = timeout
        self._session_factory = session_factory or _official_session_factory

    def _resolve_server(self, server_key: str, db: Any, ctx: RequestContext) -> Any | None:
        artifact_ref = f"mcp_server:{server_key}"
        query = select(PluginInstalledArtifact).where(
            and_(
                PluginInstalledArtifact.tenant_id == ctx.tenant_id,
                PluginInstalledArtifact.workspace_id == ctx.workspace_id,
                PluginInstalledArtifact.artifact_kind == "mcp_server",
                PluginInstalledArtifact.enabled.is_(True),
                PluginInstalledArtifact.state == "enabled",
            )
        )
        for raw_row in db.exec(query).all():
            artifact = (
                raw_row[0]
                if hasattr(raw_row, "__getitem__") and not isinstance(raw_row, PluginInstalledArtifact)
                else raw_row
            )
            metadata = artifact.metadata_json or {}
            server = metadata.get("mcp_server") or {}
            name = str(server.get("name") or artifact.artifact_ref.split(":", 1)[-1])
            if artifact.artifact_ref != artifact_ref and name != server_key and artifact.artifact_id != artifact_ref:
                continue
            return SimpleNamespace(
                id=artifact.artifact_id or artifact.artifact_ref,
                name=name,
                endpoint=server.get("endpoint"),
                transport=server.get("transport"),
                auth_config=server.get("auth_config") or {},
            )
        return None

    async def _build_auth_headers(
        self,
        auth_config: dict[str, Any],
        secrets_port: SecretsPort | None,
    ) -> dict[str, str]:
        if not auth_config:
            return {}
        auth_type = auth_config.get("type")
        if auth_type not in {"bearer", "api_key"}:
            raise ValueError(f"Unsupported MCP authentication type: {auth_type}")
        if "token" in auth_config or "value" in auth_config:
            raise ValueError("MCP credentials must use secret_id")

        if auth_type == "bearer":
            secret_id = auth_config.get("secret_id")
            header_name = "Authorization"
            prefix = "Bearer "
        else:
            api_key = auth_config.get("api_key") or {}
            if "value" in api_key:
                raise ValueError("MCP credentials must use secret_id")
            if api_key.get("in", "header") != "header":
                raise ValueError("MCP API keys are supported only in headers")
            secret_id = api_key.get("secret_id")
            header_name = str(api_key.get("name") or "X-API-Key")
            prefix = ""

        if not secret_id:
            raise ValueError("MCP authentication requires secret_id")
        if secrets_port is None:
            raise ValueError("MCP authentication requires a secrets port")
        secret = await secrets_port.get_secret(secret_id=str(secret_id))
        return {header_name: f"{prefix}{secret}"}

    async def invoke(
        self,
        tool_ref: str,
        parameters: dict[str, Any],
        **kwargs: Any,
    ) -> ToolResponse:
        db = kwargs.get("db")
        ctx: RequestContext | None = kwargs.get("ctx")
        if db is None or ctx is None:
            return ToolResponse(result=None, success=False, error="MCP tool invocation requires db and ctx")

        try:
            server_key, tool_name = parse_mcp_tool_ref(tool_ref)
            server = self._resolve_server(server_key, db, ctx)
            if server is None:
                raise ValueError(f"MCP server not found: {server_key}")
            if server.transport != "streamable_http":
                raise ValueError(
                    f"MCP server {server_key} must use transport streamable_http"
                )
            if not server.endpoint:
                raise ValueError(f"MCP server endpoint missing: {server_key}")

            timeout = float(kwargs.get("timeout_s", self._timeout))
            headers = await self._build_auth_headers(
                server.auth_config,
                kwargs.get("secrets_port"),
            )
            async with self._session_factory(
                endpoint=str(server.endpoint).rstrip("/"),
                headers=headers,
                timeout=timeout,
            ) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                if tool_name not in {tool.name for tool in tools_result.tools}:
                    raise ValueError(f"MCP tool not found: {tool_name}")
                call_result = await session.call_tool(tool_name, arguments=parameters)

            result, error_text = _content_result(call_result)
            is_error = bool(getattr(call_result, "isError", False))
            return ToolResponse(
                result=None if is_error else result,
                success=not is_error,
                error=error_text if is_error else None,
                metadata={
                    "server_id": server.id,
                    "server_name": server.name,
                    "tool_name": tool_name,
                    "transport": "streamable_http",
                    "content": result.get("content", []) if isinstance(result, dict) else [],
                },
            )
        except Exception as exc:
            logger.warning("MCP tool invocation failed for %s: %s", tool_ref, type(exc).__name__)
            return ToolResponse(result=None, success=False, error=str(exc))
