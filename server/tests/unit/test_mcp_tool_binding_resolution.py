"""Unit tests for MCP tool binding resolution."""

import pytest

from app.modules.integrations.mcp.application.service import MCPService
from app.modules.integrations.mcp.domain.models import MCPServer


@pytest.mark.asyncio
async def test_resolve_tool_refs_accepts_mcp_tool_refs(db, ctx):
    server = MCPServer(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="contract-mcp",
        description="MCP contract",
        transport="http",
        endpoint="https://mcp.example.test",
        enabled=True,
        status="active",
        capabilities_json={
            "tools": [{"name": "echo", "description": "echo tool"}],
        },
    )
    db.add(server)
    db.commit()
    db.refresh(server)

    service = MCPService(db=db, ctx=ctx)

    resolved = await service.resolve_tool_refs(tool_refs=["mcp_tool:contract-mcp:echo"])

    assert "mcp_tool:contract-mcp:echo" in resolved
    assert resolved["mcp_tool:contract-mcp:echo"]["binding_type"] == "mcp_tool"
    assert resolved["mcp_tool:contract-mcp:echo"]["binding_ref"] == "mcp_tool:contract-mcp:echo"
