"""Entrypoint contract: passwords, second factors and reset mails are rate limited.

Redis is replaced by an in-memory counter store; the throttle's own behaviour
when Redis is down is covered by its unit tests.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import status

from app.kernel.commons.time import utc_now
from app.kernel.identity.totp import generate_code
from app.modules.identity.application.sign_in_throttle import SignInThrottle
from app.settings.settings import settings
from tests.entrypoints import test_mfa_api
from tests.entrypoints.test_mfa_api import PASSWORD, _enrol, _register

auth_client = test_mfa_api.auth_client


class MemoryCounters:
    """The slice of the Redis client the throttle uses, without expiry."""

    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    async def get(self, name: str):
        return self.values.get(name)

    async def incr(self, name: str) -> int:
        self.values[name] = self.values.get(name, 0) + 1
        return self.values[name]

    async def expire(self, name: str, time: int) -> bool:
        return True

    async def ttl(self, name: str) -> int:
        return 42

    async def delete(self, *names: str) -> int:
        return sum(1 for name in names if self.values.pop(name, None) is not None)


@pytest_asyncio.fixture
async def counters(monkeypatch):
    store = MemoryCounters()
    monkeypatch.setattr(SignInThrottle, "_redis", lambda self: store)
    monkeypatch.setattr(settings, "auth_max_failed_attempts", 3)
    return store


async def _login(client, email: str, password: str):
    return await client.post("/api/v1/login", json={"email": email, "password": password})


@pytest.mark.asyncio
@pytest.mark.usefixtures("counters")
async def test_an_account_is_refused_after_too_many_wrong_passwords(auth_client):
    email = "throttle-password@example.com"
    await _register(auth_client, email)

    for _ in range(3):
        assert (await _login(auth_client, email, "wrong-password")).status_code == status.HTTP_401_UNAUTHORIZED

    # Refused even with the right password: otherwise the lockout only slows
    # guessing down instead of stopping it.
    locked = await _login(auth_client, email, PASSWORD)
    assert locked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert locked.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert locked.json()["details"]["retry_after"] == 42


@pytest.mark.asyncio
@pytest.mark.usefixtures("counters")
async def test_a_successful_sign_in_clears_the_failures(auth_client):
    email = "throttle-reset@example.com"
    await _register(auth_client, email)

    for _ in range(2):
        await _login(auth_client, email, "wrong-password")
    assert (await _login(auth_client, email, PASSWORD)).status_code == status.HTTP_200_OK
    for _ in range(2):
        await _login(auth_client, email, "wrong-password")
    assert (await _login(auth_client, email, PASSWORD)).status_code == status.HTTP_200_OK


@pytest.mark.asyncio
@pytest.mark.usefixtures("counters")
async def test_unknown_addresses_are_throttled_like_known_ones(auth_client):
    """Answering an unknown address differently would reveal which exist."""
    for _ in range(3):
        response = await _login(auth_client, "nobody@example.com", "wrong-password")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert (
        await _login(auth_client, "nobody@example.com", "wrong-password")
    ).status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
@pytest.mark.usefixtures("counters")
async def test_fresh_challenges_do_not_reset_second_factor_guesses(auth_client):
    email = "throttle-mfa@example.com"
    payload = await _register(auth_client, email)
    secret, _codes = await _enrol(auth_client, payload)

    async def _challenge() -> str:
        response = await _login(auth_client, email, PASSWORD)
        assert response.status_code == status.HTTP_200_OK, response.text
        return response.json()["data"]["mfa_token"]

    for _ in range(3):
        wrong = await auth_client.post(
            "/api/v1/login/mfa", json={"mfa_token": await _challenge(), "code": "000000"}
        )
        assert wrong.status_code == status.HTTP_401_UNAUTHORIZED

    right = await auth_client.post(
        "/api/v1/login/mfa",
        json={"mfa_token": await _challenge(), "code": generate_code(secret, int(utc_now().timestamp()))},
    )
    assert right.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
@pytest.mark.usefixtures("counters")
async def test_a_disabled_account_is_only_revealed_to_its_password(auth_client, async_db):
    from sqlmodel import select

    from app.modules.identity.domain.models import User

    email = "throttle-inactive@example.com"
    await _register(auth_client, email)
    user = (await async_db.exec(select(User).where(User.email == email))).one()
    user.is_active = False
    async_db.add(user)
    await async_db.commit()

    wrong = await _login(auth_client, email, "wrong-password")
    assert wrong.status_code == status.HTTP_401_UNAUTHORIZED
    assert "inactive" not in wrong.text
    right = await _login(auth_client, email, PASSWORD)
    assert right.status_code == status.HTTP_401_UNAUTHORIZED
    assert "inactive" in right.text
