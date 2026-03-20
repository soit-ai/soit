"""Entrypoint tests for the skill API contract."""

from fastapi import status


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_skill_crud_version_and_publish_contract(client):
    create_resp = client.post(
        "/api/v1/skills",
        json={
            "name": "contract-skill",
            "description": "Skill contract",
            "category": "business",
            "visibility": "workspace",
            "metadata_json": {"owner": "qa"},
            "spec_json": {"steps": [{"type": "tool", "ref": "tool:test:echo"}]},
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    skill = create_resp.json()["data"]
    skill_id = skill["id"]
    assert skill_id.startswith("skl_")
    assert skill["name"] == "contract-skill"
    assert skill["current_version_id"].startswith("sklv_")

    list_resp = client.get("/api/v1/skills", headers=_headers())
    assert list_resp.status_code == status.HTTP_200_OK
    assert any(item["id"] == skill_id for item in list_resp.json()["data"]["items"])

    detail_resp = client.get(f"/api/v1/skills/{skill_id}", headers=_headers())
    assert detail_resp.status_code == status.HTTP_200_OK
    assert detail_resp.json()["data"]["id"] == skill_id

    version_resp = client.post(
        f"/api/v1/skills/{skill_id}/versions",
        json={"spec_json": {"steps": [{"type": "workflow", "ref": "wf:test"}]}},
        headers=_headers(),
    )
    assert version_resp.status_code == status.HTTP_201_CREATED
    version = version_resp.json()["data"]
    assert version["skill_id"] == skill_id
    assert version["version"] == 2

    versions_resp = client.get(f"/api/v1/skills/{skill_id}/versions", headers=_headers())
    assert versions_resp.status_code == status.HTTP_200_OK
    assert len(versions_resp.json()["data"]["items"]) == 2

    publish_resp = client.post(
        f"/api/v1/skills/{skill_id}/publish",
        json={"version_id": version["id"]},
        headers=_headers(),
    )
    assert publish_resp.status_code == status.HTTP_200_OK
    published = publish_resp.json()["data"]
    assert published["published_version_id"] == version["id"]

    update_resp = client.put(
        f"/api/v1/skills/{skill_id}",
        json={"description": "updated", "status": "active"},
        headers=_headers(),
    )
    assert update_resp.status_code == status.HTTP_200_OK
    assert update_resp.json()["data"]["description"] == "updated"

    delete_resp = client.delete(f"/api/v1/skills/{skill_id}", headers=_headers())
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT
