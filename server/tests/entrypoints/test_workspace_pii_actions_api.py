"""A workspace sets how personal data is handled; loosening takes the tenant."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from app.kernel.contracts.context import RequestContext
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.identity.domain.models import Tenant, Workspace
from app.settings.settings import settings


async def _patch(async_client, ctx: RequestContext, body: dict[str, Any], **roles: str | None):
    caller = dataclasses.replace(ctx, **roles)
    app.dependency_overrides[get_current_context] = lambda: caller
    try:
        return await async_client.patch(
            f"/api/v1/workspaces/{ctx.workspace_id}",
            json=body,
            headers={"X-Workspace-Id": ctx.workspace_id},
        )
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx


@pytest.fixture
def builtin_safety(monkeypatch) -> None:
    monkeypatch.setattr(settings, "content_safety_enabled", True)
    monkeypatch.setattr(settings, "content_safety_provider", "builtin")
    monkeypatch.setattr(settings, "content_safety_pii_action", "redact")


async def _workspace(async_db, ctx: RequestContext) -> None:
    async_db.add(Tenant(id=ctx.tenant_id, name="tenant"))
    async_db.add(Workspace(id=ctx.workspace_id, tenant_id=ctx.tenant_id, name="workspace"))
    await async_db.commit()


@pytest.mark.asyncio
@pytest.mark.usefixtures("builtin_safety")
async def test_pii_actions_change_by_direction_of_strictness(async_client, async_db, ctx) -> None:
    await _workspace(async_db, ctx)

    developer = await _patch(
        async_client, ctx, {"pii_action_inbound": "block"}, tenant_role=None, workspace_role="Dev"
    )
    assert developer.status_code == 400

    admin = await _patch(
        async_client, ctx, {"pii_action_inbound": "block"}, tenant_role=None, workspace_role="Admin"
    )
    assert admin.status_code == 200
    data = admin.json()["data"]
    assert (data["pii_action_inbound"], data["pii_action_outbound"]) == ("block", None)
    assert data["pii_action_default"] == "redact"

    # Below the deployment's redact is looser: a tenant decision.
    loosen = await _patch(
        async_client, ctx, {"pii_action_outbound": "observe"}, tenant_role=None, workspace_role="Admin"
    )
    assert loosen.status_code == 400
    tenant_admin = await _patch(
        async_client, ctx, {"pii_action_outbound": "observe"}, tenant_role="Admin", workspace_role="Admin"
    )
    assert tenant_admin.status_code == 200
    assert tenant_admin.json()["data"]["pii_action_outbound"] == "observe"

    # Null returns a direction to the deployment, and is never a loosening.
    cleared = await _patch(
        async_client, ctx, {"pii_action_outbound": None}, tenant_role=None, workspace_role="Admin"
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["pii_action_outbound"] is None
    assert cleared.json()["data"]["pii_action_inbound"] == "block"


@pytest.mark.asyncio
@pytest.mark.usefixtures("builtin_safety")
async def test_a_workspace_that_blocks_personal_data_refuses_the_call(
    async_client, async_db, ctx
) -> None:
    await _workspace(async_db, ctx)
    body = {
        "model": "model:test:chat",
        "messages": [{"role": "user", "content": "email grace@example.com the invoice"}],
    }

    before = await async_client.post("/v1/chat/completions", json=body)
    assert before.status_code == 200
    # The deployment redacts: the model never saw the address.
    assert "grace@example.com" not in before.json()["choices"][0]["message"]["content"]

    await _patch(async_client, ctx, {"pii_action_inbound": "block"}, workspace_role="Admin")
    refused = await async_client.post("/v1/chat/completions", json=body)

    assert refused.status_code == 403
    assert refused.json()["error"]["type"] == "permission_error"
