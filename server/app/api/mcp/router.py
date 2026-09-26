"""SOIT as an MCP server: one workspace's tools over streamable HTTP.

``POST /mcp`` answers JSON-RPC in the stateless form of the MCP streamable
HTTP transport: every request stands alone, no session id is issued, answers
are ``application/json`` rather than an event stream, and the server never
calls the client back. The credential names the workspace, as at ``/v1``: an
API key, or a session with ``X-Workspace-Id``.

``tools/list`` lists the tools the credential may invoke, and ``tools/call``
goes through the tool invocation service, so every call is a governed run of
its own (``mode=tool``), exactly as through ``/api/v1/tools``. A tool that
needs approval does not run: the result says so, and the same call sent again
once the approval is decided runs it or reports the rejection.

``/.well-known/oauth-protected-resource`` describes the endpoint as an OAuth
2.1 protected resource (RFC 9728), and a request without a usable credential
is answered 401 with a challenge that names that document.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import urlsplit

import orjson
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from mcp import types
from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.mcp.names import tool_names
from app.infra.db.session import get_async_db
from app.kernel.commons.errors import KernelError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.tools.catalog import CatalogTool
from app.kernel.runtime.tools.approval import tool_approval_rule
from app.kernel.runtime.tools.invocation import ToolInvocation, ToolInvocationService
from app.middleware.auth import get_current_context, security
from app.settings.settings import settings
from app.wiring.services import build_tool_invocation_service

logger = logging.getLogger(__name__)

router = APIRouter()
well_known_router = APIRouter()

SERVER_NAME = "soit"
METADATA_PATH = "/.well-known/oauth-protected-resource"
META_PREFIX = "ai.soit/"
INSTRUCTIONS = (
    "Tools of one SOIT workspace. Every call is a governed run in SOIT: secrets, egress, budgets "
    "and audit apply. A tool marked as needing approval does not run until a reviewer approves "
    "the call in SOIT; call it again with the same arguments once approved."
)


class _RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class _Call:
    ctx: RequestContext
    db: AsyncSession
    params: dict[str, Any]


async def mcp_caller(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> RequestContext | None:
    """The caller, or None when the request carries no credential that works."""

    try:
        return await get_current_context(request, credentials, x_workspace_id, x_api_key)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


def _resource_url(request: Request) -> str:
    if settings.mcp_resource_url:
        return settings.mcp_resource_url.rstrip("/")
    return f"{str(request.base_url).rstrip('/')}/mcp"


def _metadata_url(request: Request) -> str:
    resource = urlsplit(_resource_url(request))
    return f"{resource.scheme}://{resource.netloc}{METADATA_PATH}{resource.path}"


def _unauthorized(request: Request) -> JSONResponse:
    presented = bool(request.headers.get("authorization") or request.headers.get("x-api-key"))
    challenge = f'resource_metadata="{_metadata_url(request)}"'
    if presented:
        challenge = f'error="invalid_token", {challenge}'
    return JSONResponse(
        {
            "error": "invalid_token" if presented else "unauthorized",
            "error_description": "A SOIT API key is required, sent as a bearer token",
        },
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": f"Bearer {challenge}"},
    )


def _origin_allowed(request: Request) -> bool:
    # DNS rebinding protection: a browser page may only reach the endpoint
    # from its own origin or one the deployment lists. Clients that are not
    # browsers send no Origin.
    origin = request.headers.get("origin")
    if not origin:
        return True
    if origin.rstrip("/") in {entry.rstrip("/") for entry in settings.mcp_allowed_origins}:
        return True
    return urlsplit(origin).netloc == request.headers.get("host")


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_none=True, mode="json")


def _rpc_result(request_id: Any, result: BaseModel | dict[str, Any]) -> JSONResponse:
    body = _dump(result) if isinstance(result, BaseModel) else result
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": body})


def _rpc_error(request_id: Any, code: int, message: str, *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}},
        status_code=status_code,
    )


def _input_schema(schema: dict[str, Any]) -> dict[str, Any]:
    return schema if schema.get("type") == "object" else {**schema, "type": "object"}


def _description(tool: CatalogTool) -> str:
    text = tool.description or tool.name
    if tool_approval_rule(tool.policy).required:
        text = f"{text} Needs approval in SOIT before it runs."
    return text


def _json_value(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _content_of(result: Any) -> tuple[list[types.ContentBlock], dict[str, Any] | None]:
    if isinstance(result, dict) and isinstance(result.get("content"), list):
        # A tool of an MCP server SOIT fronts: pass its own content through.
        try:
            passed = types.CallToolResult.model_validate({"content": result["content"]})
            structured = result.get("structuredContent")
            return passed.content, _json_value(structured) if isinstance(structured, dict) else None
        except PydanticValidationError:
            pass
    value = _json_value(result)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return [types.TextContent(type="text", text=text)], value if isinstance(value, dict) else None


def _refusal_text(exc: KernelError) -> str:
    """The refusal, with what was wrong with the arguments when it says."""
    errors = (exc.details or {}).get("errors")
    if isinstance(errors, list):
        reasons = [str(item["message"]) for item in errors if isinstance(item, dict) and item.get("message")]
        if reasons:
            return f"{exc.message}: {'; '.join(reasons)}"
    return exc.message


def _tool_error(text: str, meta: dict[str, Any] | None = None) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        isError=True,
        _meta=meta,
    )


def _call_result(invocation: ToolInvocation) -> types.CallToolResult:
    meta: dict[str, Any] = {
        f"{META_PREFIX}run_id": invocation.run_id,
        f"{META_PREFIX}tool_ref": invocation.tool_ref,
    }
    if invocation.approval_id:
        meta[f"{META_PREFIX}approval_id"] = invocation.approval_id
    if invocation.status == "succeeded":
        content, structured = _content_of(invocation.result)
        return types.CallToolResult(content=content, structuredContent=structured, isError=False, _meta=meta)
    if invocation.status == "waiting_approval":
        return _tool_error(
            "Not run: this call needs approval in SOIT"
            f" (approval {invocation.approval_id}, run {invocation.run_id})."
            " Once a reviewer approves it under Govern > Approvals, call the tool again"
            " with the same arguments to run it.",
            meta,
        )
    if invocation.status == "rejected":
        return _tool_error("Not run: a reviewer rejected this call in SOIT.", meta)
    return _tool_error(invocation.error or "The tool call failed", meta)


async def _initialize(call: _Call) -> BaseModel:
    requested = call.params.get("protocolVersion")
    version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else types.LATEST_PROTOCOL_VERSION
    return types.InitializeResult(
        protocolVersion=version,
        capabilities=types.ServerCapabilities(tools=types.ToolsCapability(listChanged=False)),
        serverInfo=types.Implementation(name=SERVER_NAME, title="SOIT", version=settings.platform_version),
        instructions=INSTRUCTIONS,
    )


async def _ping(_call: _Call) -> dict[str, Any]:
    return {}


async def _named_tools(service: ToolInvocationService) -> tuple[list[CatalogTool], dict[str, str]]:
    tools = await service.list_tools()
    return tools, tool_names(tool.ref for tool in tools)


async def _list_tools(call: _Call) -> BaseModel:
    # A credential that may not write may not invoke, so it is offered nothing.
    if not call.ctx.can_write():
        return types.ListToolsResult(tools=[])
    tools, names = await _named_tools(build_tool_invocation_service(db=call.db, ctx=call.ctx))
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name=names[tool.ref],
                title=tool.name,
                description=_description(tool),
                inputSchema=_input_schema(tool.input_schema),
                _meta={f"{META_PREFIX}tool_ref": tool.ref},
            )
            for tool in tools
        ]
    )


async def _call_tool(call: _Call) -> BaseModel:
    name = call.params.get("name")
    arguments = call.params.get("arguments") or {}
    if not isinstance(name, str) or not isinstance(arguments, dict):
        raise _RpcError(types.INVALID_PARAMS, "tools/call takes a tool name and an arguments object")
    if not call.ctx.can_write():
        raise _RpcError(types.INVALID_PARAMS, f"Unknown tool: {name}")
    service = build_tool_invocation_service(db=call.db, ctx=call.ctx)
    _, names = await _named_tools(service)
    tool_ref = next((ref for ref, candidate in names.items() if candidate == name), None)
    if tool_ref is None:
        raise _RpcError(types.INVALID_PARAMS, f"Unknown tool: {name}")
    try:
        invocation = await service.invoke_or_continue(tool_ref, arguments)
    except KernelError as exc:
        # A refusal the model can act on: bad arguments, a blocked address,
        # a spent budget. Reported as the tool's result, not a protocol error.
        return _tool_error(_refusal_text(exc), {f"{META_PREFIX}tool_ref": tool_ref, f"{META_PREFIX}code": exc.code})
    except Exception:
        logger.exception("MCP tool call failed", extra={"tool_ref": tool_ref})
        return _tool_error("The tool call failed", {f"{META_PREFIX}tool_ref": tool_ref})
    return _call_result(invocation)


_HANDLERS: dict[str, Callable[[_Call], Awaitable[BaseModel | dict[str, Any]]]] = {
    "initialize": _initialize,
    "ping": _ping,
    "tools/list": _list_tools,
    "tools/call": _call_tool,
}


@router.post("")
async def mcp_endpoint(
    request: Request,
    ctx: Annotated[RequestContext | None, Depends(mcp_caller)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> Response:
    """One JSON-RPC message in, its answer out."""

    if not _origin_allowed(request):
        return _rpc_error(None, types.INVALID_REQUEST, "Origin not allowed", status_code=status.HTTP_403_FORBIDDEN)
    if ctx is None:
        return _unauthorized(request)
    version = request.headers.get("mcp-protocol-version")
    if version is not None and version not in SUPPORTED_PROTOCOL_VERSIONS:
        return _rpc_error(
            None,
            types.INVALID_REQUEST,
            f"Unsupported protocol version: {version}",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        message = orjson.loads(await request.body())
    except orjson.JSONDecodeError:
        return _rpc_error(None, types.PARSE_ERROR, "Parse error", status_code=status.HTTP_400_BAD_REQUEST)
    if isinstance(message, list):
        return _rpc_error(
            None, types.INVALID_REQUEST, "Batches are not supported", status_code=status.HTTP_400_BAD_REQUEST
        )
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _rpc_error(None, types.INVALID_REQUEST, "Not a JSON-RPC 2.0 message", status_code=status.HTTP_400_BAD_REQUEST)
    if message.get("id") is None:
        # A notification, or an answer to a request this server never sends:
        # accepted, and there is nothing to reply.
        return Response(status_code=status.HTTP_202_ACCEPTED)

    request_id = message["id"]
    method = message.get("method")
    params = message.get("params") or {}
    if not isinstance(method, str):
        return _rpc_error(request_id, types.INVALID_REQUEST, "A request needs a method")
    if not isinstance(params, dict):
        return _rpc_error(request_id, types.INVALID_PARAMS, "params must be an object")
    handler = _HANDLERS.get(method)
    if handler is None:
        return _rpc_error(request_id, types.METHOD_NOT_FOUND, f"Method not found: {method}")
    try:
        result = await handler(_Call(ctx=ctx, db=db, params=params))
    except _RpcError as exc:
        return _rpc_error(request_id, exc.code, exc.message)
    return _rpc_result(request_id, result)


@router.get("")
@router.delete("")
async def mcp_no_stream() -> Response:
    """No server stream and no session: the endpoint is stateless."""

    return Response(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, headers={"Allow": "POST"})


@well_known_router.get(METADATA_PATH)
@well_known_router.get(f"{METADATA_PATH}/mcp")
async def protected_resource_metadata(request: Request) -> JSONResponse:
    """The MCP endpoint as an OAuth 2.1 protected resource (RFC 9728)."""

    body: dict[str, Any] = {
        "resource": _resource_url(request),
        "bearer_methods_supported": ["header"],
        "resource_name": "SOIT MCP",
    }
    if settings.mcp_authorization_servers:
        body["authorization_servers"] = list(settings.mcp_authorization_servers)
    return JSONResponse(body, headers={"Cache-Control": "public, max-age=3600"})
