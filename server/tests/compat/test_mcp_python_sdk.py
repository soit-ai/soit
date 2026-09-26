"""The official MCP Python SDK client works against SOIT's /mcp unchanged.

Claude Code, Cursor and other MCP clients speak the same streamable HTTP
transport. Driving the SDK's own client, not raw JSON-RPC, catches a change
that breaks what a real client sends or parses: the initialize handshake, the
stateless JSON answers, tool listing and results.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.api.mcp.router import mcp_caller
from app.main import app
from app.wiring import get_container

# The fixture binds the test database the app reads through.
pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("async_client")]


@asynccontextmanager
async def _session(ctx) -> AsyncIterator[ClientSession]:
    """An SDK session against the app, as a client would open one against SOIT.

    Opened inside the test itself: the SDK's task groups must be left in the
    task that entered them. The MCP caller is the test caller in place of API
    key auth, while the SDK still sends its bearer header.
    """
    get_container()
    app.dependency_overrides[mcp_caller] = lambda: ctx
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            headers={"Authorization": "Bearer sk-compat-not-a-real-key"},
        ) as http:
            async with streamable_http_client("http://testserver/mcp", http_client=http) as (read, write, _):
                async with ClientSession(read, write) as client:
                    yield client
    finally:
        app.dependency_overrides.pop(mcp_caller, None)


async def test_the_sdk_initializes_against_a_stateless_server(ctx) -> None:
    async with _session(ctx) as session:
        result = await session.initialize()

    assert result.serverInfo.name == "soit"
    assert result.capabilities.tools is not None


async def test_the_sdk_lists_and_calls_tools(ctx) -> None:
    async with _session(ctx) as session:
        await session.initialize()
        tools = {tool.name: tool for tool in (await session.list_tools()).tools}
        result = await session.call_tool("function_random_int", {"min": 3, "max": 3})

    assert "function_time_now" in tools
    assert tools["function_random_int"].inputSchema["required"] == ["min", "max"]
    assert result.isError is False
    assert result.structuredContent == {"value": 3}
    assert (result.meta or {}).get("ai.soit/run_id", "").startswith("run_")


async def test_the_sdk_sees_a_refused_call_as_a_tool_error(ctx) -> None:
    async with _session(ctx) as session:
        await session.initialize()
        result = await session.call_tool("function_random_int", {"min": 1})

    assert result.isError is True
    assert "'max' is a required property" in result.content[0].text
