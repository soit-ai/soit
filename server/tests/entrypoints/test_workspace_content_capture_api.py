"""A workspace admin can keep less of run content; keeping it again takes the tenant."""

from __future__ import annotations

import dataclasses

import pytest

from app.kernel.contracts.context import RequestContext
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.identity.domain.models import Tenant, Workspace


async def _patch(async_client, ctx: RequestContext, mode: str, **roles: str | None):
    caller = dataclasses.replace(ctx, **roles)
    app.dependency_overrides[get_current_context] = lambda: caller
    try:
        return await async_client.patch(
            f"/api/v1/workspaces/{ctx.workspace_id}",
            json={"content_capture": mode},
            headers={"X-Workspace-Id": ctx.workspace_id},
        )
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx


@pytest.mark.asyncio
async def test_content_capture_changes_by_direction(async_client, async_db, ctx) -> None:
    async_db.add(Tenant(id=ctx.tenant_id, name="tenant"))
    async_db.add(Workspace(id=ctx.workspace_id, tenant_id=ctx.tenant_id, name="workspace"))
    await async_db.commit()

    developer = await _patch(async_client, ctx, "metadata_only", tenant_role=None, workspace_role="Dev")
    assert developer.status_code == 400

    admin = await _patch(async_client, ctx, "metadata_only", tenant_role=None, workspace_role="Admin")
    assert admin.status_code == 200
    assert admin.json()["data"]["content_capture"] == "metadata_only"

    loosen = await _patch(async_client, ctx, "full", tenant_role=None, workspace_role="Admin")
    assert loosen.status_code == 400

    tenant_admin = await _patch(async_client, ctx, "full", tenant_role="Admin", workspace_role="Admin")
    assert tenant_admin.status_code == 200
    assert tenant_admin.json()["data"]["content_capture"] == "full"
