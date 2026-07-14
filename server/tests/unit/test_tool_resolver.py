"""Tests for ToolResolver."""

import pytest

from app.adapters.tools.router import RegistryToolRouterPort
from app.kernel.ports.llm.interface import ToolDefinition
from app.kernel.registry.deps import get_registry
from app.kernel.runtime.tools.resolver import ToolResolver


@pytest.fixture
def tool_router():
    return RegistryToolRouterPort()


@pytest.fixture
def resolver(tool_router):
    return ToolResolver(tool_port=tool_router)


@pytest.mark.asyncio
async def test_resolve_empty_refs(resolver, ctx):
    result = await resolver.resolve(None, ctx)
    assert result == []


@pytest.mark.asyncio
async def test_resolve_empty_list(resolver, ctx):
    result = await resolver.resolve([], ctx)
    assert result == []


@pytest.mark.asyncio
async def test_resolve_builtin_tool(resolver, ctx):
    result = await resolver.resolve(["tool:function:time_now"], ctx)
    assert len(result) == 1
    assert isinstance(result[0], ToolDefinition)
    assert result[0].name == "tool:function:time_now"
    assert "time_now" in result[0].description or result[0].description == "time_now"
    assert result[0].parameters["type"] == "object"


@pytest.mark.asyncio
async def test_resolve_registered_tool(resolver, ctx):
    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="tool:custom:my_tool",
        version="1.0.0",
        payload={
            "tool_spec": {
                "name": "my_tool",
                "description": "A custom tool",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            }
        },
    )
    result = await resolver.resolve(["tool:custom:my_tool"], ctx)
    assert len(result) == 1
    assert result[0].name == "tool:custom:my_tool"
    assert result[0].description == "A custom tool"


@pytest.mark.asyncio
async def test_resolve_unknown_tool_skipped(resolver, ctx):
    result = await resolver.resolve(["tool:nonexistent:foo"], ctx)
    assert result == []


@pytest.mark.asyncio
async def test_resolve_multiple_tools(resolver, ctx):
    result = await resolver.resolve(
        ["tool:function:time_now", "tool:function:random_int"],
        ctx,
    )
    assert len(result) == 2
    names = {td.name for td in result}
    assert "tool:function:time_now" in names
    assert "tool:function:random_int" in names


@pytest.mark.asyncio
async def test_resolve_registered_plugin_tool_ref(resolver, ctx):
    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="tool:http:plugin_search",
        version="1.0.0",
        payload={
            "tool_spec": {
                "name": "plugin_search",
                "description": "Search through an installed plugin.",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
            "plugin": {"name": "soit:search", "version": "1.0.0"},
        },
    )

    result = await resolver.resolve(["tool:http:plugin_search"], ctx)

    assert len(result) == 1
    assert result[0].name == "tool:http:plugin_search"
    assert result[0].description == "Search through an installed plugin."


@pytest.mark.asyncio
async def test_resolve_mcp_tool_ref_fallback(resolver, ctx):
    """mcp_tool: refs get a basic ToolDefinition even without mcp_tool_resolver."""
    result = await resolver.resolve(["mcp_tool:my-server:echo"], ctx)
    assert len(result) == 1
    assert result[0].name == "mcp_tool:my-server:echo"
    assert "echo" in result[0].description
    assert result[0].parameters == {"type": "object"}


@pytest.mark.asyncio
async def test_resolve_mcp_tool_ref_with_resolver(ctx):
    """mcp_tool: refs use mcp_tool_resolver when provided."""
    expected_def = ToolDefinition(
        name="mcp_tool:my-server:echo",
        description="Echo tool from MCP",
        parameters={"type": "object", "properties": {"value": {"type": "string"}}},
    )

    async def mock_resolver(_ref, _ctx):
        return expected_def

    resolver = ToolResolver(
        tool_port=RegistryToolRouterPort(),
        mcp_tool_resolver=mock_resolver,
    )
    result = await resolver.resolve(["mcp_tool:my-server:echo"], ctx)
    assert len(result) == 1
    assert result[0] is expected_def
