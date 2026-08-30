"""Entrypoint tests for Security API."""

from fastapi import status

from app.modules.identity.domain.models import Tenant, Workspace


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def _seed_workspace(db) -> None:
    tenant = Tenant(id="test-tenant", name="Test Tenant", plan="free")
    workspace = Workspace(
        id="test-workspace",
        tenant_id=tenant.id,
        name="Test Workspace",
    )
    db.add(tenant)
    db.add(workspace)
    db.commit()


def test_security_api_updates_workspace_egress_policy_limits_and_audits(client, db):
    _seed_workspace(db)

    egress_response = client.put(
        "/api/v1/security/egress/workspace",
        headers=_headers(),
        json={
            "allowlist": ["api.example.com", "*.trusted.internal"],
            "blocklist": ["*.blocked.example"],
        },
    )
    assert egress_response.status_code == status.HTTP_200_OK
    assert egress_response.json()["data"] == {
        "scope": "workspace",
        "allowlist": ["api.example.com", "*.trusted.internal"],
        "blocklist": ["*.blocked.example"],
    }

    get_egress_response = client.get("/api/v1/security/egress/workspace", headers=_headers())
    assert get_egress_response.status_code == status.HTTP_200_OK
    assert get_egress_response.json()["data"]["allowlist"] == ["api.example.com", "*.trusted.internal"]

    audits_response = client.get(
        "/api/v1/security/egress/audits?scope=workspace&page_size=10",
        headers=_headers(),
    )
    assert audits_response.status_code == status.HTTP_200_OK
    audits = audits_response.json()["data"]["items"]
    assert len(audits) == 1
    assert audits[0]["scope"] == "workspace"
    assert audits[0]["workspace_id"] == "test-workspace"
    assert audits[0]["created_by"] == "test-user"
    assert audits[0]["allowlist"] == ["api.example.com", "*.trusted.internal"]

    limits_response = client.put(
        "/api/v1/security/limits/workspace",
        headers=_headers(),
        json={
            "llm_rate_limit_per_minute": 60,
            "tool_rate_limit_per_minute": 120,
            "llm_daily_quota": 1000,
            "tool_daily_quota": 2000,
        },
    )
    assert limits_response.status_code == status.HTTP_200_OK
    assert limits_response.json()["data"] == {
        "scope": "workspace",
        "llm_rate_limit_per_minute": 60,
        "tool_rate_limit_per_minute": 120,
        "llm_daily_quota": 1000,
        "tool_daily_quota": 2000,
    }


def test_security_api_records_policy_revisions_and_restores_one(client, db):
    """The console has to be able to show what a policy was, and put it back."""
    _seed_workspace(db)

    client.put(
        "/api/v1/security/egress/workspace",
        headers=_headers(),
        json={"allowlist": ["safe.example.com"], "blocklist": []},
    )
    client.put(
        "/api/v1/security/egress/workspace",
        headers=_headers(),
        json={"allowlist": ["*"], "blocklist": []},
    )

    revisions_response = client.get(
        "/api/v1/security/policies/revisions?scope=workspace",
        headers=_headers(),
    )
    assert revisions_response.status_code == status.HTTP_200_OK
    revisions = revisions_response.json()["data"]["items"]
    assert [row["revision"] for row in revisions] == [2, 1]
    assert revisions[0]["active"] is True
    assert revisions[1]["active"] is False

    bundle_response = client.get(
        "/api/v1/security/policies/bundle?scope=workspace",
        headers=_headers(),
    )
    bundle = bundle_response.json()["data"]
    assert bundle["revision"] == 2
    assert bundle["bundle_id"] == revisions[0]["bundle_id"]
    assert bundle["document"]["egress_allowlist"] == ["*"]

    diff_response = client.get(
        "/api/v1/security/policies/revisions/diff"
        "?scope=workspace&from_revision=1&to_revision=2",
        headers=_headers(),
    )
    diff = diff_response.json()["data"]
    assert [change["field"] for change in diff["changes"]] == ["egress_allowlist"]
    assert diff["changes"][0]["after"] == ["*"]

    rollback_response = client.post(
        f"/api/v1/security/policies/revisions/{revisions[1]['id']}/rollback",
        headers=_headers(),
        json={"note": "Too permissive"},
    )
    assert rollback_response.status_code == status.HTTP_200_OK
    restored = rollback_response.json()["data"]
    assert restored["revision"] == 3
    assert restored["document"]["egress_allowlist"] == ["safe.example.com"]

    current = client.get("/api/v1/security/egress/workspace", headers=_headers())
    assert current.json()["data"]["allowlist"] == ["safe.example.com"]


def test_security_api_reports_a_bundle_before_anything_was_saved(client, db):
    """A fresh install still has a policy, so it still has an identifier."""
    _seed_workspace(db)

    response = client.get(
        "/api/v1/security/policies/bundle?scope=workspace",
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_200_OK
    bundle = response.json()["data"]
    assert bundle["bundle_id"].startswith("pb_")
    assert bundle["revision"] == 0
    assert bundle["activated_at"] is None
