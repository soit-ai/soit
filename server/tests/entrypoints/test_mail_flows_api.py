"""Entrypoint contract for the flows that need the instance to send mail.

Two properties matter throughout: a deployment with no mail outlet says so
instead of accepting requests it will drop, and a reset form never reveals
which addresses are registered.
"""

import pytest
import pytest_asyncio
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


@pytest_asyncio.fixture
async def auth_client(async_db, outbox):
    """A client that really authenticates, with a mail outlet that records."""
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.infra.db import session as db_session
    from app.infra.db.session import get_async_db
    from app.main import app
    from app.settings.settings import settings
    from app.wiring import container as container_module

    async def _override_get_async_db():
        yield async_db

    engine = async_db.bind
    previous_engine = db_session._async_engine
    previous_factory = db_session._AsyncSessionLocal
    db_session._async_engine = engine
    db_session._AsyncSessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    container = container_module.get_container()
    previous_mail = container.get_mail_port
    container.get_mail_port = lambda: outbox  # type: ignore[method-assign]

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
        container.get_mail_port = previous_mail  # type: ignore[method-assign]

        db_session._async_engine = previous_engine
        db_session._AsyncSessionLocal = previous_factory


PASSWORD = "password123"


async def _register(async_client, email: str) -> dict:
    response = await async_client.post(
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


@pytest.mark.asyncio
async def test_a_reset_request_answers_the_same_for_a_stranger(auth_client, outbox):
    """Otherwise the form is a way to find out who has an account."""
    await _register(auth_client, "reset-known@example.com")

    known = await auth_client.post(
        "/api/v1/auth/password-reset", json={"email": "reset-known@example.com"}
    )
    unknown = await auth_client.post(
        "/api/v1/auth/password-reset", json={"email": "nobody@example.com"}
    )

    assert known.status_code == status.HTTP_204_NO_CONTENT
    assert unknown.status_code == status.HTTP_204_NO_CONTENT
    # Only the real account was mailed.
    assert [message.to for message in outbox.sent] == ["reset-known@example.com"]


@pytest.mark.asyncio
async def test_a_reset_link_sets_the_password_once_and_ends_open_sessions(auth_client, outbox):
    payload = await _register(auth_client, "reset-use@example.com")
    await auth_client.post("/api/v1/auth/password-reset", json={"email": "reset-use@example.com"})
    token = _link(outbox, "password_reset").split("token=")[1]

    reset = await auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "brand-new-password"},
    )
    assert reset.status_code == status.HTTP_204_NO_CONTENT

    # The session open before the reset is gone: a reset is what someone does
    # when they think the account is compromised.
    assert (
        (await auth_client.get("/api/v1/me/sessions", headers=_headers(payload))).status_code
        == status.HTTP_401_UNAUTHORIZED
    )
    assert (
        (await auth_client.post(
            "/api/v1/login",
            json={"email": "reset-use@example.com", "password": "brand-new-password"},
        )).status_code
        == status.HTTP_200_OK
    )
    # And the link is spent.
    assert (
        (await auth_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "another-password"},
        )).status_code
        == status.HTTP_401_UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_asking_again_retires_the_earlier_link(auth_client, outbox):
    """A link someone was tricked into requesting must not outlive the real one."""
    await _register(auth_client, "reset-twice@example.com")
    await auth_client.post("/api/v1/auth/password-reset", json={"email": "reset-twice@example.com"})
    first = _link(outbox, "password_reset").split("token=")[1]
    await auth_client.post("/api/v1/auth/password-reset", json={"email": "reset-twice@example.com"})

    response = await auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": first, "new_password": "does-not-matter"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_an_invitation_is_addressed_to_one_person(auth_client, outbox):
    inviter = await _register(auth_client, "inviter@example.com")
    invitee = await _register(auth_client, "invitee@example.com")
    intruder = await _register(auth_client, "intruder@example.com")

    created = await auth_client.post(
        f"/api/v1/workspaces/{inviter['workspace_id']}/invitations",
        json={"email": "invitee@example.com", "role": "Dev"},
        headers=_headers(inviter),
    )
    assert created.status_code == status.HTTP_200_OK
    token = _link(outbox, "invitation").split("token=")[1]

    # A forwarded link does not move the membership to whoever opened it.
    refused = await auth_client.post(
        "/api/v1/invitations/accept",
        json={"token": token},
        headers=_headers(intruder),
    )
    assert refused.status_code == status.HTTP_403_FORBIDDEN

    accepted = await auth_client.post(
        "/api/v1/invitations/accept",
        json={"token": token},
        headers=_headers(invitee),
    )
    assert accepted.status_code == status.HTTP_200_OK
    assert accepted.json()["data"]["status"] == "accepted"

    members = await auth_client.get(
        f"/api/v1/workspaces/{inviter['workspace_id']}/members",
        headers=_headers(inviter),
    )
    assert "invitee@example.com" in [row["email"] for row in members.json()["data"]]


@pytest.mark.asyncio
async def test_a_revoked_invitation_stops_working_immediately(auth_client, outbox):
    inviter = await _register(auth_client, "revoker@example.com")
    invitee = await _register(auth_client, "revoked-invitee@example.com")
    created = (await auth_client.post(
        f"/api/v1/workspaces/{inviter['workspace_id']}/invitations",
        json={"email": "revoked-invitee@example.com", "role": "Viewer"},
        headers=_headers(inviter),
    )).json()["data"]
    token = _link(outbox, "invitation").split("token=")[1]

    revoked = await auth_client.delete(
        f"/api/v1/invitations/{created['id']}", headers=_headers(inviter)
    )
    assert revoked.status_code == status.HTTP_200_OK

    response = await auth_client.post(
        "/api/v1/invitations/accept",
        json={"token": token},
        headers=_headers(invitee),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_confirming_an_address_records_when(auth_client, outbox):
    payload = await _register(auth_client, "verify@example.com")

    requested = await auth_client.post(
        "/api/v1/me/email-verification", headers=_headers(payload)
    )
    assert requested.status_code == status.HTTP_204_NO_CONTENT
    token = _link(outbox, "email_verification").split("token=")[1]

    confirmed = await auth_client.post(
        "/api/v1/auth/email-verification/confirm", json={"token": token}
    )
    assert confirmed.status_code == status.HTTP_204_NO_CONTENT

    me = (await auth_client.get("/api/v1/me", headers=_headers(payload))).json()["data"]
    assert me["profile"]["email_verified_at"]


@pytest.mark.asyncio
async def test_reset_mails_to_one_address_are_capped(auth_client, outbox, monkeypatch):
    """Otherwise the form can flood someone's mailbox; unknown addresses count
    the same so the cap reveals nothing about which are registered."""
    from app.modules.identity.application.sign_in_throttle import SignInThrottle
    from app.settings.settings import settings

    counts: dict[str, int] = {}

    class _Counters:
        async def get(self, name):
            return counts.get(name)

        async def incr(self, name):
            counts[name] = counts.get(name, 0) + 1
            return counts[name]

        async def expire(self, name, time):
            return True

        async def ttl(self, name):
            return 60

        async def delete(self, *names):
            return 0

    monkeypatch.setattr(SignInThrottle, "_redis", lambda self: _Counters())
    monkeypatch.setattr(settings, "auth_max_failed_attempts", 2)
    await _register(auth_client, "reset-flood@example.com")

    for email in ("reset-flood@example.com", "reset-nobody@example.com"):
        for _ in range(2):
            response = await auth_client.post("/api/v1/auth/password-reset", json={"email": email})
            assert response.status_code == status.HTTP_204_NO_CONTENT
        refused = await auth_client.post("/api/v1/auth/password-reset", json={"email": email})
        assert refused.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    assert len([m for m in outbox.sent if "reset-password" in m.body]) == 2


@pytest.mark.asyncio
async def test_signing_up_with_an_invitation_lands_in_the_invited_workspace(
    auth_client, outbox, monkeypatch
):
    """The invitation admits even with public sign-up off, and only its addressee."""
    from app.settings.settings import settings

    inviter = await _register(auth_client, "signup-inviter@example.com")
    created = await auth_client.post(
        f"/api/v1/workspaces/{inviter['workspace_id']}/invitations",
        json={"email": "newcomer@example.com", "role": "Dev"},
        headers=_headers(inviter),
    )
    assert created.status_code == status.HTTP_200_OK
    token = _link(outbox, "invitation").split("token=")[1]
    monkeypatch.setattr(settings, "allow_public_registration", False)

    def _sign_up(email: str, invitation_token: str | None):
        return auth_client.post(
            "/api/v1/register",
            json={
                "email": email,
                "password": PASSWORD,
                "name": "Newcomer",
                "invitation_token": invitation_token,
            },
        )

    assert (await _sign_up("uninvited@example.com", None)).status_code == status.HTTP_403_FORBIDDEN
    forwarded = await _sign_up("forwarded@example.com", token)
    assert forwarded.status_code == status.HTTP_403_FORBIDDEN
    # The refusal left no account behind for that address.
    assert (await _sign_up("forwarded@example.com", None)).status_code == status.HTTP_403_FORBIDDEN
    monkeypatch.setattr(settings, "allow_public_registration", True)
    assert (await _sign_up("forwarded@example.com", None)).status_code == status.HTTP_200_OK
    monkeypatch.setattr(settings, "allow_public_registration", False)

    joined = await _sign_up("newcomer@example.com", token)
    assert joined.status_code == status.HTTP_200_OK, joined.text
    newcomer = joined.json()["data"]
    assert newcomer["workspace_id"] == inviter["workspace_id"]

    members = await auth_client.get(
        f"/api/v1/workspaces/{inviter['workspace_id']}/members",
        headers=_headers(inviter),
    )
    roles = {row["email"]: row["role"] for row in members.json()["data"]}
    assert roles["newcomer@example.com"] == "Dev"
    # The link is spent.
    assert (await _sign_up("newcomer-2@example.com", token)).status_code == status.HTTP_400_BAD_REQUEST

