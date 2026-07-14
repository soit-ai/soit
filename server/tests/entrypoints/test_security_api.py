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
