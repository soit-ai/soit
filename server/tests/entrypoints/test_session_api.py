"""Entrypoint contract for the session and refresh surface.

Signing out has to mean the access token stops working, not that it expires
eventually. These drive the real routes to prove that end to end.
"""

import pytest
import pytest_asyncio
from fastapi import status


@pytest_asyncio.fixture
async def auth_client(async_db):
    """A client that really authenticates.

    The shared `client` fixture overrides context resolution so every request
    is the same synthetic user; these tests are about who the caller is and
    whether their session is still alive, so they need the real path.
    """
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.infra.db import session as db_session
    from app.infra.db.session import get_async_db
    from app.main import app
    from app.settings.settings import settings

    async def _override_get_async_db():
        yield async_db

    engine = async_db.bind
    previous_engine = db_session._async_engine
    previous_factory = db_session._AsyncSessionLocal
    db_session._async_engine = engine
    db_session._AsyncSessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    previous_ingest = getattr(settings, "knowledge_ingest_worker_enabled", False)
    previous_outbox_flag = getattr(settings, "outbox_dispatcher_enabled", False)
    settings.knowledge_ingest_worker_enabled = False
    settings.outbox_dispatcher_enabled = False
    app.dependency_overrides[get_async_db] = _override_get_async_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as test_client:
            yield test_client
    finally:
        settings.knowledge_ingest_worker_enabled = previous_ingest
        settings.outbox_dispatcher_enabled = previous_outbox_flag
        app.dependency_overrides.pop(get_async_db, None)

        db_session._async_engine = previous_engine
        db_session._AsyncSessionLocal = previous_factory


async def _register(auth_client, email: str = "sessions-api@example.com") -> dict:
    response = await auth_client.post(
        "/api/v1/register",
        json={"email": email, "password": "password123", "name": "API User"},
        params={"tenant_name": f"tenant-{email}"},
    )
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED), response.text
    return response.json()["data"]


def _auth(token: str, workspace_id: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-Workspace-Id": workspace_id}


@pytest.mark.asyncio
async def test_registration_returns_a_refresh_token(auth_client):
    payload = await _register(auth_client)

    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["expires_in"] > 0


@pytest.mark.asyncio
async def test_refresh_returns_a_new_pair_and_the_old_one_stops_working(auth_client):
    payload = await _register(auth_client, "refresh-api@example.com")

    first = await auth_client.post(
        "/api/v1/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert first.status_code == status.HTTP_200_OK
    rotated = first.json()["data"]
    assert rotated["refresh_token"] != payload["refresh_token"]

    replay = await auth_client.post(
        "/api/v1/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert replay.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_a_session_lists_itself_as_the_current_one(auth_client):
    payload = await _register(auth_client, "list-api@example.com")
    headers = _auth(payload["access_token"], payload["workspace_id"])

    response = await auth_client.get("/api/v1/me/sessions", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    sessions = response.json()["data"]
    assert len(sessions) == 1
    assert sessions[0]["current"] is True
    assert sessions[0]["status"] == "active"


@pytest.mark.asyncio
async def test_revoking_the_current_session_immediately_stops_its_token(auth_client):
    """The point of the session id in the token: a sign-out takes effect now."""
    payload = await _register(auth_client, "revoke-api@example.com")
    headers = _auth(payload["access_token"], payload["workspace_id"])
    session_id = (await auth_client.get("/api/v1/me/sessions", headers=headers)).json()["data"][0]["id"]

    revoked = await auth_client.delete(f"/api/v1/me/sessions/{session_id}", headers=headers)
    assert revoked.status_code == status.HTTP_200_OK

    after = await auth_client.get("/api/v1/me/sessions", headers=headers)
    assert after.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_signing_out_everywhere_keeps_the_calling_device_by_default(auth_client):
    payload = await _register(auth_client, "revoke-all-api@example.com")
    headers = _auth(payload["access_token"], payload["workspace_id"])
    # A second sign-in from somewhere else.
    other = await auth_client.post(
        "/api/v1/login",
        json={"email": "revoke-all-api@example.com", "password": "password123"},
    )
    assert other.status_code == status.HTTP_200_OK

    response = await auth_client.post("/api/v1/me/sessions/revoke-all", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["revoked"] == 1
    # The caller is still signed in.
    assert (await auth_client.get("/api/v1/me/sessions", headers=headers)).status_code == status.HTTP_200_OK
