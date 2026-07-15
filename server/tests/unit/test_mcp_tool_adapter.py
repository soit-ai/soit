"""Basic MCP tool adapter behavior."""

import pytest

from app.adapters.tools.mcp import MCPToolAdapter, parse_mcp_tool_ref


def test_parse_valid_mcp_tool_ref():
    assert parse_mcp_tool_ref("mcp_tool:server:echo") == ("server", "echo")


@pytest.mark.parametrize("tool_ref", ["tool:server:echo", "mcp_tool:server", "mcp_tool::echo"])
def test_parse_rejects_invalid_mcp_tool_ref(tool_ref):
    with pytest.raises(ValueError, match="Invalid MCP tool ref"):
        parse_mcp_tool_ref(tool_ref)


@pytest.mark.asyncio
async def test_invoke_requires_database_and_context():
    result = await MCPToolAdapter().invoke("mcp_tool:server:echo", {})
    assert result.success is False
    assert result.error == "MCP tool invocation requires db and ctx"
