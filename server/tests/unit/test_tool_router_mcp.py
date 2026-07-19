"""Tests for MCP routing in RegistryToolRouterPort."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.adapters.tools.mcp import MCPToolAdapter
from app.adapters.tools.router import RegistryToolRouterPort
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.tools.interface import ToolResponse
from app.kernel.ports.tools.policy import ToolPolicyGateway
from app.kernel.runtime.db.models.runs import RunStepToolCall
from app.kernel.runtime.runs.writer import TraceWriter


def _make_ctx():
    return RequestContext(tenant_id="t1", workspace_id="w1", user_id="u1")


@pytest.mark.asyncio
async def test_mcp_tool_ref_routes_to_mcp_adapter():
    """mcp_tool:* refs are routed directly to MCPToolAdapter."""
    mock_mcp = AsyncMock(spec=MCPToolAdapter)
    mock_mcp.invoke.return_value = ToolResponse(result={"echo": "hi"}, success=True)

    router = RegistryToolRouterPort(mcp_adapter=mock_mcp)
    ctx = _make_ctx()

    result = await router.invoke(
        "mcp_tool:my-server:echo",
        {"value": "hi"},
        ctx=ctx,
        db=MagicMock(),
    )

    assert result.success is True
    assert result.result == {"echo": "hi"}
    mock_mcp.invoke.assert_called_once()
    call_args = mock_mcp.invoke.call_args
    assert call_args[0][0] == "mcp_tool:my-server:echo"
    assert call_args[0][1] == {"value": "hi"}


@pytest.mark.asyncio
async def test_non_mcp_ref_does_not_route_to_mcp():
    """Regular tool refs should not go to the MCP adapter."""
    mock_mcp = AsyncMock(spec=MCPToolAdapter)
    router = RegistryToolRouterPort(mcp_adapter=mock_mcp)

    # This will fall through to the HTTP port since there's no registry entry
    await router.invoke(
        "tool:test:echo",
        {"url": "https://example.com", "method": "GET"},
    )

    mock_mcp.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_default_mcp_adapter_is_created():
    """Router creates a default MCPToolAdapter if none provided."""
    router = RegistryToolRouterPort()
    assert isinstance(router.mcp_adapter, MCPToolAdapter)


@pytest.mark.asyncio
async def test_mcp_tool_route_uses_the_governed_runtime_ledger(db, ctx):
    mock_mcp = AsyncMock(spec=MCPToolAdapter)
    mock_mcp.invoke.return_value = ToolResponse(result={"echo": "hi"}, success=True)
    writer = TraceWriter(db, ctx)
    run = writer.create_run(mode="agent", kind="agent")
    gateway = ToolPolicyGateway(
        gateway=RegistryToolRouterPort(mcp_adapter=mock_mcp),
        ctx=ctx,
        trace_writer=writer,
        enable_egress_check=False,
    )

    response = await gateway.invoke(
        "mcp_tool:my-server:echo",
        {"value": "hi"},
        ctx=ctx,
        db=db,
        run_id=run.id,
        tool_call_id="call-mcp-echo",
        idempotency_key=f"tool:{run.id}:call-mcp-echo",
    )

    record = db.execute(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).scalars().one()
    assert response.success is True
    assert record.tool_call_id == "call-mcp-echo"
    assert record.tool_ref == "mcp_tool:my-server:echo"
    assert record.status == "succeeded"
