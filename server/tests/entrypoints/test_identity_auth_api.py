"""test_identity_auth_api

Integration tests for identity auth endpoints.
"""

from fastapi import status


def _register_payload(suffix: str) -> dict:
    return {
        "email": f"user_{suffix}@example.com",
        "password": "Test1234!",
        "name": "Tester",
    }


def test_register_returns_token_and_workspace(client):
    """Register returns token response with workspace id."""
    payload = _register_payload("register_ok")
    response = client.post("/api/v1/register", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert isinstance(data["expires_in"], int)
    assert data["workspace_id"]


def test_register_with_tenant_name_query_param(client):
    """Register accepts tenant_name query param."""
    payload = _register_payload("register_tenant")
    response = client.post("/api/v1/register?tenant_name=acme", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["access_token"]


def test_register_rejects_duplicate_email(client):
    """Register rejects duplicate email."""
    payload = _register_payload("register_dup")
    response = client.post("/api/v1/register", json=payload)
    assert response.status_code == status.HTTP_200_OK

    response = client.post("/api/v1/register", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_login_success_and_failure(client):
    """Login succeeds for valid credentials and fails for invalid password."""
    payload = _register_payload("login_ok")
    response = client.post("/api/v1/register", json=payload)
    assert response.status_code == status.HTTP_200_OK

    login_ok = client.post(
        "/api/v1/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_ok.status_code == status.HTTP_200_OK
    data = login_ok.json()["data"]
    assert data["access_token"]
    assert data["token_type"] == "bearer"

    login_bad = client.post(
        "/api/v1/login",
        json={"email": payload["email"], "password": "WrongPassword!"},
    )
    assert login_bad.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_workspace_returns_metadata_json(client, db, ctx):
    """Workspace responses expose metadata_json as metadata."""
    from app.modules.identity.domain.models import Workspace

    workspace = Workspace(
        id=ctx.workspace_id,
        tenant_id=ctx.tenant_id,
        name="Test Workspace",
        metadata_json={"control_surface": "phase1"},
    )
    db.add(workspace)
    db.commit()

    response = client.get(f"/api/v1/workspaces/{workspace.id}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["id"] == workspace.id
    assert data["metadata"] == {"control_surface": "phase1"}
