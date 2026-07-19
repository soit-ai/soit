from fastapi import status

from app.kernel.registry.deps import get_registry


def _headers() -> dict[str, str]:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_plugin_api_rejects_legacy_published_alias_and_hides_it_in_responses(client):
    create_resp = client.post(
        "/api/v1/plugins",
        json={
            "name": "plugin-contract",
            "version": "1.0.0",
            "description": "contract",
            "spec_json": {"name": "plugin-contract", "version": "1.0.0"},
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    plugin = create_resp.json()["data"]
    plugin_id = plugin["id"]
    assert "published" not in plugin
    assert plugin["publish_status"] == "draft"

    update_resp = client.put(
        f"/api/v1/plugins/{plugin_id}",
        json={"published": True},
        headers=_headers(),
    )
    assert update_resp.status_code == status.HTTP_400_BAD_REQUEST

    publish_resp = client.put(
        f"/api/v1/plugins/{plugin_id}",
        json={"publish_status": "published"},
        headers=_headers(),
    )
    assert publish_resp.status_code == status.HTTP_200_OK
    assert publish_resp.json()["data"]["publish_status"] == "published"
    assert "published" not in publish_resp.json()["data"]


def test_runtime_tools_endpoint_returns_only_registry_latest_in_deterministic_order(client):
    registry = get_registry()
    shared_ref = "tool:function:create-ticket"
    for version, tool_name in [("1.0.0.dev1", "Create ticket preview"), ("1.0.0", "Create ticket")]:
        registry.register(
            kind="tool",
            tenant_id="test-tenant",
            workspace_id="test-workspace",
            name=shared_ref,
            version=version,
            payload={
                "plugin": {"name": "tickets", "version": version},
                "tool_spec": {"name": tool_name, "description": None, "input_schema": {}},
            },
        )
    mixed_ref = "tool:function:registry-cache"
    for version, tool_name in [
        ("1.0.0", "Registry cache stable"),
        ("registry-cache", "Registry cache fallback"),
    ]:
        registry.register(
            kind="tool",
            tenant_id="test-tenant",
            workspace_id="test-workspace",
            name=mixed_ref,
            version=version,
            payload={
                "plugin": {"name": "registry", "version": version},
                "tool_spec": {"name": tool_name, "description": None, "input_schema": {}},
            },
        )
    registry.register(
        kind="tool",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        name="tool:function:audit-log",
        version="2.0.0",
        payload={
            "plugin": {"name": "audit", "version": "2.0.0"},
            "tool_spec": {"name": "Audit log", "description": None, "input_schema": {}},
        },
    )

    response = client.get("/api/v1/plugins/runtime/tools", headers=_headers())

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["tools"] == [
        {
            "tool_ref": "tool:function:audit-log",
            "version": "2.0.0",
            "plugin": {"name": "audit", "version": "2.0.0"},
            "tool_spec": {"name": "Audit log", "description": None, "input_schema": {}},
        },
        {
            "tool_ref": shared_ref,
            "version": "1.0.0",
            "plugin": {"name": "tickets", "version": "1.0.0"},
            "tool_spec": {"name": "Create ticket", "description": None, "input_schema": {}},
        },
        {
            "tool_ref": mixed_ref,
            "version": "registry-cache",
            "plugin": {"name": "registry", "version": "registry-cache"},
            "tool_spec": {
                "name": "Registry cache fallback",
                "description": None,
                "input_schema": {},
            },
        },
    ]
