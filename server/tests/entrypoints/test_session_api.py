"""Entrypoint contract for the session and refresh surface.

Signing out has to mean the access token stops working, not that it expires
eventually. These drive the real routes to prove that end to end.
"""

import pytest
from fastapi import status


@pytest.fixture
def auth_client(db):
    """A client that really authenticates.

    The shared `client` fixture overrides context resolution so every request
    is the same synthetic user; these tests are about who the caller is and
    whether their session is still alive, so they need the real path.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import Session as SqlModelSession

    from app.infra.db import session as db_session
    from app.infra.db.session import get_db
    from app.main import app
    from app.settings.settings import settings

    def _override_get_db():
        yield db

    # Authenticating for real means the membership and session reads run, and
    # those open their own connection through get_db_sync rather than the
    # request's. Point the global engine at this test's in-memory database so
    # they land in the same place.
    engine = db.get_bind()
    previous_engine = db_session._engine
    previous_factory = db_session._SessionLocal
    db_session._engine = engine
    db_session._SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=SqlModelSession,
    )

    previous_ingest = getattr(settings, "knowledge_ingest_worker_enabled", False)
    previous_outbox = getattr(settings, "outbox_dispatcher_enabled", False)
    settings.knowledge_ingest_worker_enabled = False
    settings.outbox_dispatcher_enabled = False
    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        settings.knowledge_ingest_worker_enabled = previous_ingest
        settings.outbox_dispatcher_enabled = previous_outbox
        app.dependency_overrides.pop(get_db, None)
        db_session._engine = previous_engine
        db_session._SessionLocal = previous_factory


def _register(auth_client, email: str = "sessions-api@example.com") -> dict:
    response = auth_client.post(
        "/api/v1/register",
        json={"email": email, "password": "password123", "name": "API User"},
        params={"tenant_name": f"tenant-{email}"},
    )
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED), response.text
    return response.json()["data"]


def _auth(token: str, workspace_id: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-Workspace-Id": workspace_id}


def test_registration_returns_a_refresh_token(auth_client):
    payload = _register(auth_client)

    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["expires_in"] > 0


def test_refresh_returns_a_new_pair_and_the_old_one_stops_working(auth_client):
    payload = _register(auth_client, "refresh-api@example.com")

    first = auth_client.post(
        "/api/v1/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert first.status_code == status.HTTP_200_OK
    rotated = first.json()["data"]
    assert rotated["refresh_token"] != payload["refresh_token"]

    replay = auth_client.post(
        "/api/v1/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert replay.status_code == status.HTTP_401_UNAUTHORIZED


def test_a_session_lists_itself_as_the_current_one(auth_client):
    payload = _register(auth_client, "list-api@example.com")
    headers = _auth(payload["access_token"], payload["workspace_id"])

    response = auth_client.get("/api/v1/me/sessions", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    sessions = response.json()["data"]
    assert len(sessions) == 1
    assert sessions[0]["current"] is True
    assert sessions[0]["status"] == "active"


def test_revoking_the_current_session_immediately_stops_its_token(auth_client):
    """The point of the session id in the token: a sign-out takes effect now."""
    payload = _register(auth_client, "revoke-api@example.com")
    headers = _auth(payload["access_token"], payload["workspace_id"])
    session_id = auth_client.get("/api/v1/me/sessions", headers=headers).json()["data"][0]["id"]

    revoked = auth_client.delete(f"/api/v1/me/sessions/{session_id}", headers=headers)
    assert revoked.status_code == status.HTTP_200_OK

    after = auth_client.get("/api/v1/me/sessions", headers=headers)
    assert after.status_code == status.HTTP_401_UNAUTHORIZED


def test_signing_out_everywhere_keeps_the_calling_device_by_default(auth_client):
    payload = _register(auth_client, "revoke-all-api@example.com")
    headers = _auth(payload["access_token"], payload["workspace_id"])
    # A second sign-in from somewhere else.
    other = auth_client.post(
        "/api/v1/login",
        json={"email": "revoke-all-api@example.com", "password": "password123"},
    )
    assert other.status_code == status.HTTP_200_OK

    response = auth_client.post("/api/v1/me/sessions/revoke-all", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["revoked"] == 1
    # The caller is still signed in.
    assert auth_client.get("/api/v1/me/sessions", headers=headers).status_code == status.HTTP_200_OK
