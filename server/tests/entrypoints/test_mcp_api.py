"""Entrypoint tests for the MCP API contract."""

from fastapi import status


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_mcp_server_crud_and_catalog_contract(client):
    create_resp = client.post(
        "/api/v1/mcp/servers",
        json={
            "name": "contract-mcp",
            "description": "MCP contract",
            "transport": "http",
            "endpoint": "https://mcp.example.test",
            "enabled": True,
            "capabilities_json": {
                "tools": [{"name": "echo", "description": "echo tool"}],
                "resources": [{"name": "kb", "uri": "kb://test"}],
                "templates": [{"name": "support-reply"}],
            },
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    server = create_resp.json()["data"]
    server_id = server["id"]
    assert server_id.startswith("mcp_")

    list_resp = client.get("/api/v1/mcp/servers", headers=_headers())
    assert list_resp.status_code == status.HTTP_200_OK
    assert any(item["id"] == server_id for item in list_resp.json()["data"]["items"])

    detail_resp = client.get(f"/api/v1/mcp/servers/{server_id}", headers=_headers())
    assert detail_resp.status_code == status.HTTP_200_OK
    assert detail_resp.json()["data"]["endpoint"] == "https://mcp.example.test"

    server_catalog_resp = client.get(f"/api/v1/mcp/servers/{server_id}/catalog", headers=_headers())
    assert server_catalog_resp.status_code == status.HTTP_200_OK
    server_catalog = server_catalog_resp.json()["data"]
    assert server_catalog["tools"][0]["name"] == "echo"

    catalog_resp = client.get("/api/v1/mcp/catalog", headers=_headers())
    assert catalog_resp.status_code == status.HTTP_200_OK
    catalog = catalog_resp.json()["data"]
    assert catalog["tools"][0]["server_id"] == server_id

    update_resp = client.put(
        f"/api/v1/mcp/servers/{server_id}",
        json={"description": "updated", "enabled": False, "status": "disabled"},
        headers=_headers(),
    )
    assert update_resp.status_code == status.HTTP_200_OK
    updated = update_resp.json()["data"]
    assert updated["description"] == "updated"
    assert updated["enabled"] is False

    delete_resp = client.delete(f"/api/v1/mcp/servers/{server_id}", headers=_headers())
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT
