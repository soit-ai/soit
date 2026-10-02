"""A member cannot grant themselves access, nor point a document at another base's file.

Both would reach past knowledge base visibility: a grant opens a private
resource to its holder, and a document's ``file_id`` is the storage key it is
downloaded from.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi import status

from app.kernel.contracts.context import RequestContext
from app.main import app
from app.middleware.auth import get_current_context

pytestmark = pytest.mark.asyncio


def _act_as(ctx: RequestContext, user_id: str, role: str) -> None:
    member = replace(ctx, user_id=user_id, workspace_role=role, tenant_role="Member")

    async def _override() -> RequestContext:
        return member

    app.dependency_overrides[get_current_context] = _override


async def _create(async_client, name: str, visibility: str = "workspace") -> str:
    response = await async_client.post(
        "/api/v1/knowledge", json={"name": name, "knowledge_type": "document", "visibility": visibility}
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]["id"]


GRANT = {"resource_type": "knowledge", "resource_id": "kb-private", "user_id": "dev-1", "actions": ["*"]}


@pytest.mark.parametrize("role", ["Dev", "Viewer"])
async def test_a_member_cannot_grant_themselves_access(async_client, ctx, role) -> None:
    _act_as(ctx, "dev-1", role)
    try:
        created = await async_client.post("/api/v1/resource-grants", json=GRANT)
        revoked = await async_client.delete("/api/v1/resource-grants/knowledge/kb-private/dev-1")
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    assert created.status_code == status.HTTP_403_FORBIDDEN
    assert revoked.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("role", ["Owner", "Admin"])
async def test_a_workspace_admin_grants_and_revokes(async_client, ctx, role) -> None:
    _act_as(ctx, "admin-1", role)
    try:
        created = await async_client.post("/api/v1/resource-grants", json=GRANT)
        revoked = await async_client.delete("/api/v1/resource-grants/knowledge/kb-private/dev-1")
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    assert created.status_code == status.HTTP_200_OK, created.text
    assert revoked.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT), revoked.text


async def test_a_document_cannot_name_another_bases_file(async_client, ctx) -> None:
    private_id = await _create(async_client, "Payroll", "private")
    open_id = await _create(async_client, "Handbook")
    stolen = f"tenants/{ctx.tenant_id}/workspaces/{ctx.workspace_id}/knowledge/{private_id}/raw/01PAYROLL"

    _act_as(ctx, "dev-1", "Dev")
    try:
        responses = [
            await async_client.post(
                f"/api/v1/knowledge/{open_id}/documents",
                data={"doc_key": "copy", "source_kind": "upload", "file_id": file_id, "async_ingest": "false"},
            )
            for file_id in (stolen, "tenants/other/workspaces/x/knowledge/y/raw/z", f"../{private_id}/raw/1")
        ]
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    for response in responses:
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert "file_id" in response.json()["message"]
