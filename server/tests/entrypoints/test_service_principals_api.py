"""Service principals are set up by workspace admins and act through their keys."""

from __future__ import annotations

import dataclasses

import pytest
import pytest_asyncio

from app.kernel.contracts.context import RequestContext
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.identity.domain.models import WorkspaceMembership

BASE = "/api/v1/service-principals"


@pytest_asyncio.fixture
async def owner_membership(async_db, ctx: RequestContext) -> None:
    async_db.add(
        WorkspaceMembership(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            role="Admin",
        )
    )
    async_db.add(
        WorkspaceMembership(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id="dev-member",
            role="Dev",
        )
    )
    await async_db.commit()


def _as(ctx: RequestContext, **changes) -> None:
    caller = dataclasses.replace(ctx, **changes)
    app.dependency_overrides[get_current_context] = lambda: caller


@pytest.mark.asyncio
@pytest.mark.usefixtures("owner_membership")
async def test_an_admin_sets_up_a_principal_and_issues_it_a_key(async_client) -> None:
    created = await async_client.post(BASE, json={"name": "nightly-etl", "workspace_role": "Dev"})
    assert created.status_code == 201
    principal = created.json()["data"]
    assert principal["id"].startswith("sp_")
    assert principal["owner_user_id"] == "test-user"

    issued = await async_client.post(
        "/api/v1/api-keys",
        json={"name": "etl key", "scopes": ["write"], "expires_in_days": 30, "principal_id": principal["id"]},
    )
    assert issued.status_code == 200
    assert issued.json()["data"]["item"]["principal_id"] == principal["id"]

    listed = (await async_client.get(BASE)).json()["data"]
    assert [item["name"] for item in listed] == ["nightly-etl"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("owner_membership")
async def test_a_principal_cannot_hold_more_than_its_owner(async_client) -> None:
    refused = await async_client.post(
        BASE,
        json={"name": "too-strong", "workspace_role": "Admin", "owner_user_id": "dev-member"},
    )
    assert refused.status_code == 400

    stranger = await async_client.post(
        BASE, json={"name": "orphan", "workspace_role": "Viewer", "owner_user_id": "not-a-member"}
    )
    assert stranger.status_code == 400


@pytest.mark.asyncio
@pytest.mark.usefixtures("owner_membership")
async def test_developers_cannot_set_up_principals_or_issue_them_keys(async_client, ctx) -> None:
    principal_id = (await async_client.post(BASE, json={"name": "bot"})).json()["data"]["id"]

    _as(ctx, user_id="dev-member", workspace_role="Dev", tenant_role=None)
    try:
        create = await async_client.post(BASE, json={"name": "dev-bot"})
        issue = await async_client.post(
            "/api/v1/api-keys",
            json={"name": "k", "scopes": ["read"], "expires_in_days": 1, "principal_id": principal_id},
        )
        listed = await async_client.get(BASE)
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    assert create.status_code == 403
    assert issue.status_code == 403
    assert listed.status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("owner_membership")
async def test_a_principal_is_disabled_renamed_and_removed(async_client) -> None:
    principal_id = (await async_client.post(BASE, json={"name": "bot"})).json()["data"]["id"]

    changed = await async_client.patch(
        f"{BASE}/{principal_id}", json={"name": "renamed-bot", "status": "disabled"}
    )
    assert changed.status_code == 200
    assert (changed.json()["data"]["name"], changed.json()["data"]["status"]) == ("renamed-bot", "disabled")

    issue = await async_client.post(
        "/api/v1/api-keys",
        json={"name": "k", "scopes": ["read"], "expires_in_days": 1, "principal_id": principal_id},
    )
    assert issue.status_code == 400

    assert (await async_client.delete(f"{BASE}/{principal_id}")).status_code == 204
    assert (await async_client.get(f"{BASE}/{principal_id}")).status_code == 404
