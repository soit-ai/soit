"""Entrypoint tests for the Agent capability catalog API contract."""

from fastapi import status

from app.kernel.registry.deps import get_registry
from app.modules.knowledge.domain.models import Knowledge
from app.modules.modelhub.domain.models import Provider, ProviderModel
from app.modules.plugin.domain.models import (
    Plugin,
    PluginInstallation,
    PluginInstalledArtifact,
    PluginVersion,
)
from app.modules.workflow.domain.models import Workflow


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_agent_capability_catalog_api_lists_runtime_capabilities(client, db, ctx):
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
        status="active",
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
    plugin = Plugin(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="workspace-capabilities",
        version="1.0.0",
        publisher="workspace",
        plugin_type="mixed",
        status="active",
        description="Workspace capability plugin",
        spec_json={"name": "workspace-capabilities", "publisher": "workspace", "version": "1.0.0"},
        manifest_json={},
        publish_status="published",
    )
    db.add(model)
    db.add(knowledge)
    db.add(workflow)
    db.add(plugin)
    db.commit()
    db.refresh(model)
    db.refresh(knowledge)
    db.refresh(workflow)
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
        artifact_summary_json={"skills": ["skill:triage-skill"], "mcp_servers": ["mcp_server:contract-mcp"]},
    )
    db.add(plugin_version)
    db.commit()
    db.refresh(plugin_version)
    plugin.current_version_id = plugin_version.id
    plugin.published_version_id = plugin_version.id
    db.add(plugin)
    db.commit()

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
            artifact_kind="skill",
            artifact_ref="skill:triage-skill",
            artifact_id="skill:triage-skill",
            artifact_version_id=None,
            enabled=True,
            state="enabled",
            metadata_json={"skill": {"name": "triage-skill", "category": "support"}},
        )
    )
    db.add(
        PluginInstalledArtifact(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            plugin_id=plugin.id,
            plugin_version_id=plugin_version.id,
            installation_id=installation.id,
            artifact_kind="mcp_server",
            artifact_ref="mcp_server:contract-mcp",
            artifact_id="mcp_server:contract-mcp",
            artifact_version_id=None,
            enabled=True,
            state="enabled",
            metadata_json={
                "mcp_server": {
                    "name": "contract-mcp",
                    "description": "MCP contract",
                    "transport": "http",
                    "endpoint": "https://mcp.example.test",
                    "capabilities_json": {"tools": [{"name": "echo", "description": "echo tool"}]},
                }
            },
        )
    )
    db.commit()

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

    response = client.get("/api/v1/agents/capabilities", headers=_headers())
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    items = payload["items"]

    kinds = {item["kind"] for item in items}
    source_kinds = {item["source_kind"] for item in items}
    refs = {item["ref"] for item in items}

    assert {"model", "knowledge", "workflow", "skill", "tool"}.issubset(kinds)
    assert {"builtin", "native", "plugin"}.issubset(source_kinds)
    assert "tool:http:request" in refs
    assert "tool:plugin:search:1.0.0" in refs
    assert "mcp_tool:contract-mcp:echo" in refs
    assert "skill:triage-skill" in refs
    assert any(item["kind"] == "model" and item["source_kind"] == "native" for item in items)
    assert any(item["kind"] == "knowledge" and item["source_kind"] == "native" for item in items)
    assert any(item["kind"] == "workflow" and item["source_kind"] == "native" for item in items)
    assert any(item["kind"] == "skill" and item["source_kind"] == "plugin" for item in items)
    assert all(isinstance(item["metadata_json"], dict) for item in items)

    plugin_only = client.get("/api/v1/agents/capabilities?source_kind=plugin", headers=_headers())
    assert plugin_only.status_code == status.HTTP_200_OK
    assert "mcp_tool:contract-mcp:echo" in {item["ref"] for item in plugin_only.json()["data"]["items"]}

    skill_only = client.get("/api/v1/agents/capabilities?kind=skill", headers=_headers())
    assert skill_only.status_code == status.HTTP_200_OK
    assert all(item["kind"] == "skill" for item in skill_only.json()["data"]["items"])


def test_agent_capability_catalog_api_projects_plugin_exported_tools_as_tools(client, ctx):
    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="tool:http:plugin_search",
        version="registry-cache",
        payload={
            "tool_spec": {
                "name": "plugin_search",
                "description": "Search through an installed plugin.",
                "input_schema": {"type": "object", "properties": {}},
            },
            "plugin": {"name": "search", "version": "2.3.4"},
            "metadata_json": {"adapter": "plugin"},
        },
    )

    response = client.get("/api/v1/agents/capabilities?kind=tool", headers=_headers())
    assert response.status_code == status.HTTP_200_OK
    items = response.json()["data"]["items"]
    plugin_tool = next(item for item in items if item["ref"] == "tool:http:plugin_search")

    assert plugin_tool["kind"] == "tool"
    assert plugin_tool["source_kind"] == "plugin"
    assert plugin_tool["source_id"] == "search"
    assert plugin_tool["source_version"] == "2.3.4"
    assert plugin_tool["metadata_json"]["plugin"] == {"name": "search", "version": "2.3.4"}
