"""Entrypoint contract for people who belong to more than one organization.

A token records the organization its sign-in began in; the workspace a
request names decides the organization it acts in. These drive the real
authentication path, so a workspace in another organization the caller
belongs to is reachable without signing in again, and one they do not belong
to is not.
"""

import pytest
import pytest_asyncio
from fastapi import status


@pytest_asyncio.fixture
async def auth_client(async_db):
    """A client that really authenticates (see test_session_api)."""
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


async def _register(auth_client, email: str, *, tenant_name: str | None = None) -> dict:
    params = {"tenant_name": tenant_name} if tenant_name else None
    response = await auth_client.post(
        "/api/v1/register",
        json={"email": email, "password": "password123", "name": email.split("@")[0]},
        params=params,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["data"]


def _auth(token: str, workspace_id: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-Workspace-Id": workspace_id}


async def _me(auth_client, session: dict) -> dict:
    response = await auth_client.get(
        "/api/v1/me", headers=_auth(session["access_token"], session["workspace_id"])
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["data"]


async def _workspace(auth_client, session: dict, workspace_id: str):
    return await auth_client.get(
        f"/api/v1/workspaces/{workspace_id}",
        headers=_auth(session["access_token"], workspace_id),
    )


@pytest.mark.asyncio
async def test_a_workspace_in_another_organization_is_reachable(auth_client, multi_organization):
    owner = await _register(auth_client, "owner@acme.example.com", tenant_name="Acme")
    pat = await _register(auth_client, "pat@elsewhere.example.com", tenant_name="Elsewhere")
    stranger = await _register(auth_client, "stranger@nowhere.example.com", tenant_name="Nowhere")
    acme_workspace = owner["workspace_id"]
    acme_id = (await _workspace(auth_client, owner, acme_workspace)).json()["data"]["tenant_id"]
    pat_id = (await _me(auth_client, pat))["id"]

    owner_headers = _auth(owner["access_token"], acme_workspace)
    added = await auth_client.post(
        f"/api/v1/tenants/{acme_id}/members",
        json={"user_id": pat_id, "role": "Member"},
        headers=owner_headers,
    )
    assert added.status_code == status.HTTP_200_OK, added.text
    added = await auth_client.post(
        f"/api/v1/workspaces/{acme_workspace}/members",
        json={"user_id": pat_id, "role": "Dev"},
        headers=owner_headers,
    )
    assert added.status_code == status.HTTP_200_OK, added.text

    # Pat's token was issued for their own organization; the switcher lists
    # Acme's workspace beside it, and naming it is all it takes to act there.
    listed = await auth_client.get(
        "/api/v1/me/workspaces", headers=_auth(pat["access_token"], pat["workspace_id"])
    )
    assert listed.status_code == status.HTTP_200_OK, listed.text
    rows = {row["id"]: row for row in listed.json()["data"]}
    assert rows[pat["workspace_id"]]["tenant_name"] == "Elsewhere"
    assert rows[acme_workspace]["tenant_id"] == acme_id
    assert rows[acme_workspace]["tenant_name"] == "Acme"
    assert rows[acme_workspace]["role"] == "Dev"
    assert listed.json()["data"][0]["id"] == pat["workspace_id"]  # current organization first

    reached = await _workspace(auth_client, pat, acme_workspace)
    assert reached.status_code == status.HTTP_200_OK, reached.text
    assert reached.json()["data"]["tenant_id"] == acme_id

    refused = await _workspace(auth_client, stranger, acme_workspace)
    assert refused.status_code == status.HTTP_403_FORBIDDEN


async def _capabilities(auth_client) -> dict:
    response = await auth_client.get("/api/v1/auth/capabilities")
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_one_organization_the_first_founds_and_the_rest_join(auth_client):
    assert (await _capabilities(auth_client))["sign_up_founds_organization"] is True
    founder = await _register(auth_client, "founder@example.com", tenant_name="Acme")
    assert (await _capabilities(auth_client))["sign_up_founds_organization"] is False

    # A later sign-up joins Acme whatever name it asks for, as a member with a
    # workspace of its own, not a seat in the founder's.
    joiner = await _register(auth_client, "joiner@example.com", tenant_name="Breakaway")
    assert joiner["workspace_id"] != founder["workspace_id"]
    founder_org = (await _workspace(auth_client, founder, founder["workspace_id"])).json()["data"]
    joiner_ws = (await _workspace(auth_client, joiner, joiner["workspace_id"])).json()["data"]
    assert joiner_ws["tenant_id"] == founder_org["tenant_id"]
    assert joiner_ws["name"] == "joiner's workspace"
    assert (await _workspace(auth_client, joiner, founder["workspace_id"])).status_code == (
        status.HTTP_403_FORBIDDEN
    )
    listed = await auth_client.get(
        "/api/v1/me/workspaces", headers=_auth(joiner["access_token"], joiner["workspace_id"])
    )
    assert [row["tenant_name"] for row in listed.json()["data"]] == ["Acme"]

    # Being in one organization is what lets the founder add the joiner to a
    # shared workspace by id, with no mail outlet needed.
    joiner_id = (await _me(auth_client, joiner))["id"]
    added = await auth_client.post(
        f"/api/v1/workspaces/{founder['workspace_id']}/members",
        json={"user_id": joiner_id, "role": "Viewer"},
        headers=_auth(founder["access_token"], founder["workspace_id"]),
    )
    assert added.status_code == status.HTTP_200_OK, added.text
    assert (await _workspace(auth_client, joiner, founder["workspace_id"])).status_code == (
        status.HTTP_200_OK
    )


@pytest.mark.asyncio
async def test_one_organization_refuses_another_tenant(auth_client):
    founder = await _register(auth_client, "solo@example.com")
    refused = await auth_client.post(
        "/api/v1/tenants",
        json={"name": "Second"},
        headers=_auth(founder["access_token"], founder["workspace_id"]),
    )
    assert refused.status_code == status.HTTP_403_FORBIDDEN

