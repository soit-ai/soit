"""http_runtime

HTTP-based PluginRuntimePort adapter.

Expected manifest shape (stored in registry payload under kind="plugin"):

{
  "runtime": {
    "type": "http",
    "base_url": "https://plugin.example.com",
    "invoke_path": "/invoke"   # optional, default "/invoke"
  }
}

Request format:
POST {base_url}{invoke_path}
{
  "plugin": {"name": "...", "version": "..."},
  "tool": {"name": "..."},
  "input": {...},
  "context": {"tenant_id": "...", "workspace_id": "...", "user_id": "..."}  # best-effort
}
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.adapters.http.governed_client import governed_httpx_client
from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.kernel.registry.deps import get_registry
from app.kernel.security.egress import GovernedEgressGuard
from app.settings.settings import settings


class HTTPPluginRuntimePort(PluginRuntimePort):
    """HTTP plugin runtime adapter."""

    def __init__(
        self,
        *,
        registry: Any | None = None,
        egress_guard: GovernedEgressGuard | None = None,
    ) -> None:
        self._reg = registry or get_registry()
        self._egress_guard = egress_guard or GovernedEgressGuard()

    def list_tools(self, *, plugin_name: str, version: str, ctx: RequestContext) -> list[dict[str, Any]]:
        found = self._reg.get(kind="plugin", tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, name=plugin_name, version=version)
        if not found:
            raise ValidationError(f"Plugin not installed: {plugin_name}@{version}")
        _, payload = found
        tools = (payload or {}).get("tools") or []
        out: list[dict[str, Any]] = []
        for tool_ref in tools:
            latest = self._reg.get_latest(kind="tool", tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, name=tool_ref)
            if not latest:
                continue
            _, tool_payload = latest
            tool_spec = (tool_payload or {}).get("tool_spec") or {}
            if tool_spec:
                out.append(tool_spec)
        return out

    async def invoke(
        self,
        *,
        plugin_name: str,
        version: str,
        tool_name: str,
        input_json: dict[str, Any],
        ctx: RequestContext,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        found = self._reg.get(kind="plugin", tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, name=plugin_name, version=version)
        if not found:
            raise ValidationError(f"Plugin not installed: {plugin_name}@{version}")

        _, _payload = found

        manifest = (_payload or {}).get("manifest") or {}
        runtime = (manifest or {}).get("runtime") or {}
        if (runtime.get("type") or "http") != "http":
            raise ValidationError(f"Unsupported plugin runtime type: {runtime.get('type')}")

        base_url = runtime.get("base_url")
        if not base_url:
            raise ValidationError("Plugin manifest missing runtime.base_url")
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "::1") and not settings.plugin_runtime_allow_localhost:
            raise ValidationError("Plugin runtime must run out-of-process (localhost not allowed)")
        invoke_path = runtime.get("invoke_path") or "/invoke"
        if not str(invoke_path).startswith("/"):
            invoke_path = f"/{invoke_path}"
        url = base_url.rstrip("/") + invoke_path

        context_json: dict[str, Any] = {
            "tenant_id": getattr(ctx, "tenant_id", None),
            "workspace_id": getattr(ctx, "workspace_id", None),
            "user_id": getattr(ctx, "user_id", None),
        }

        req = {
            "plugin": {"name": plugin_name, "version": version},
            "tool": {"name": tool_name},
            "input": input_json or {},
            "context": {k: v for k, v in context_json.items() if v is not None},
        }

        timeout = httpx.Timeout(timeout_s or 60.0)
        async with governed_httpx_client(
            ctx=ctx,
            resource_ref=f"plugin:{plugin_name}@{version}",
            egress_guard=self._egress_guard,
            timeout=timeout,
        ) as client:
            resp = await client.post(url, json=req)
            resp.raise_for_status()
            data = resp.json()

        if not isinstance(data, dict):
            raise ValidationError("Plugin runtime returned non-object JSON")
        return data
