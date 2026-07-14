"""Tests for MCPToolAdapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.tools.mcp import MCPToolAdapter, parse_mcp_tool_ref
from app.kernel.contracts.context import RequestContext
from app.modules.plugin.domain.models import (
    Plugin,
    PluginInstallation,
    PluginInstalledArtifact,
    PluginVersion,
)


def _make_ctx():
    return RequestContext(tenant_id="t1", workspace_id="w1", user_id="u1")


def _seed_mcp_artifact(db, ctx, *, name="my-server", enabled=True, auth_config_json=None):
    plugin = Plugin(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name=f"{name}-plugin",
        version="1.0.0",
        publisher="workspace",
        plugin_type="mcp",
        status="active",
        spec_json={"name": f"{name}-plugin", "publisher": "workspace", "version": "1.0.0"},
        manifest_json={},
        publish_status="published",
    )
    db.add(plugin)
    db.commit()
    db.refresh(plugin)

    plugin_version = PluginVersion(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        plugin_id=plugin.id,
        version=1,
        package_version="1.0.0",
        status="published",
        spec_json=plugin.spec_json,
        manifest_json={},
    )
    db.add(plugin_version)
    db.commit()
    db.refresh(plugin_version)

    installation = PluginInstallation(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        plugin_id=plugin.id,
        plugin_version_id=plugin_version.id,
        enabled=enabled,
        state="installed" if enabled else "disabled",
    )
    db.add(installation)
    db.commit()
    db.refresh(installation)

    db.add(
        PluginInstalledArtifact(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            plugin_id=plugin.id,
            plugin_version_id=plugin_version.id,
            installation_id=installation.id,
            artifact_kind="mcp_server",
            artifact_ref=f"mcp_server:{name}",
            artifact_id=f"mcp_server:{name}",
            enabled=enabled,
            state="enabled" if enabled else "disabled",
            metadata_json={
                "mcp_server": {
                    "name": name,
                    "endpoint": "https://mcp.example.com/rpc",
                    "transport": "http",
                    "auth_config_json": auth_config_json or {},
                    "capabilities_json": {"tools": [{"name": "echo"}]},
                }
            },
        )
    )
    db.commit()


class TestParseMcpToolRef:
    def test_valid_ref(self):
        server, tool = parse_mcp_tool_ref("mcp_tool:my-server:echo")
        assert server == "my-server"
        assert tool == "echo"

    def test_invalid_prefix(self):
        with pytest.raises(ValueError, match="Invalid MCP tool ref"):
            parse_mcp_tool_ref("tool:test:echo")

    def test_too_few_parts(self):
        with pytest.raises(ValueError, match="Invalid MCP tool ref"):
            parse_mcp_tool_ref("mcp_tool:only")


@pytest.mark.asyncio
async def test_invoke_requires_db_and_ctx():
    adapter = MCPToolAdapter()
    result = await adapter.invoke("mcp_tool:srv:echo", {"value": "hi"})
    assert result.success is False
    assert "requires db and ctx" in result.error


@pytest.mark.asyncio
async def test_invoke_resolves_mcp_server_from_plugin_artifact(db, ctx):
    import httpx

    plugin = Plugin(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="github-tools",
        version="1.0.0",
        publisher="workspace",
        plugin_type="mcp",
        status="active",
        spec_json={"name": "github-tools", "publisher": "workspace", "version": "1.0.0"},
        manifest_json={},
        publish_status="published",
    )
    db.add(plugin)
    db.commit()
    db.refresh(plugin)

    plugin_version = PluginVersion(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        plugin_id=plugin.id,
        version=1,
        package_version="1.0.0",
        status="published",
        spec_json=plugin.spec_json,
        manifest_json={},
    )
    db.add(plugin_version)
    db.commit()
    db.refresh(plugin_version)

    installation = PluginInstallation(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        plugin_id=plugin.id,
        plugin_version_id=plugin_version.id,
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
            plugin_version_id=plugin_version.id,
            installation_id=installation.id,
            artifact_kind="mcp_server",
            artifact_ref="mcp_server:my-server",
            artifact_id="mcp_server:my-server",
            enabled=True,
            state="enabled",
            metadata_json={
                "mcp_server": {
                    "name": "my-server",
                    "endpoint": "https://mcp.example.com/rpc",
                    "transport": "http",
                    "auth_config_json": {"type": "bearer", "token": "secret-token"},
                    "capabilities_json": {"tools": [{"name": "echo"}]},
                }
            },
        )
    )
    db.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"jsonrpc": "2.0", "result": {"output": "hello"}, "id": "1"}
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    adapter = MCPToolAdapter(client=mock_client)
    result = await adapter.invoke("mcp_tool:my-server:echo", {"value": "hi"}, db=db, ctx=ctx)

    assert result.success is True
    assert result.result == {"output": "hello"}
    assert result.metadata["server_name"] == "my-server"
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://mcp.example.com/rpc"
    assert call_args[1]["headers"]["Authorization"] == "Bearer secret-token"


@pytest.mark.asyncio
async def test_invoke_server_not_found(db, ctx):
    adapter = MCPToolAdapter()
    result = await adapter.invoke("mcp_tool:missing:echo", {"value": "hi"}, db=db, ctx=ctx)

    assert result.success is False
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_invoke_server_disabled(db, ctx):
    adapter = MCPToolAdapter()
    _seed_mcp_artifact(db, ctx, enabled=False)
    result = await adapter.invoke("mcp_tool:my-server:echo", {"value": "hi"}, db=db, ctx=ctx)

    assert result.success is False
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_invoke_success(httpx_mock_or_manual, db, ctx):
    """Test successful MCP tool invocation with mocked HTTP."""
    _ = httpx_mock_or_manual
    import httpx

    # Create a mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"jsonrpc": "2.0", "result": {"output": "hello"}, "id": "1"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    adapter = MCPToolAdapter(client=mock_client)
    _seed_mcp_artifact(db, ctx)
    result = await adapter.invoke("mcp_tool:my-server:echo", {"value": "hi"}, db=db, ctx=ctx)

    assert result.success is True
    assert result.result == {"output": "hello"}
    assert result.metadata["server_name"] == "my-server"
    assert result.metadata["tool_name"] == "echo"

    # Verify the request
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://mcp.example.com/rpc"
    payload = call_args[1]["json"]
    assert payload["method"] == "tools/call"
    assert payload["params"]["name"] == "echo"
    assert payload["params"]["arguments"] == {"value": "hi"}


@pytest.mark.asyncio
async def test_invoke_with_bearer_auth(db, ctx):
    """Test that bearer auth headers are included."""
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"jsonrpc": "2.0", "result": "ok", "id": "1"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    adapter = MCPToolAdapter(client=mock_client)
    _seed_mcp_artifact(db, ctx, auth_config_json={"type": "bearer", "token": "secret-token"})
    await adapter.invoke("mcp_tool:my-server:echo", {}, db=db, ctx=ctx)

    call_args = mock_client.post.call_args
    headers = call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer secret-token"


@pytest.mark.asyncio
async def test_invoke_jsonrpc_error(db, ctx):
    """Test handling of JSON-RPC error responses."""
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "error": {"code": -32601, "message": "Tool not found"},
        "id": "1",
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    adapter = MCPToolAdapter(client=mock_client)
    _seed_mcp_artifact(db, ctx)
    result = await adapter.invoke("mcp_tool:my-server:echo", {}, db=db, ctx=ctx)

    assert result.success is False
    assert "Tool not found" in result.error


@pytest.mark.asyncio
async def test_invoke_mcp_content_array(db, ctx):
    """Test extraction of MCP content array format."""
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "result": {
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": "World"},
            ]
        },
        "id": "1",
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    adapter = MCPToolAdapter(client=mock_client)
    _seed_mcp_artifact(db, ctx)
    result = await adapter.invoke("mcp_tool:my-server:echo", {}, db=db, ctx=ctx)

    assert result.success is True
    assert result.result["text"] == "Hello\nWorld"


# Use a fixture marker so pytest doesn't complain about the parameter name
@pytest.fixture
def httpx_mock_or_manual():
    """Placeholder fixture - tests use manual mocking."""
    return None
