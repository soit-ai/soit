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

from typing import Any, Dict, List, Optional

import httpx

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ValidationError
from app.kernel.registry.deps import get_registry
from app.kernel.ports.plugins.interface import PluginRuntimePort


class HTTPPluginRuntimePort(PluginRuntimePort):
    """HTTP plugin runtime adapter."""

    def __init__(self) -> None:
        self._reg = get_registry()

    def list_tools(self, *, plugin_name: str, version: str, ctx: RequestContext) -> List[Dict[str, Any]]:
        found = self._reg.get(kind="plugin", tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, name=plugin_name, version=version)
        if not found:
            raise ValidationError(f"Plugin not installed: {plugin_name}@{version}")
        _, payload = found
        tools = (payload or {}).get("tools") or []
        out: List[Dict[str, Any]] = []
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
        input_json: Dict[str, Any],
        ctx: RequestContext,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
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
        invoke_path = runtime.get("invoke_path") or "/invoke"
        url = base_url.rstrip("/") + invoke_path

        context_json: Dict[str, Any] = {
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
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=req)
            resp.raise_for_status()
            data = resp.json()

        if not isinstance(data, dict):
            raise ValidationError("Plugin runtime returned non-object JSON")
        return data
