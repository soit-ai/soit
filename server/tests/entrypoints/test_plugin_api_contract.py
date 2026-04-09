from fastapi import status


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
