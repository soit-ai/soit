"""Contract tests for the official MCP SDK adapter."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.adapters.tools.mcp import MCPToolAdapter
from app.kernel.ports.secrets.interface import SecretsPort
from app.modules.plugin.domain.models import (
    Plugin,
    PluginInstallation,
    PluginInstalledArtifact,
    PluginVersion,
)


class StubSecretsPort(SecretsPort):
    def __init__(self, value: str = "resolved-token") -> None:
        self.value = value
        self.get_secret_mock = AsyncMock(return_value=value)

    async def get_secret(self, secret_ref: str, **kwargs):
        return await self.get_secret_mock(secret_ref=secret_ref, **kwargs)

    async def set_secret(self, secret_ref: str, value: str, **kwargs):
        raise NotImplementedError

    async def delete_secret(self, secret_ref: str, **kwargs):
        raise NotImplementedError


class StubSessionFactory:
    def __init__(self, result) -> None:
        self.session = SimpleNamespace(
            initialize=AsyncMock(),
            list_tools=AsyncMock(return_value=SimpleNamespace(tools=[SimpleNamespace(name="echo")])),
            call_tool=AsyncMock(return_value=result),
        )
        self.calls: list[dict[str, object]] = []

    @asynccontextmanager
    async def __call__(self, *, endpoint: str, headers: dict[str, str], timeout: float):
        self.calls.append({"endpoint": endpoint, "headers": headers, "timeout": timeout})
        yield self.session


def _seed_artifact(db, ctx, *, transport: str = "streamable_http", auth_config: dict | None = None):
    plugin = Plugin(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="official-mcp-plugin",
        version="1.0.0",
        publisher="workspace",
        plugin_type="mcp",
        status="active",
        spec_json={"name": "official-mcp-plugin", "publisher": "workspace", "version": "1.0.0"},
        manifest_json={},
        publish_status="published",
    )
    db.add(plugin)
    db.commit()
    db.refresh(plugin)
    version = PluginVersion(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        plugin_id=plugin.id,
        version=1,
        package_version="1.0.0",
        status="published",
        spec_json=plugin.spec_json,
        manifest_json={},
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    installation = PluginInstallation(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        plugin_id=plugin.id,
        plugin_version_id=version.id,
        enabled=True,
        state="installed",
    )
    db.add(installation)
    db.commit()
    db.refresh(installation)
    db.add(
        PluginInstalledArtifact(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            plugin_id=plugin.id,
            plugin_version_id=version.id,
            installation_id=installation.id,
            artifact_kind="mcp_server",
            artifact_ref="mcp_server:official",
            artifact_id="mcp_server:official",
            enabled=True,
            state="enabled",
            metadata_json={
                "mcp_server": {
                    "name": "official",
                    "endpoint": "https://mcp.example.com/mcp",
                    "transport": transport,
                    "auth_config": auth_config or {},
                }
            },
        )
    )
    db.commit()


@pytest.mark.asyncio
async def test_official_session_lifecycle_and_structured_content(db, ctx):
    result = SimpleNamespace(
        structuredContent={"answer": 42},
        content=[SimpleNamespace(type="text", text="fallback")],
        isError=False,
    )
    factory = StubSessionFactory(result)
    secrets = StubSecretsPort()
    _seed_artifact(
        db,
        ctx,
        auth_config={"type": "bearer", "secret_ref": "secret:mcp-token"},
    )

    response = await MCPToolAdapter(session_factory=factory).invoke(
        "mcp_tool:official:echo",
        {"value": "hello"},
        db=db,
        ctx=ctx,
        secrets_port=secrets,
    )

    assert response.success is True
    assert response.result == {"answer": 42}
    factory.session.initialize.assert_awaited_once_with()
    factory.session.list_tools.assert_awaited_once_with()
    factory.session.call_tool.assert_awaited_once_with("echo", arguments={"value": "hello"})
    assert factory.calls == [
        {
            "endpoint": "https://mcp.example.com/mcp",
            "headers": {"Authorization": "Bearer resolved-token"},
            "timeout": 30.0,
        }
    ]
    secrets.get_secret_mock.assert_awaited_once_with(secret_ref="secret:mcp-token")


@pytest.mark.asyncio
async def test_mcp_is_error_maps_to_failed_tool_response(db, ctx):
    result = SimpleNamespace(
        structuredContent=None,
        content=[SimpleNamespace(type="text", text="tool failed")],
        isError=True,
    )
    factory = StubSessionFactory(result)
    _seed_artifact(db, ctx)

    response = await MCPToolAdapter(session_factory=factory).invoke(
        "mcp_tool:official:echo", {}, db=db, ctx=ctx
    )

    assert response.success is False
    assert response.error == "tool failed"


@pytest.mark.asyncio
async def test_legacy_http_transport_is_rejected(db, ctx):
    factory = StubSessionFactory(SimpleNamespace())
    _seed_artifact(db, ctx, transport="http")

    response = await MCPToolAdapter(session_factory=factory).invoke(
        "mcp_tool:official:echo", {}, db=db, ctx=ctx
    )

    assert response.success is False
    assert "streamable_http" in response.error
    assert factory.calls == []


@pytest.mark.asyncio
async def test_plaintext_mcp_credentials_are_rejected(db, ctx):
    factory = StubSessionFactory(SimpleNamespace())
    _seed_artifact(db, ctx, auth_config={"type": "bearer", "token": "plaintext"})

    response = await MCPToolAdapter(session_factory=factory).invoke(
        "mcp_tool:official:echo", {}, db=db, ctx=ctx
    )

    assert response.success is False
    assert "secret_ref" in response.error
    assert factory.calls == []
