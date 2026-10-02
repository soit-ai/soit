"""The document restriction routes: who may set one, and what a reader is told."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi import status

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import (
    register_resource_grant_provider,
    reset_resource_grant_provider,
)
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.knowledge.domain.models import KnowledgeDocument

pytestmark = pytest.mark.asyncio


class _NoGrants:
    """No member holds a grant; the real lookup opens a session of its own."""

    async def allows_resource_action(self, **kwargs) -> bool:
        del kwargs
        return False


@pytest.fixture(autouse=True)
def _reset_grants():
    yield
    reset_resource_grant_provider()


def _act_as(ctx: RequestContext, user_id: str, role: str) -> None:
    member = replace(ctx, user_id=user_id, workspace_role=role, tenant_role="Member")
    app.dependency_overrides[get_current_context] = lambda: member


async def _base_with_document(async_client, async_db, ctx: RequestContext) -> str:
    created = await async_client.post("/api/v1/knowledge", json={"name": "Handbook", "knowledge_type": "document"})
    knowledge_id = created.json()["data"]["id"]
    async_db.add(
        KnowledgeDocument(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            knowledge_id=knowledge_id,
            doc_key="payroll",
            version=1,
            is_latest=True,
            status="indexed",
            source_kind="upload",
            title="Payroll",
            created_by=ctx.user_id,
        )
    )
    await async_db.commit()
    return knowledge_id


async def test_an_admin_restricts_a_document_and_a_member_is_not_told(async_client, async_db, ctx) -> None:
    knowledge_id = await _base_with_document(async_client, async_db, ctx)
    path = f"/api/v1/knowledge/{knowledge_id}/document-restrictions"

    restricted = await async_client.put(path, json={"doc_key": "payroll", "restricted": True})
    assert restricted.status_code == status.HTTP_200_OK, restricted.text
    [row] = restricted.json()["data"]
    assert (row["doc_key"], row["grant_resource_id"]) == ("payroll", f"{knowledge_id}:payroll")

    # Registered after the app has wired its own provider on the first request.
    register_resource_grant_provider(_NoGrants())
    _act_as(ctx, "dev-1", "Dev")
    try:
        listed = await async_client.get(path)
        lifted = await async_client.put(path, json={"doc_key": "payroll", "restricted": False})
        documents = await async_client.get(f"/api/v1/knowledge/{knowledge_id}/documents")
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    assert listed.json()["data"] == []
    assert lifted.status_code == status.HTTP_403_FORBIDDEN
    data = documents.json()["data"]
    assert (data["items"] if isinstance(data, dict) else data) == []

    missing = await async_client.put(path, json={"doc_key": "nothing", "restricted": True})
    assert missing.status_code == status.HTTP_404_NOT_FOUND
