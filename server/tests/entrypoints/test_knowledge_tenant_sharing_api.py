"""A knowledge base shared with the tenant is read, never changed, from its other workspaces."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi import status
from sqlmodel import select

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.knowledge.domain.models import KnowledgeIndex

pytestmark = pytest.mark.asyncio

HOME = "workspace-handbooks"


def _act_as(ctx: RequestContext, **changes: str | None) -> RequestContext:
    member = replace(ctx, tenant_role="Member", **changes)

    async def _override() -> RequestContext:
        return member

    app.dependency_overrides[get_current_context] = _override
    return member


async def _create(async_client, name: str, visibility: str) -> str:
    response = await async_client.post(
        "/api/v1/knowledge",
        json={
            "name": name,
            "knowledge_type": "document",
            "visibility": visibility,
            # An embedding model gives it the index a query needs.
            "default_embedding_model_ref": "model:test:embedder",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]["id"]


async def test_a_tenant_share_is_listed_opened_and_queried_but_not_changed_elsewhere(
    async_client, async_db, ctx
) -> None:
    _act_as(ctx, workspace_id=HOME, user_id="admin-alice", workspace_role="Admin")
    shared = await _create(async_client, "handbook", "tenant")
    local = await _create(async_client, "drafts", "workspace")

    # Indexed and ready, as a shared handbook would be.
    for index in (await async_db.exec(select(KnowledgeIndex))).all():
        index.status = "ready"
    await async_db.commit()

    _act_as(ctx, user_id="dev-bob", workspace_role="Dev")
    listed = await async_client.get("/api/v1/knowledge/shared")
    assert listed.status_code == status.HTTP_200_OK
    items = listed.json()["data"]["items"]
    assert [(item["id"], item["workspace_id"]) for item in items] == [(shared, HOME)]
    own = await async_client.get("/api/v1/knowledge")
    assert shared not in {item["id"] for item in own.json()["data"]["items"]}

    detail = await async_client.get(f"/api/v1/knowledge/{shared}")
    assert detail.status_code == status.HTTP_200_OK
    assert detail.json()["data"]["workspace_id"] == HOME
    assert (await async_client.get(f"/api/v1/knowledge/{shared}/documents")).status_code == 200
    queried = await async_client.post(
        f"/api/v1/knowledge/{shared}/query", json={"query": "leave policy", "top_k": 3}
    )
    assert queried.status_code == status.HTTP_200_OK, queried.text

    # The read is recorded where the data lives, against the reader.
    runs = (await async_db.exec(select(Run).where(Run.subject_id == shared))).all()
    assert runs
    assert {(run.workspace_id, run.user_id) for run in runs} == {(HOME, "dev-bob")}

    # A viewer opens it but, as at home, does not run retrieval.
    _act_as(ctx, user_id="viewer-erin", workspace_role="Viewer")
    assert (await async_client.get(f"/api/v1/knowledge/{shared}")).status_code == 200
    viewer_query = await async_client.post(
        f"/api/v1/knowledge/{shared}/query", json={"query": "leave policy", "top_k": 3}
    )
    assert viewer_query.status_code == status.HTTP_403_FORBIDDEN

    # Nothing changes it from here, and what is not shared stays out of sight.
    _act_as(ctx, user_id="dev-bob", workspace_role="Dev")
    changed = await async_client.put(f"/api/v1/knowledge/{shared}", json={"description": "mine now"})
    # A Dev deletes no knowledge base anywhere, so this one is refused sooner.
    removed = await async_client.delete(f"/api/v1/knowledge/{shared}")
    hidden = await async_client.get(f"/api/v1/knowledge/{local}")
    assert [changed.status_code, removed.status_code, hidden.status_code] == [404, 403, 404]
    unchanged = await async_client.get(f"/api/v1/knowledge/{shared}")
    assert unchanged.json()["data"]["description"] != "mine now"


async def test_other_tenants_never_see_a_tenant_share(async_client, ctx) -> None:
    _act_as(ctx, workspace_id=HOME, user_id="admin-alice", workspace_role="Admin")
    shared = await _create(async_client, "handbook", "tenant")

    _act_as(ctx, tenant_id="another-tenant", workspace_id="their-workspace", workspace_role="Admin")
    listed = await async_client.get("/api/v1/knowledge/shared")

    assert listed.json()["data"]["items"] == []
    assert (await async_client.get(f"/api/v1/knowledge/{shared}")).status_code == 404


async def test_only_workspace_owners_and_admins_share_with_the_tenant(async_client, ctx) -> None:
    _act_as(ctx, user_id="dev-alice", workspace_role="Dev")
    refused = await async_client.post(
        "/api/v1/knowledge",
        json={"name": "notes", "knowledge_type": "document", "visibility": "tenant"},
    )
    assert refused.status_code == status.HTTP_403_FORBIDDEN
    knowledge_id = await _create(async_client, "notes", "workspace")
    promoted = await async_client.put(f"/api/v1/knowledge/{knowledge_id}", json={"visibility": "tenant"})
    assert promoted.status_code == status.HTTP_403_FORBIDDEN

    _act_as(ctx, user_id="admin-carol", workspace_role="Admin")
    shared = await async_client.put(f"/api/v1/knowledge/{knowledge_id}", json={"visibility": "tenant"})
    assert shared.status_code == status.HTTP_200_OK
    assert shared.json()["data"]["visibility"] == "tenant"
