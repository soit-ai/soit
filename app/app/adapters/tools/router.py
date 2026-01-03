""" router

Registry-backed ToolPort implementation.

Behaviour
- If a tool_ref exists in the runtime registry (kind="tool"), resolve its tool_spec and execute via adapter.
- Otherwise, fall back to raw HTTPToolsPort behaviour (expects url/method/headers/body in parameters).

Supported adapters (initial)
- http: uses HTTPToolsPort
"""

from __future__ import annotations

from typing import Dict, Any, Optional

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.registry.deps import get_registry
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.adapters.tools.http import HTTPToolsPort


class RegistryToolRouterPort(ToolPort):
    """ToolPort that resolves tool specs from the in-process registry."""

    def __init__(self, *, http_port: Optional[HTTPToolsPort] = None):
        self.http_port = http_port or HTTPToolsPort()

    async def invoke(self, tool_ref: str, parameters: Dict[str, Any], **kwargs: Any) -> ToolResponse:
        ctx: Optional[RequestContext] = kwargs.get("ctx")
        if ctx is None:
            # allow callers to pass tenant/workspace explicitly
            tenant_id = kwargs.get("tenant_id")
            workspace_id = kwargs.get("workspace_id")
            if tenant_id and workspace_id:
                ctx = RequestContext(tenant_id=tenant_id, workspace_id=workspace_id, user_id=kwargs.get("user_id"))
            else:
                # No ctx: fall back to raw http mode if possible
                return await self.http_port.invoke(tool_ref=tool_ref, parameters=parameters, **kwargs)

        reg = get_registry()
        found = reg.get_latest(kind="tool", tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, name=tool_ref)
        if not found:
            # Not registered -> raw http mode
            return await self.http_port.invoke(tool_ref=tool_ref, parameters=parameters, **kwargs)

        _, payload = found
        tool_spec = payload.get("tool_spec") or {}
        adapter = tool_spec.get("adapter")

        if adapter == "http":
            http_cfg = tool_spec.get("http") or {}
            url = http_cfg.get("url") or parameters.get("url")
            if not url:
                raise ValidationError(f"HTTP tool '{tool_ref}' missing url (tool_spec.http.url)")
            method = http_cfg.get("method") or parameters.get("method") or "POST"
            headers = {}
            headers.update(http_cfg.get("headers") or {})
            headers.update(parameters.get("headers") or {})

            # default body: user parameters (excluding transport keys)
            body = parameters.get("body")
            if body is None:
                body = {k: v for k, v in parameters.items() if k not in ("url", "method", "headers", "body", "query")}

            http_params = {
                "url": url,
                "method": method,
                "headers": headers,
                "body": body,
            }
            # pass through query if provided
            if "query" in parameters:
                http_params["query"] = parameters["query"]

            return await self.http_port.invoke(tool_ref=tool_ref, parameters=http_params, **kwargs)

        # adapter not supported yet
        raise ValidationError(f"Unsupported tool adapter: {adapter} (tool_ref={tool_ref})")
