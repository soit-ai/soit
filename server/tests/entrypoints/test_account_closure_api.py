"""Entrypoint contract for closing an account.

Closure removes access; it does not remove history. The pause before it takes
effect is what makes a closure asked for in anger, or by someone holding a
stolen session, recoverable.
"""

import pytest
import pytest_asyncio
from fastapi import status

from app.kernel.commons.time import utc_now


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


async def _second_owner(async_db, tenant_id: str) -> None:
    """Give the tenant another owner so the caller is not its last one."""
    from app.kernel.identity.rbac import TENANT_ROLE_OWNER
    from app.modules.identity.domain.models import TenantMembership, User

    other = User(email=f"co-owner-{tenant_id}@example.com", password_hash="x", name="Co")
    async_db.add(other)
    await async_db.commit()
    async_db.add(
        TenantMembership(tenant_id=tenant_id, user_id=other.id, role=TENANT_ROLE_OWNER)
    )
    await async_db.commit()


async def _tenant_of(async_db, user_email: str) -> str:
    from sqlmodel import select

    from app.modules.identity.domain.models import TenantMembership, User

    user = (await async_db.exec(select(User).where(User.email == user_email))).first()
    user = user[0] if isinstance(user, tuple) else user
    membership = (await async_db.exec(
        select(TenantMembership).where(TenantMembership.user_id == user.id)
    )).first()
    membership = membership[0] if isinstance(membership, tuple) else membership
    return membership.tenant_id


@pytest.mark.asyncio
async def test_the_last_owner_of_a_tenant_cannot_close_their_account(auth_client):
    """It would leave the tenant with nobody who can administer it."""
    payload = await _register(auth_client, "closing-owner@example.com")

    response = await auth_client.post(
        "/api/v1/me/deletion-request",
        json={"reason": "leaving"},
        headers=_headers(payload),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ownership" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_a_closure_is_recorded_with_a_pause_and_can_be_withdrawn(auth_client, async_db):
    payload = await _register(auth_client, "closing-member@example.com")
    await _second_owner(async_db, await _tenant_of(async_db, "closing-member@example.com"))

    created = await auth_client.post(
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

    pending = await auth_client.get("/api/v1/me/deletion-request", headers=_headers(payload))
    assert pending.json()["data"]["id"] == request["id"]

    withdrawn = await auth_client.delete("/api/v1/me/deletion-request", headers=_headers(payload))
    assert withdrawn.status_code == status.HTTP_200_OK
    assert withdrawn.json()["data"]["status"] == "cancelled"
    assert (await auth_client.get(
        "/api/v1/me/deletion-request", headers=_headers(payload)
    )).json()["data"] is None


@pytest.mark.asyncio
async def test_asking_twice_returns_the_same_request(auth_client, async_db):
    payload = await _register(auth_client, "closing-twice@example.com")
    await _second_owner(async_db, await _tenant_of(async_db, "closing-twice@example.com"))

    first = (await auth_client.post(
        "/api/v1/me/deletion-request", json={}, headers=_headers(payload)
    )).json()["data"]
    second = (await auth_client.post(
        "/api/v1/me/deletion-request", json={}, headers=_headers(payload)
    )).json()["data"]

    assert first["id"] == second["id"]


@pytest.mark.asyncio
async def test_withdrawing_when_nothing_is_pending_is_a_404(auth_client):
    payload = await _register(auth_client, "closing-none@example.com")

    response = await auth_client.delete("/api/v1/me/deletion-request", headers=_headers(payload))

    assert response.status_code == status.HTTP_404_NOT_FOUND
