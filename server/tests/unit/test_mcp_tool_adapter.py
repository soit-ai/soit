"""Tests for MCPToolAdapter."""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch

from app.adapters.tools.mcp import MCPToolAdapter, parse_mcp_tool_ref
from app.kernel.contracts.context import RequestContext


def _make_ctx():
    return RequestContext(tenant_id="t1", workspace_id="w1", user_id="u1")


def _make_server(*, name="my-server", endpoint="https://mcp.example.com/rpc", enabled=True, status="active", auth_config_json=None):
    return SimpleNamespace(
        id="mcp_001",
        name=name,
        endpoint=endpoint,
        enabled=enabled,
        status=status,
        auth_config_json=auth_config_json or {},
        capabilities_json={"tools": [{"name": "echo"}]},
    )


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
async def test_invoke_server_not_found():
    adapter = MCPToolAdapter()
    db = MagicMock()
    ctx = _make_ctx()

    with patch("app.adapters.tools.mcp.MCPServerRepository") as MockRepo:
        repo_instance = MockRepo.return_value
        repo_instance.get_by_name.return_value = None
        repo_instance.get_by_id.return_value = None

        result = await adapter.invoke("mcp_tool:missing:echo", {"value": "hi"}, db=db, ctx=ctx)

    assert result.success is False
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_invoke_server_disabled():
    adapter = MCPToolAdapter()
    db = MagicMock()
    ctx = _make_ctx()

    with patch("app.adapters.tools.mcp.MCPServerRepository") as MockRepo:
        repo_instance = MockRepo.return_value
        repo_instance.get_by_name.return_value = _make_server(enabled=False, status="disabled")

        result = await adapter.invoke("mcp_tool:my-server:echo", {"value": "hi"}, db=db, ctx=ctx)

    assert result.success is False
    assert "not active" in result.error


@pytest.mark.asyncio
async def test_invoke_success(httpx_mock_or_manual):
    """Test successful MCP tool invocation with mocked HTTP."""
    import httpx

    # Create a mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"jsonrpc": "2.0", "result": {"output": "hello"}, "id": "1"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    adapter = MCPToolAdapter(client=mock_client)
    db = MagicMock()
    ctx = _make_ctx()

    with patch("app.adapters.tools.mcp.MCPServerRepository") as MockRepo:
        repo_instance = MockRepo.return_value
        repo_instance.get_by_name.return_value = _make_server()

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
async def test_invoke_with_bearer_auth():
    """Test that bearer auth headers are included."""
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"jsonrpc": "2.0", "result": "ok", "id": "1"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    adapter = MCPToolAdapter(client=mock_client)
    db = MagicMock()
    ctx = _make_ctx()

    server = _make_server(auth_config_json={"type": "bearer", "token": "secret-token"})
    with patch("app.adapters.tools.mcp.MCPServerRepository") as MockRepo:
        repo_instance = MockRepo.return_value
        repo_instance.get_by_name.return_value = server

        await adapter.invoke("mcp_tool:my-server:echo", {}, db=db, ctx=ctx)

    call_args = mock_client.post.call_args
    headers = call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer secret-token"


@pytest.mark.asyncio
async def test_invoke_jsonrpc_error():
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
    db = MagicMock()
    ctx = _make_ctx()

    with patch("app.adapters.tools.mcp.MCPServerRepository") as MockRepo:
        repo_instance = MockRepo.return_value
        repo_instance.get_by_name.return_value = _make_server()

        result = await adapter.invoke("mcp_tool:my-server:echo", {}, db=db, ctx=ctx)

    assert result.success is False
    assert "Tool not found" in result.error


@pytest.mark.asyncio
async def test_invoke_mcp_content_array():
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
    db = MagicMock()
    ctx = _make_ctx()

    with patch("app.adapters.tools.mcp.MCPServerRepository") as MockRepo:
        repo_instance = MockRepo.return_value
        repo_instance.get_by_name.return_value = _make_server()

        result = await adapter.invoke("mcp_tool:my-server:echo", {}, db=db, ctx=ctx)

    assert result.success is True
    assert result.result["text"] == "Hello\nWorld"


# Use a fixture marker so pytest doesn't complain about the parameter name
@pytest.fixture
def httpx_mock_or_manual():
    """Placeholder fixture - tests use manual mocking."""
    return None
