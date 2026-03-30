"""Entrypoint tests for the skill API contract."""

from fastapi import status
from sqlalchemy import select

from app.modules.skill.domain.models import SkillPublish


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_skill_crud_version_and_publish_contract(client, db):
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

    detail_after_version = client.get(f"/api/v1/skills/{skill_id}", headers=_headers())
    assert detail_after_version.status_code == status.HTTP_200_OK
    assert detail_after_version.json()["data"]["current_version_id"] == version["id"]
    assert detail_after_version.json()["data"]["published_version_id"] is None

    versions_resp = client.get(f"/api/v1/skills/{skill_id}/versions", headers=_headers())
    assert versions_resp.status_code == status.HTTP_200_OK
    versions = versions_resp.json()["data"]["items"]
    assert len(versions) == 2
    initial_version_id = next(item["id"] for item in versions if item["version"] == 1)

    publish_resp = client.post(
        f"/api/v1/skills/{skill_id}/publish",
        json={"version_id": version["id"], "notes": "publish second"},
        headers=_headers(),
    )
    assert publish_resp.status_code == status.HTTP_200_OK
    published = publish_resp.json()["data"]
    assert published["published_version_id"] == version["id"]
    assert published["current_version_id"] == version["id"]

    rollback_resp = client.post(
        f"/api/v1/skills/{skill_id}/rollback",
        json={"version_id": initial_version_id, "notes": "rollback first"},
        headers=_headers(),
    )
    assert rollback_resp.status_code == status.HTTP_200_OK
    rolled_back = rollback_resp.json()["data"]
    assert rolled_back["published_version_id"] == initial_version_id
    assert rolled_back["current_version_id"] == version["id"]

    releases_resp = client.get(f"/api/v1/skills/{skill_id}/releases", headers=_headers())
    assert releases_resp.status_code == status.HTTP_200_OK
    releases = releases_resp.json()["data"]["items"]
    assert len(releases) == 2
    assert releases[0]["action"] == "rollback"
    assert releases[0]["from_version_id"] == version["id"]
    assert releases[0]["to_version_id"] == initial_version_id
    assert releases[0]["notes"] == "rollback first"
    assert releases[1]["action"] == "publish"
    assert releases[1]["to_version_id"] == version["id"]
    assert releases[1]["notes"] == "publish second"

    rows = db.execute(
        select(SkillPublish)
        .where(SkillPublish.skill_id == skill_id)
        .order_by(SkillPublish.created_at.desc())
    ).scalars().all()
    assert len(rows) >= 2
    latest = rows[0]
    previous = rows[1]
    assert latest.action == "rollback"
    assert latest.from_version_id == version["id"]
    assert latest.to_version_id == initial_version_id
    assert latest.rollback_of_publish_id == previous.id
    assert latest.notes == "rollback first"

    update_resp = client.put(
        f"/api/v1/skills/{skill_id}",
        json={"description": "updated", "status": "active"},
        headers=_headers(),
    )
    assert update_resp.status_code == status.HTTP_200_OK
    assert update_resp.json()["data"]["description"] == "updated"

    delete_resp = client.delete(f"/api/v1/skills/{skill_id}", headers=_headers())
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT
