"""Entrypoint tests for the capability registry API contract."""

from fastapi import status

from app.kernel.registry.deps import get_registry
from app.modules.integrations.mcp.domain.models import MCPServer
from app.modules.knowledge.domain.models import Knowledge
from app.modules.modelhub.domain.models import Provider, ProviderModel
from app.modules.skill.domain.models import Skill
from app.modules.workflow.domain.models import Workflow


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_capability_registry_api_lists_runtime_capabilities(client, db, ctx):
    provider = Provider(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        kind="openai",
        name="openai-provider",
        status="active",
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)

    model = ProviderModel(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        provider_id=provider.id,
        provider_kind=provider.kind,
        model_id="gpt-5",
        display_name="GPT-5",
        enabled=True,
        source="platform",
        sync_status="in_sync",
    )
    knowledge = Knowledge(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="support-kb",
        status="active",
        visibility="private",
    )
    workflow = Workflow(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="support-flow",
        status="active",
        visibility="private",
    )
    skill = Skill(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="triage-skill",
        status="active",
        visibility="private",
    )
    mcp_server = MCPServer(
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
    db.add(model)
    db.add(knowledge)
    db.add(workflow)
    db.add(skill)
    db.add(mcp_server)
    db.commit()
    db.refresh(model)
    db.refresh(knowledge)
    db.refresh(workflow)
    db.refresh(skill)
    db.refresh(mcp_server)

    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="tool:http:request",
        version="1.0.0",
        payload={"builtin": True, "metadata_json": {"adapter": "http"}},
    )
    reg.register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="tool:plugin:search:1.0.0",
        version="1.0.0",
        payload={
            "plugin": {"name": "search", "version": "1.0.0"},
            "metadata_json": {"adapter": "plugin"},
        },
    )

    response = client.get("/api/v1/capabilities", headers=_headers())
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    items = payload["items"]

    kinds = {item["kind"] for item in items}
    source_kinds = {item["source_kind"] for item in items}
    refs = {item["ref"] for item in items}

    assert {"model", "knowledge", "workflow", "skill", "tool"}.issubset(kinds)
    assert {"builtin", "native", "plugin", "mcp"}.issubset(source_kinds)
    assert "tool:http:request" in refs
    assert "tool:plugin:search:1.0.0" in refs
    assert "mcp_tool:contract-mcp:echo" in refs
    assert any(item["kind"] == "model" and item["source_kind"] == "native" for item in items)
    assert any(item["kind"] == "knowledge" and item["source_kind"] == "native" for item in items)
    assert any(item["kind"] == "workflow" and item["source_kind"] == "native" for item in items)
    assert any(item["kind"] == "skill" and item["source_kind"] == "native" for item in items)
    assert all(isinstance(item["metadata_json"], dict) for item in items)

    mcp_only = client.get("/api/v1/capabilities?source_kind=mcp", headers=_headers())
    assert mcp_only.status_code == status.HTTP_200_OK
    assert all(item["source_kind"] == "mcp" for item in mcp_only.json()["data"]["items"])

    skill_only = client.get("/api/v1/capabilities?kind=skill", headers=_headers())
    assert skill_only.status_code == status.HTTP_200_OK
    assert all(item["kind"] == "skill" for item in skill_only.json()["data"]["items"])
