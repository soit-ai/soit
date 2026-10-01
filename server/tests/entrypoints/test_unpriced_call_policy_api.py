"""A workspace decides what calls with no price do; the gateways refuse them by its policy."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from app.kernel.contracts.context import RequestContext
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.identity.domain.models import Tenant, Workspace

CHAT = {"model": "model:test:chat", "messages": [{"role": "user", "content": "hello"}]}


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


async def _workspace(async_db, ctx: RequestContext) -> None:
    async_db.add(Tenant(id=ctx.tenant_id, name="tenant"))
    async_db.add(Workspace(id=ctx.workspace_id, tenant_id=ctx.tenant_id, name="workspace"))
    await async_db.commit()


@pytest.mark.asyncio
async def test_the_policy_is_a_workspace_admins_call(async_client, async_db, ctx) -> None:
    await _workspace(async_db, ctx)

    developer = await _patch(
        async_client, ctx, {"unpriced_call_policy": "refuse"}, tenant_role=None, workspace_role="Dev"
    )
    assert developer.status_code == 400

    admin = await _patch(
        async_client, ctx, {"unpriced_call_policy": "refuse_when_budgeted"}, tenant_role=None, workspace_role="Admin"
    )
    assert admin.status_code == 200
    assert admin.json()["data"]["unpriced_call_policy"] == "refuse_when_budgeted"

    allowed = await _patch(async_client, ctx, {"unpriced_call_policy": "allow"}, workspace_role="Admin")
    assert allowed.json()["data"]["unpriced_call_policy"] == "allow"
    stored = await async_db.get(Workspace, ctx.workspace_id)
    await async_db.refresh(stored)
    assert stored.unpriced_call_policy is None

    unknown = await _patch(async_client, ctx, {"unpriced_call_policy": "sometimes"}, workspace_role="Admin")
    assert unknown.status_code == 400


@pytest.mark.asyncio
async def test_a_workspace_that_refuses_unpriced_calls_answers_each_gateway_in_its_shape(
    async_client, async_db, ctx
) -> None:
    await _workspace(async_db, ctx)

    # The test model has no price: allowed until the workspace says otherwise.
    assert (await async_client.post("/v1/chat/completions", json=CHAT)).status_code == 200

    await _patch(async_client, ctx, {"unpriced_call_policy": "refuse"}, workspace_role="Admin")

    openai = await async_client.post("/v1/chat/completions", json=CHAT)
    assert openai.status_code == 403
    error = openai.json()["error"]
    assert (error["type"], error["code"]) == ("permission_error", "pricing_not_configured")
    assert "model:test:chat" in error["message"]

    anthropic = await async_client.post(
        "/v1/messages",
        json={"model": "model:test:chat", "max_tokens": 16, "messages": [{"role": "user", "content": "hello"}]},
    )
    assert anthropic.status_code == 403
    assert anthropic.json()["type"] == "error"
    assert anthropic.json()["error"]["type"] == "permission_error"

    platform = await async_client.post("/v1/chat/completions", json={**CHAT, "stream": True})
    assert platform.status_code == 403
