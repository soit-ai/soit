"""Entrypoint contract for the second factor.

The property that matters is that a password alone stops producing a session
the moment a second factor is active, and that the token bridging the two steps
cannot be used for anything else.
"""

import pytest
import pytest_asyncio
from fastapi import status

from app.kernel.commons.time import utc_now
from app.kernel.identity.totp import generate_code


@pytest_asyncio.fixture
async def auth_client(async_db):
    """A client that really authenticates, sharing this test's database."""
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
    previous_outbox = getattr(settings, "outbox_dispatcher_enabled", False)
    settings.knowledge_ingest_worker_enabled = False
    settings.outbox_dispatcher_enabled = False
    app.dependency_overrides[get_async_db] = _override_get_async_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as test_client:
            yield test_client
    finally:
        settings.knowledge_ingest_worker_enabled = previous_ingest
        settings.outbox_dispatcher_enabled = previous_outbox
        app.dependency_overrides.pop(get_async_db, None)
        db_session._async_engine = previous_engine
        db_session._AsyncSessionLocal = previous_factory


PASSWORD = "password123"


async def _register(async_client, email: str) -> dict:
    response = await async_client.post(
        "/api/v1/register",
        json={"email": email, "password": PASSWORD, "name": "MFA User"},
        params={"tenant_name": f"tenant-{email}"},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["data"]


def _headers(payload: dict) -> dict:
    return {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Workspace-Id": payload["workspace_id"],
    }


async def _enrol(async_client, payload: dict) -> tuple[str, list[str]]:
    """Complete enrolment and return (secret, recovery codes)."""
    setup = await async_client.post("/api/v1/me/mfa/setup", headers=_headers(payload))
    assert setup.status_code == status.HTTP_200_OK, setup.text
    secret = setup.json()["data"]["secret"]

    confirm = await async_client.post(
        "/api/v1/me/mfa/confirm",
        json={"code": generate_code(secret, int(utc_now().timestamp()))},
        headers=_headers(payload),
    )
    assert confirm.status_code == status.HTTP_200_OK, confirm.text
    return secret, confirm.json()["data"]["recovery_codes"]


@pytest.mark.asyncio
async def test_enrolment_is_not_active_until_a_code_confirms_it(auth_client):
    """Activating at setup would let a mistyped scan lock someone out."""
    payload = await _register(auth_client, "mfa-pending@example.com")

    setup = await auth_client.post("/api/v1/me/mfa/setup", headers=_headers(payload))
    assert setup.status_code == status.HTTP_200_OK
    assert setup.json()["data"]["provisioning_uri"].startswith("otpauth://totp/")

    state = (await auth_client.get("/api/v1/me/mfa", headers=_headers(payload))).json()["data"]
    assert state["enabled"] is False
    assert state["pending"] is True

    # And a password still signs in, because nothing is enforced yet.
    login = await auth_client.post(
        "/api/v1/login",
        json={"email": "mfa-pending@example.com", "password": PASSWORD},
    )
    assert login.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_a_wrong_code_does_not_activate_the_enrolment(auth_client):
    payload = await _register(auth_client, "mfa-wrong@example.com")
    await auth_client.post("/api/v1/me/mfa/setup", headers=_headers(payload))

    confirm = await auth_client.post(
        "/api/v1/me/mfa/confirm",
        json={"code": "000000"},
        headers=_headers(payload),
    )

    assert confirm.status_code == status.HTTP_401_UNAUTHORIZED
    state = (await auth_client.get("/api/v1/me/mfa", headers=_headers(payload))).json()["data"]
    assert state["enabled"] is False


@pytest.mark.asyncio
async def test_once_enabled_a_password_alone_no_longer_signs_in(auth_client):
    payload = await _register(auth_client, "mfa-login@example.com")
    secret, _codes = await _enrol(auth_client, payload)

    login = await auth_client.post(
        "/api/v1/login",
        json={"email": "mfa-login@example.com", "password": PASSWORD},
    )

    assert login.status_code == status.HTTP_200_OK
    challenge = login.json()["data"]
    assert challenge["mfa_required"] is True
    assert challenge["mfa_token"]
    assert "access_token" not in challenge

    completed = await auth_client.post(
        "/api/v1/login/mfa",
        json={
            "mfa_token": challenge["mfa_token"],
            "code": generate_code(secret, int(utc_now().timestamp())),
        },
    )
    assert completed.status_code == status.HTTP_200_OK
    assert completed.json()["data"]["access_token"]
    assert completed.json()["data"]["refresh_token"]


@pytest.mark.asyncio
async def test_the_challenge_token_cannot_authorize_a_request(auth_client):
    """Otherwise the second factor is optional for anyone who notices."""
    payload = await _register(auth_client, "mfa-bearer@example.com")
    await _enrol(auth_client, payload)
    challenge = (await auth_client.post(
        "/api/v1/login",
        json={"email": "mfa-bearer@example.com", "password": PASSWORD},
    )).json()["data"]

    response = await auth_client.get(
        "/api/v1/me/mfa",
        headers={
            "Authorization": f"Bearer {challenge['mfa_token']}",
            "X-Workspace-Id": payload["workspace_id"],
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_a_recovery_code_signs_in_once_and_only_once(auth_client):
    payload = await _register(auth_client, "mfa-recovery@example.com")
    _secret, codes = await _enrol(auth_client, payload)
    assert len(codes) == 10

    async def _sign_in_with(code: str):
        challenge = (await auth_client.post(
            "/api/v1/login",
            json={"email": "mfa-recovery@example.com", "password": PASSWORD},
        )).json()["data"]
        return await auth_client.post(
            "/api/v1/login/mfa",
            json={"mfa_token": challenge["mfa_token"], "code": code},
        )

    first = await _sign_in_with(codes[0])
    assert first.status_code == status.HTTP_200_OK

    replay = await _sign_in_with(codes[0])
    assert replay.status_code == status.HTTP_401_UNAUTHORIZED

    # A different code from the same sheet still works.
    assert (await _sign_in_with(codes[1])).status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_turning_the_second_factor_off_needs_the_password(auth_client):
    """A live session is exactly what a second factor is meant to survive."""
    payload = await _register(auth_client, "mfa-disable@example.com")
    await _enrol(auth_client, payload)

    refused = await auth_client.post(
        "/api/v1/me/mfa/disable",
        json={"password": "not-the-password"},
        headers=_headers(payload),
    )
    assert refused.status_code == status.HTTP_401_UNAUTHORIZED
    assert (await auth_client.get("/api/v1/me/mfa", headers=_headers(payload))).json()["data"][
        "enabled"
    ]

    accepted = await auth_client.post(
        "/api/v1/me/mfa/disable",
        json={"password": PASSWORD},
        headers=_headers(payload),
    )
    assert accepted.status_code == status.HTTP_204_NO_CONTENT
    assert not (await auth_client.get("/api/v1/me/mfa", headers=_headers(payload))).json()["data"][
        "enabled"
    ]


@pytest.mark.asyncio
async def test_regenerating_recovery_codes_retires_the_old_sheet(auth_client):
    payload = await _register(auth_client, "mfa-regen@example.com")
    secret, old_codes = await _enrol(auth_client, payload)

    regenerated = await auth_client.post(
        "/api/v1/me/mfa/recovery-codes",
        json={"code": generate_code(secret, int(utc_now().timestamp()))},
        headers=_headers(payload),
    )
    assert regenerated.status_code == status.HTTP_200_OK
    new_codes = regenerated.json()["data"]["recovery_codes"]
    assert set(new_codes).isdisjoint(old_codes)

    challenge = (await auth_client.post(
        "/api/v1/login",
        json={"email": "mfa-regen@example.com", "password": PASSWORD},
    )).json()["data"]
    stale = await auth_client.post(
        "/api/v1/login/mfa",
        json={"mfa_token": challenge["mfa_token"], "code": old_codes[0]},
    )
    assert stale.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_a_workspace_can_require_a_second_factor(auth_client, async_db):
    """The requirement belongs to one workspace, not to the sign-in."""
    from app.modules.identity.domain.models import Workspace

    payload = await _register(auth_client, "mfa-required@example.com")
    workspace = await async_db.get(Workspace, payload["workspace_id"])
    workspace.require_mfa = True
    async_db.add(workspace)
    await async_db.commit()

    blocked = await auth_client.get("/api/v1/me/mfa", headers=_headers(payload))
    assert blocked.status_code == status.HTTP_403_FORBIDDEN
    # Distinguishable from "not a member", so the console can offer enrolment
    # rather than an access error nobody can act on.
    assert blocked.json()["details"]["reason"] == "mfa_required"
