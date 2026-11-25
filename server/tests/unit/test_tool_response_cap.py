"""HTTP tools and plugin runtimes refuse a response body past the size limit."""

from __future__ import annotations

import httpx
import pytest

from app.adapters.http import governed_client
from app.adapters.plugins import http_runtime as plugin_runtime_module
from app.adapters.tools import http as http_tool_module
from app.adapters.tools.http import HTTPToolsPort
from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.settings.settings import settings


class _AllowAll:
    async def authorize(self, *args, **kwargs) -> None:
        return None


def _ctx() -> RequestContext:
    return RequestContext(tenant_id="t", workspace_id="w", user_id="u")


def _serve(monkeypatch, module, handler) -> None:
    """Route the module's governed client through an in-memory transport."""

    def client(**kwargs):
        kwargs.pop("transport", None)
        return governed_client.governed_httpx_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(module, "governed_httpx_client", client)


@pytest.mark.asyncio
async def test_an_http_tool_response_past_the_limit_fails_the_call(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tool_max_response_bytes", 1024)
    # Streamed without a Content-Length, so only counting can catch it.
    async def chunks():
        for _ in range(2):
            yield b"x" * 600

    _serve(monkeypatch, http_tool_module, lambda request: httpx.Response(200, content=chunks()))

    response = await HTTPToolsPort(egress_guard=_AllowAll()).invoke(
        "tool:http:big", {"url": "https://tools.example.com/big", "method": "GET"}, ctx=_ctx()
    )

    assert response.success is False
    assert "1024 byte limit" in (response.error or "")


@pytest.mark.asyncio
async def test_an_http_tool_response_within_the_limit_is_decoded(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tool_max_response_bytes", 1024)
    _serve(monkeypatch, http_tool_module, lambda request: httpx.Response(200, json={"ok": True}))

    response = await HTTPToolsPort(egress_guard=_AllowAll()).invoke(
        "tool:http:small", {"url": "https://tools.example.com/small", "method": "POST", "body": {}}, ctx=_ctx()
    )

    assert response.success is True
    assert response.result == {"ok": True}
    assert response.metadata["http_status"] == 200


@pytest.mark.asyncio
async def test_a_plugin_runtime_response_past_the_limit_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tool_max_response_bytes", 1024)
    _serve(
        monkeypatch,
        plugin_runtime_module,
        lambda request: httpx.Response(200, headers={"content-length": "4096"}, content=b"{" + b" " * 4094 + b"}"),
    )
    class Registry:
        def get(self, **kwargs):
            return ("1.0.0", {"manifest": {"runtime": {"type": "http", "base_url": "https://plugins.example.com"}}})

    adapter = plugin_runtime_module.HTTPPluginRuntimePort(registry=Registry(), egress_guard=_AllowAll())

    with pytest.raises(ValidationError, match="too large"):
        await adapter.invoke(plugin_name="p", version="1.0.0", tool_name="t", input_json={}, ctx=_ctx())
