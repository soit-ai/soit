"""test_tool_router_strict

Unit tests for RegistryToolRouterPort strict tenant/workspace behavior.
"""

import pytest
from unittest.mock import AsyncMock

from app.adapters.tools.router import RegistryToolRouterPort
from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.registry.deps import get_registry
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.ports.tools.interface import ToolResponse


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
