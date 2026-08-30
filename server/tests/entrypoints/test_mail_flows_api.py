"""Entrypoint contract for the flows that need the instance to send mail.

Two properties matter throughout: a deployment with no mail outlet says so
instead of accepting requests it will drop, and a reset form never reveals
which addresses are registered.
"""

import pytest
from fastapi import status

from app.kernel.ports.mail.interface import MailMessage


class _Outbox:
    """Stands in for the mail outlet, keeping what would have been sent."""

    def __init__(self) -> None:
        self.sent: list[MailMessage] = []

    async def send(self, message: MailMessage) -> None:
        self.sent.append(message)


@pytest.fixture
def outbox():
    return _Outbox()


@pytest.fixture
def auth_client(db, outbox):
    """A client that really authenticates, with a mail outlet that records."""
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import Session as SqlModelSession

    from app.infra.db import session as db_session
    from app.infra.db.session import get_db
    from app.main import app
    from app.settings.settings import settings
    from app.wiring import container as container_module

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

    container = container_module.get_container()
    previous_mail = container.get_mail_port
    container.get_mail_port = lambda: outbox  # type: ignore[method-assign]

    previous_ingest = getattr(settings, "knowledge_ingest_worker_enabled", False)
    previous_outbox_flag = getattr(settings, "outbox_dispatcher_enabled", False)
    settings.knowledge_ingest_worker_enabled = False
    settings.outbox_dispatcher_enabled = False
    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        settings.knowledge_ingest_worker_enabled = previous_ingest
        settings.outbox_dispatcher_enabled = previous_outbox_flag
        app.dependency_overrides.pop(get_db, None)
        container.get_mail_port = previous_mail  # type: ignore[method-assign]
        db_session._engine = previous_engine
        db_session._SessionLocal = previous_factory


PASSWORD = "password123"


def _register(client, email: str) -> dict:
    response = client.post(
        "/api/v1/register",
        json={"email": email, "password": PASSWORD, "name": "Mail User"},
        params={"tenant_name": f"tenant-{email}"},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["data"]


def _headers(payload: dict) -> dict:
    return {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Workspace-Id": payload["workspace_id"],
    }


def _link(outbox: _Outbox, kind: str) -> str:
    body = next(message.body for message in outbox.sent if message.kind == kind)
    return next(line for line in body.splitlines() if line.startswith("http"))


def test_a_reset_request_answers_the_same_for_a_stranger(auth_client, outbox):
    """Otherwise the form is a way to find out who has an account."""
    _register(auth_client, "reset-known@example.com")

    known = auth_client.post(
        "/api/v1/auth/password-reset", json={"email": "reset-known@example.com"}
    )
    unknown = auth_client.post(
        "/api/v1/auth/password-reset", json={"email": "nobody@example.com"}
    )

    assert known.status_code == status.HTTP_204_NO_CONTENT
    assert unknown.status_code == status.HTTP_204_NO_CONTENT
    # Only the real account was mailed.
    assert [message.to for message in outbox.sent] == ["reset-known@example.com"]


def test_a_reset_link_sets_the_password_once_and_ends_open_sessions(auth_client, outbox):
    payload = _register(auth_client, "reset-use@example.com")
    auth_client.post("/api/v1/auth/password-reset", json={"email": "reset-use@example.com"})
    token = _link(outbox, "password_reset").split("token=")[1]

    reset = auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "brand-new-password"},
    )
    assert reset.status_code == status.HTTP_204_NO_CONTENT

    # The session open before the reset is gone: a reset is what someone does
    # when they think the account is compromised.
    assert (
        auth_client.get("/api/v1/me/sessions", headers=_headers(payload)).status_code
        == status.HTTP_401_UNAUTHORIZED
    )
    assert (
        auth_client.post(
            "/api/v1/login",
            json={"email": "reset-use@example.com", "password": "brand-new-password"},
        ).status_code
        == status.HTTP_200_OK
    )
    # And the link is spent.
    assert (
        auth_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "another-password"},
        ).status_code
        == status.HTTP_401_UNAUTHORIZED
    )


def test_asking_again_retires_the_earlier_link(auth_client, outbox):
    """A link someone was tricked into requesting must not outlive the real one."""
    _register(auth_client, "reset-twice@example.com")
    auth_client.post("/api/v1/auth/password-reset", json={"email": "reset-twice@example.com"})
    first = _link(outbox, "password_reset").split("token=")[1]
    auth_client.post("/api/v1/auth/password-reset", json={"email": "reset-twice@example.com"})

    response = auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": first, "new_password": "does-not-matter"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_an_invitation_is_addressed_to_one_person(auth_client, outbox):
    inviter = _register(auth_client, "inviter@example.com")
    invitee = _register(auth_client, "invitee@example.com")
    intruder = _register(auth_client, "intruder@example.com")

    created = auth_client.post(
        f"/api/v1/workspaces/{inviter['workspace_id']}/invitations",
        json={"email": "invitee@example.com", "role": "Dev"},
        headers=_headers(inviter),
    )
    assert created.status_code == status.HTTP_200_OK
    token = _link(outbox, "invitation").split("token=")[1]

    # A forwarded link does not move the membership to whoever opened it.
    refused = auth_client.post(
        "/api/v1/invitations/accept",
        json={"token": token},
        headers=_headers(intruder),
    )
    assert refused.status_code == status.HTTP_403_FORBIDDEN

    accepted = auth_client.post(
        "/api/v1/invitations/accept",
        json={"token": token},
        headers=_headers(invitee),
    )
    assert accepted.status_code == status.HTTP_200_OK
    assert accepted.json()["data"]["status"] == "accepted"

    members = auth_client.get(
        f"/api/v1/workspaces/{inviter['workspace_id']}/members",
        headers=_headers(inviter),
    )
    assert "invitee@example.com" in [row["email"] for row in members.json()["data"]]


def test_a_revoked_invitation_stops_working_immediately(auth_client, outbox):
    inviter = _register(auth_client, "revoker@example.com")
    invitee = _register(auth_client, "revoked-invitee@example.com")
    created = auth_client.post(
        f"/api/v1/workspaces/{inviter['workspace_id']}/invitations",
        json={"email": "revoked-invitee@example.com", "role": "Viewer"},
        headers=_headers(inviter),
    ).json()["data"]
    token = _link(outbox, "invitation").split("token=")[1]

    revoked = auth_client.delete(
        f"/api/v1/invitations/{created['id']}", headers=_headers(inviter)
    )
    assert revoked.status_code == status.HTTP_200_OK

    response = auth_client.post(
        "/api/v1/invitations/accept",
        json={"token": token},
        headers=_headers(invitee),
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_confirming_an_address_records_when(auth_client, outbox):
    payload = _register(auth_client, "verify@example.com")

    requested = auth_client.post(
        "/api/v1/me/email-verification", headers=_headers(payload)
    )
    assert requested.status_code == status.HTTP_204_NO_CONTENT
    token = _link(outbox, "email_verification").split("token=")[1]

    confirmed = auth_client.post(
        "/api/v1/auth/email-verification/confirm", json={"token": token}
    )
    assert confirmed.status_code == status.HTTP_204_NO_CONTENT

    me = auth_client.get("/api/v1/me", headers=_headers(payload)).json()["data"]
    assert me["profile"]["email_verified_at"]
