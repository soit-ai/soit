"""test_identity_auth_api

Integration tests for identity auth endpoints.
"""

import pytest
from fastapi import status


def _register_payload(suffix: str) -> dict:
    return {
        "email": f"user_{suffix}@example.com",
        "password": "Test1234!",
        "name": "Tester",
    }


@pytest.mark.asyncio
async def test_register_returns_token_and_workspace(async_client):
    """Register returns token response with workspace id."""
    payload = _register_payload("register_ok")
    response = await async_client.post("/api/v1/register", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert isinstance(data["expires_in"], int)
    assert data["workspace_id"]


@pytest.mark.asyncio
async def test_register_with_tenant_name_query_param(async_client):
    """Register accepts tenant_name query param."""
    payload = _register_payload("register_tenant")
    response = await async_client.post("/api/v1/register?tenant_name=acme", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["access_token"]


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(async_client):
    """Register rejects duplicate email."""
    payload = _register_payload("register_dup")
    response = await async_client.post("/api/v1/register", json=payload)
    assert response.status_code == status.HTTP_200_OK

    response = await async_client.post("/api/v1/register", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_register_disabled_returns_403(async_client):
    """Public registration can be disabled by operators."""
    from app.settings.settings import settings

    previous = settings.allow_public_registration
    settings.allow_public_registration = False
    try:
        response = await async_client.post("/api/v1/register", json=_register_payload("register_off"))
        assert response.status_code == status.HTTP_403_FORBIDDEN
    finally:
        settings.allow_public_registration = previous


@pytest.mark.asyncio
async def test_update_profile_rejects_overlong_name(async_client):
    """Profile name is length-bounded (schema validation): 300 chars > max_length 255."""
    response = await async_client.patch("/api/v1/me", json={"name": "n" * 300})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_login_success_and_failure(async_client):
    """Login succeeds for valid credentials and fails for invalid password."""
    payload = _register_payload("login_ok")
    response = await async_client.post("/api/v1/register", json=payload)
    assert response.status_code == status.HTTP_200_OK

    login_ok = await async_client.post(
        "/api/v1/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_ok.status_code == status.HTTP_200_OK
    data = login_ok.json()["data"]
    assert data["access_token"]
    assert data["token_type"] == "bearer"

    login_bad = await async_client.post(
        "/api/v1/login",
        json={"email": payload["email"], "password": "WrongPassword!"},
    )
    assert login_bad.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_workspace_returns_metadata_json(async_client, async_db, ctx):
    """Workspace responses expose metadata_json as metadata."""
    from app.modules.identity.domain.models import Workspace

    workspace = Workspace(
        id=ctx.workspace_id,
        tenant_id=ctx.tenant_id,
        name="Test Workspace",
        metadata_json={"control_surface": "phase1"},
    )
    async_db.add(workspace)
    await async_db.commit()

    response = await async_client.get(f"/api/v1/workspaces/{workspace.id}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["id"] == workspace.id
    assert data["metadata"] == {"control_surface": "phase1"}
