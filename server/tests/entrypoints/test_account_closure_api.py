"""Entrypoint contract for closing an account.

Closure removes access; it does not remove history. The pause before it takes
effect is what makes a closure asked for in anger, or by someone holding a
stolen session, recoverable.
"""

import pytest
from fastapi import status

from app.kernel.commons.time import utc_now


@pytest.fixture
def auth_client(db):
    """A client that really authenticates, sharing this test's database."""
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import Session as SqlModelSession

    from app.infra.db import session as db_session
    from app.infra.db.session import get_db
    from app.main import app
    from app.settings.settings import settings

    def _override_get_db():
        yield db

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


PASSWORD = "password123"


def _register(client, email: str) -> dict:
    response = client.post(
        "/api/v1/register",
        json={"email": email, "password": PASSWORD, "name": "Closing User"},
        params={"tenant_name": f"tenant-{email}"},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["data"]


def _headers(payload: dict) -> dict:
    return {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Workspace-Id": payload["workspace_id"],
    }


def _second_owner(db, tenant_id: str) -> None:
    """Give the tenant another owner so the caller is not its last one."""
    from app.kernel.identity.rbac import TENANT_ROLE_OWNER
    from app.modules.identity.domain.models import TenantMembership, User

    other = User(email=f"co-owner-{tenant_id}@example.com", password_hash="x", name="Co")
    db.add(other)
    db.commit()
    db.add(
        TenantMembership(tenant_id=tenant_id, user_id=other.id, role=TENANT_ROLE_OWNER)
    )
    db.commit()


def _tenant_of(db, user_email: str) -> str:
    from sqlmodel import select

    from app.modules.identity.domain.models import TenantMembership, User

    user = db.exec(select(User).where(User.email == user_email)).first()
    user = user[0] if isinstance(user, tuple) else user
    membership = db.exec(
        select(TenantMembership).where(TenantMembership.user_id == user.id)
    ).first()
    membership = membership[0] if isinstance(membership, tuple) else membership
    return membership.tenant_id


def test_the_last_owner_of_a_tenant_cannot_close_their_account(auth_client):
    """It would leave the tenant with nobody who can administer it."""
    payload = _register(auth_client, "closing-owner@example.com")

    response = auth_client.post(
        "/api/v1/me/deletion-request",
        json={"reason": "leaving"},
        headers=_headers(payload),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ownership" in response.json()["message"].lower()


def test_a_closure_is_recorded_with_a_pause_and_can_be_withdrawn(auth_client, db):
    payload = _register(auth_client, "closing-member@example.com")
    _second_owner(db, _tenant_of(db, "closing-member@example.com"))

    created = auth_client.post(
        "/api/v1/me/deletion-request",
        json={"reason": "moving on"},
        headers=_headers(payload),
    )
    assert created.status_code == status.HTTP_200_OK
    request = created.json()["data"]
    assert request["status"] == "pending"
    assert request["reason"] == "moving on"
    # The pause is in the future; nothing has been closed.
    assert request["execute_after"] > utc_now().isoformat()

    pending = auth_client.get("/api/v1/me/deletion-request", headers=_headers(payload))
    assert pending.json()["data"]["id"] == request["id"]

    withdrawn = auth_client.delete("/api/v1/me/deletion-request", headers=_headers(payload))
    assert withdrawn.status_code == status.HTTP_200_OK
    assert withdrawn.json()["data"]["status"] == "cancelled"
    assert auth_client.get(
        "/api/v1/me/deletion-request", headers=_headers(payload)
    ).json()["data"] is None


def test_asking_twice_returns_the_same_request(auth_client, db):
    payload = _register(auth_client, "closing-twice@example.com")
    _second_owner(db, _tenant_of(db, "closing-twice@example.com"))

    first = auth_client.post(
        "/api/v1/me/deletion-request", json={}, headers=_headers(payload)
    ).json()["data"]
    second = auth_client.post(
        "/api/v1/me/deletion-request", json={}, headers=_headers(payload)
    ).json()["data"]

    assert first["id"] == second["id"]


def test_withdrawing_when_nothing_is_pending_is_a_404(auth_client):
    payload = _register(auth_client, "closing-none@example.com")

    response = auth_client.delete("/api/v1/me/deletion-request", headers=_headers(payload))

    assert response.status_code == status.HTTP_404_NOT_FOUND
