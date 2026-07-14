"""test_tool_router_strict

Unit tests for RegistryToolRouterPort strict tenant/workspace behavior.
"""

from unittest.mock import AsyncMock

import pytest

from app.adapters.tools.router import RegistryToolRouterPort
from app.kernel.commons.errors import ForbiddenError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.ports.tools.interface import ToolResponse
from app.kernel.registry.deps import get_registry
from app.kernel.security import egress
from app.settings.settings import settings


class DummyPluginRuntimePort:
    """Plugin runtime stub for tool router tests."""

    def __init__(self, result=None):
        self.result = result or {"ok": True}
        self.calls = []

    def list_tools(self, *, plugin_name, version, ctx):
        return []

    async def invoke(self, *, plugin_name, version, tool_name, input_json, ctx, timeout_s=None):
        self.calls.append(
            {
                "plugin_name": plugin_name,
                "version": version,
                "tool_name": tool_name,
                "input_json": input_json,
                "ctx": ctx,
                "timeout_s": timeout_s,
            }
        )
        return self.result


class DummySecretsPort(SecretsPort):
    """Secrets port stub for tool router tests."""

    def __init__(self, value: str):
        self.value = value

    async def get_secret(self, secret_ref: str, **kwargs):
        return self.value

    async def set_secret(self, secret_ref: str, value: str, **kwargs):
        raise RuntimeError("Not implemented")

    async def delete_secret(self, secret_ref: str, **kwargs):
        raise RuntimeError("Not implemented")


@pytest.mark.asyncio
async def test_strict_requires_context():
    port = RegistryToolRouterPort(http_port=AsyncMock())
    with pytest.raises(ValidationError):
        await port.invoke("tool:http:demo", {"foo": "bar"}, strict_registry=True)


@pytest.mark.asyncio
async def test_strict_requires_registered_tool(test_context: RequestContext):
    port = RegistryToolRouterPort(http_port=AsyncMock())
    # no registration for this tenant/workspace
    with pytest.raises(ValidationError):
        await port.invoke("tool:http:missing", {"foo": "bar"}, strict_registry=True, ctx=test_context)


@pytest.mark.asyncio
async def test_registered_http_tool_routes_to_http_port(test_context: RequestContext):
    http = AsyncMock()
    http.invoke = AsyncMock(return_value=ToolResponse(result={"ok": True}))

    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=test_context.tenant_id,
        workspace_id=test_context.workspace_id,
        name="tool:http:demo",
        version="1.0.0",
        payload={
            "tool_spec": {
                "adapter": "http",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "policy": {"audit_level": "basic"},
                "http": {
                    "url": "https://example.com/echo",
                    "method": "POST",
                    "headers": {"X-Test": "1"},
                },
            }
        },
    )

    port = RegistryToolRouterPort(http_port=http)
    await port.invoke("tool:http:demo", {"body": {"a": 1}}, strict_registry=True, ctx=test_context)

    http.invoke.assert_awaited_once()
    args, kwargs = http.invoke.await_args
    assert kwargs["tool_ref"] == "tool:http:demo"
    assert kwargs["parameters"]["url"] == "https://example.com/echo"
    assert kwargs["parameters"]["method"] == "POST"
    assert kwargs["parameters"]["headers"]["X-Test"] == "1"
    assert kwargs["parameters"]["body"] == {"a": 1}


@pytest.mark.asyncio
async def test_non_strict_fallback_to_raw_http(test_context: RequestContext):
    http = AsyncMock()
    http.invoke = AsyncMock(return_value=ToolResponse(result={"ok": True}))

    port = RegistryToolRouterPort(http_port=http)
    await port.invoke(
        "tool:http:any",
        {"url": "https://example.com", "method": "GET"},
        strict_registry=False,
        ctx=test_context,
    )
    http.invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_registered_http_tool_injects_api_key(test_context: RequestContext):
    http = AsyncMock()
    http.invoke = AsyncMock(return_value=ToolResponse(result={"ok": True}))

    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=test_context.tenant_id,
        workspace_id=test_context.workspace_id,
        name="tool:http:secure",
        version="1.0.0",
        payload={
            "tool_spec": {
                "adapter": "http",
                "input_schema": {"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}}},
                "output_schema": {"type": "object"},
                "policy": {"audit_level": "basic"},
                "http": {"url": "https://example.com/secure", "method": "POST"},
                "auth": {
                    "type": "api_key",
                    "api_key": {"in": "header", "name": "X-Api-Key", "secret_ref": "secret:test"},
                },
            }
        },
    )

    secrets = DummySecretsPort("token-123")
    port = RegistryToolRouterPort(http_port=http, secrets_port_factory=lambda ctx: secrets)
    await port.invoke("tool:http:secure", {"title": "hello"}, strict_registry=True, ctx=test_context)

    http.invoke.assert_awaited_once()
    _, kwargs = http.invoke.await_args
    assert kwargs["parameters"]["headers"]["X-Api-Key"] == "token-123"


@pytest.mark.asyncio
async def test_builtin_tool_auto_registers_and_validates(test_context: RequestContext):
    http = AsyncMock()
    http.invoke = AsyncMock(return_value=ToolResponse(result={"ok": True}))

    port = RegistryToolRouterPort(http_port=http)
    await port.invoke(
        "tool:http:request",
        {"url": "https://example.com", "method": "GET"},
        strict_registry=True,
        ctx=test_context,
    )

    http.invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_registered_plugin_tool_routes_to_plugin_runtime_and_wraps_response(test_context: RequestContext):
    plugin_runtime = DummyPluginRuntimePort(result={"echo": "ok"})
    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=test_context.tenant_id,
        workspace_id=test_context.workspace_id,
        name="tool:http:plugin_echo",
        version="1.0.0",
        payload={
            "tool_spec": {
                "adapter": "http",
                "input_schema": {"type": "object", "properties": {"value": {"type": "string"}}},
                "output_schema": {"type": "object", "required": ["echo"], "properties": {"echo": {"type": "string"}}},
            },
            "plugin": {"name": "demo-plugin", "version": "1.0.0"},
        },
    )

    port = RegistryToolRouterPort(plugin_runtime_port=plugin_runtime)
    response = await port.invoke(
        "tool:http:plugin_echo",
        {"value": "hello"},
        strict_registry=True,
        ctx=test_context,
        timeout_s=5,
    )

    assert isinstance(response, ToolResponse)
    assert response.success is True
    assert response.result == {"echo": "ok"}
    assert response.metadata == {
        "source_kind": "plugin",
        "adapter": "plugin",
        "plugin_name": "demo-plugin",
        "plugin_version": "1.0.0",
        "tool_ref": "tool:http:plugin_echo",
    }
    assert plugin_runtime.calls == [
        {
            "plugin_name": "demo-plugin",
            "version": "1.0.0",
            "tool_name": "plugin_echo",
            "input_json": {"value": "hello"},
            "ctx": test_context,
            "timeout_s": 5,
        }
    ]


@pytest.mark.asyncio
async def test_registered_plugin_tool_enforces_egress_before_plugin_runtime(
    monkeypatch,
    test_context: RequestContext,
):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", [])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(egress, "_egress_policy", None)
    plugin_runtime = DummyPluginRuntimePort()
    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=test_context.tenant_id,
        workspace_id=test_context.workspace_id,
        name="tool:http:plugin_blocked",
        version="1.0.0",
        payload={
            "tool_spec": {
                "adapter": "http",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "http": {"url": "https://blocked.example.com/run"},
                "policy": {"egress": {"allow": ["allowed.example.com"]}},
            },
            "plugin": {"name": "demo-plugin", "version": "1.0.0"},
        },
    )

    port = RegistryToolRouterPort(plugin_runtime_port=plugin_runtime)
    with pytest.raises(ForbiddenError):
        await port.invoke(
            "tool:http:plugin_blocked",
            {},
            strict_registry=True,
            ctx=test_context,
        )

    assert plugin_runtime.calls == []


@pytest.mark.asyncio
async def test_registered_plugin_tool_injects_api_key_under_reserved_auth_key(
    monkeypatch,
    test_context: RequestContext,
):
    monkeypatch.setattr(settings, "enable_egress_policy", False)
    plugin_runtime = DummyPluginRuntimePort(result={"ok": True})
    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=test_context.tenant_id,
        workspace_id=test_context.workspace_id,
        name="tool:http:plugin_secure",
        version="1.0.0",
        payload={
            "tool_spec": {
                "adapter": "http",
                "input_schema": {"type": "object", "properties": {"ticket": {"type": "string"}}},
                "output_schema": {"type": "object"},
                "auth": {
                    "type": "api_key",
                    "api_key": {"in": "header", "name": "X-Api-Key", "secret_ref": "secret:plugin-token"},
                },
            },
            "plugin": {"name": "demo-plugin", "version": "1.0.0"},
        },
    )
    secrets = DummySecretsPort("token-123")

    port = RegistryToolRouterPort(
        plugin_runtime_port=plugin_runtime,
        secrets_port_factory=lambda ctx: secrets,
    )
    await port.invoke(
        "tool:http:plugin_secure",
        {"ticket": "T-1"},
        strict_registry=True,
        ctx=test_context,
    )

    assert plugin_runtime.calls[0]["input_json"] == {
        "ticket": "T-1",
        "_soit_auth": {"headers": {"X-Api-Key": "token-123"}, "query": {}},
    }


@pytest.mark.asyncio
async def test_registered_plugin_tool_validates_plugin_output_schema(test_context: RequestContext):
    plugin_runtime = DummyPluginRuntimePort(result={"echo": 123})
    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=test_context.tenant_id,
        workspace_id=test_context.workspace_id,
        name="tool:http:plugin_echo_schema",
        version="1.0.0",
        payload={
            "tool_spec": {
                "adapter": "http",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object", "properties": {"echo": {"type": "string"}}},
            },
            "plugin": {"name": "demo-plugin", "version": "1.0.0"},
        },
    )

    port = RegistryToolRouterPort(plugin_runtime_port=plugin_runtime)
    with pytest.raises(ValidationError):
        await port.invoke(
            "tool:http:plugin_echo_schema",
            {},
            strict_registry=True,
            ctx=test_context,
        )


@pytest.mark.asyncio
async def test_registered_plugin_tool_requires_plugin_runtime_port(test_context: RequestContext):
    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=test_context.tenant_id,
        workspace_id=test_context.workspace_id,
        name="tool:http:plugin_missing_runtime",
        version="1.0.0",
        payload={
            "tool_spec": {
                "adapter": "http",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            },
            "plugin": {"name": "demo-plugin", "version": "1.0.0"},
        },
    )

    port = RegistryToolRouterPort()
    with pytest.raises(ValidationError):
        await port.invoke(
            "tool:http:plugin_missing_runtime",
            {},
            strict_registry=True,
            ctx=test_context,
        )
