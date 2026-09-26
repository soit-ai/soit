"""Knowledge visibility is enforced at the API.

Each test acts as several workspace members by swapping the request context
the app resolves: a private knowledge base must stay out of reach for members
who neither created it nor administer the workspace, in listings as well as
on direct access, unless a resource grant names them.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi import status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import (
    register_resource_grant_provider,
    reset_resource_grant_provider,
)
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.identity.domain.models import ResourceGrant

pytestmark = pytest.mark.asyncio


def _act_as(ctx: RequestContext, user_id: str, role: str) -> RequestContext:
    member = replace(ctx, user_id=user_id, workspace_role=role, tenant_role="Member")

    async def _override() -> RequestContext:
        return member

    app.dependency_overrides[get_current_context] = _override
    return member


async def _create(async_client, name: str, visibility: str | None) -> str:
    payload: dict[str, object] = {"name": name, "knowledge_type": "document"}
    if visibility is not None:
        payload["visibility"] = visibility
    response = await async_client.post("/api/v1/knowledge", json=payload)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]["id"]


async def _listed_ids(async_client) -> set[str]:
    response = await async_client.get("/api/v1/knowledge")
    assert response.status_code == status.HTTP_200_OK
    return {item["id"] for item in response.json()["data"]["items"]}


class _DbGrants:
    """Resource grants read from the test database session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def allows_resource_action(
        self,
        *,
        ctx: RequestContext,
        resource_type: str,
        resource_id: str,
        action: str,
        effective_action: str,
    ) -> bool:
        from sqlmodel import select

        rows = (
            await self.db.exec(
                select(ResourceGrant).where(
                    ResourceGrant.tenant_id == ctx.tenant_id,
                    ResourceGrant.workspace_id == ctx.workspace_id,
                    ResourceGrant.resource_type == resource_type,
                    ResourceGrant.resource_id == resource_id,
                    ResourceGrant.user_id == ctx.user_id,
                )
            )
        ).all()
        for row in rows:
            grant = row if isinstance(row, ResourceGrant) else row[0]
            actions = {str(item).lower() for item in (grant.actions or [])}
            if "*" in actions or action in actions or effective_action in actions:
                return True
        return False


async def test_new_knowledge_defaults_to_workspace_visibility(async_client, ctx) -> None:
    _act_as(ctx, "dev-alice", "Dev")
    knowledge_id = await _create(async_client, "vis-default", None)

    detail = await async_client.get(f"/api/v1/knowledge/{knowledge_id}")
    assert detail.json()["data"]["visibility"] == "workspace"

    _act_as(ctx, "dev-bob", "Dev")
    assert knowledge_id in await _listed_ids(async_client)
    assert (await async_client.get(f"/api/v1/knowledge/{knowledge_id}")).status_code == 200


async def test_private_knowledge_is_out_of_reach_for_other_members(async_client, ctx) -> None:
    _act_as(ctx, "dev-alice", "Dev")
    private_id = await _create(async_client, "vis-private", "private")
    shared_id = await _create(async_client, "vis-shared", "workspace")

    # The creator keeps full sight of their own knowledge base.
    assert {private_id, shared_id} <= await _listed_ids(async_client)
    assert (await async_client.get(f"/api/v1/knowledge/{private_id}")).status_code == 200

    for role in ("Dev", "Viewer"):
        _act_as(ctx, f"{role.lower()}-bob", role)
        listed = await _listed_ids(async_client)
        assert private_id not in listed
        assert shared_id in listed

        denied = [
            await async_client.get(f"/api/v1/knowledge/{private_id}"),
            await async_client.get(f"/api/v1/knowledge/{private_id}/documents"),
            await async_client.get(f"/api/v1/knowledge/{private_id}/runs"),
            await async_client.get(f"/api/v1/knowledge/{private_id}/retrieval/summary"),
            await async_client.post(
                f"/api/v1/knowledge/{private_id}/query", json={"query": "anything", "top_k": 3}
            ),
        ]
        assert [response.status_code for response in denied] == [403] * len(denied)

        items = await async_client.get("/api/v1/knowledge/workbench/items")
        assert items.status_code == 200
        assert private_id not in {row["id"] for row in items.json()["data"]["items"]}

        search = await async_client.get("/api/v1/search", params={"q": "vis-private"})
        assert search.status_code == 200
        assert private_id not in {hit.get("id") for hit in search.json()["data"]["items"]}


@pytest.mark.parametrize("role", ["Owner", "Admin"])
async def test_owners_and_admins_see_private_knowledge(async_client, ctx, role: str) -> None:
    _act_as(ctx, "dev-alice", "Dev")
    private_id = await _create(async_client, f"vis-admin-{role}", "private")

    _act_as(ctx, f"{role.lower()}-carol", role)
    assert private_id in await _listed_ids(async_client)
    assert (await async_client.get(f"/api/v1/knowledge/{private_id}")).status_code == 200


async def test_a_resource_grant_opens_private_knowledge(async_client, async_db, ctx) -> None:
    _act_as(ctx, "dev-alice", "Dev")
    private_id = await _create(async_client, "vis-granted", "private")
    async_db.add(
        ResourceGrant(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            resource_type="knowledge",
            resource_id=private_id,
            user_id="viewer-dan",
            actions=["read"],
            created_by="dev-alice",
        )
    )
    await async_db.flush()
    register_resource_grant_provider(_DbGrants(async_db))
    try:
        _act_as(ctx, "viewer-dan", "Viewer")
        assert private_id in await _listed_ids(async_client)
        assert (await async_client.get(f"/api/v1/knowledge/{private_id}")).status_code == 200

        _act_as(ctx, "viewer-erin", "Viewer")
        assert private_id not in await _listed_ids(async_client)
    finally:
        reset_resource_grant_provider()


async def test_only_the_creator_or_an_admin_changes_visibility(async_client, ctx) -> None:
    _act_as(ctx, "dev-alice", "Dev")
    knowledge_id = await _create(async_client, "vis-change", "workspace")

    _act_as(ctx, "dev-bob", "Dev")
    refused = await async_client.put(
        f"/api/v1/knowledge/{knowledge_id}", json={"visibility": "private"}
    )
    assert refused.status_code == status.HTTP_403_FORBIDDEN
    # Other edits by a Dev stay allowed on a workspace knowledge base.
    edited = await async_client.put(
        f"/api/v1/knowledge/{knowledge_id}", json={"description": "edited by bob"}
    )
    assert edited.status_code == status.HTTP_200_OK

    _act_as(ctx, "dev-alice", "Dev")
    made_private = await async_client.put(
        f"/api/v1/knowledge/{knowledge_id}", json={"visibility": "private"}
    )
    assert made_private.status_code == status.HTTP_200_OK
    assert made_private.json()["data"]["visibility"] == "private"

    _act_as(ctx, "dev-bob", "Dev")
    assert (await async_client.get(f"/api/v1/knowledge/{knowledge_id}")).status_code == 403
