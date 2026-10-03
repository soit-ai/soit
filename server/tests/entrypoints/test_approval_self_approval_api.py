"""A workspace can stop requesters approving their own approval requests.

The switch is a workspace admin's call. Once on, whoever opened a request is
refused approving it on every path, the chat client's resume included, and is
told so by ``can_approve``; they may still reject or cancel it, and another
approver still approves it.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from fastapi import status

from app.kernel.commons.errors import ForbiddenError
from app.kernel.contracts.context import RequestContext
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.identity.domain.models import Tenant, Workspace
from app.modules.observe.application.schemas import ApprovalResolve
from app.wiring.services import build_observe_service

pytestmark = pytest.mark.asyncio


def _as(ctx: RequestContext, user_id: str, workspace_role: str = "Dev", tenant_role: str | None = "Member") -> None:
    caller = dataclasses.replace(ctx, user_id=user_id, workspace_role=workspace_role, tenant_role=tenant_role)
    app.dependency_overrides[get_current_context] = lambda: caller


async def _workspace(async_db, ctx: RequestContext) -> None:
    async_db.add(Tenant(id=ctx.tenant_id, name="tenant"))
    async_db.add(Workspace(id=ctx.workspace_id, tenant_id=ctx.tenant_id, name="workspace"))
    await async_db.commit()


async def _set(async_client, ctx: RequestContext, value: bool, **roles: Any):
    _as(ctx, "u_setter", **roles)
    try:
        return await async_client.patch(
            f"/api/v1/workspaces/{ctx.workspace_id}",
            json={"forbid_self_approval": value},
            headers={"X-Workspace-Id": ctx.workspace_id},
        )
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx


async def _open(async_client, ctx: RequestContext, requester: str) -> str:
    _as(ctx, requester)
    response = await async_client.post("/api/v1/observe/approvals", json={"title": "Send the refund"})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]["id"]


async def test_only_a_workspace_admin_turns_it_on(async_client, async_db, ctx) -> None:
    await _workspace(async_db, ctx)

    developer = await _set(async_client, ctx, True, workspace_role="Dev", tenant_role=None)
    admin = await _set(async_client, ctx, True, workspace_role="Admin", tenant_role=None)
    off = await _set(async_client, ctx, False, workspace_role="Admin", tenant_role=None)

    assert developer.status_code == 400
    assert admin.status_code == 200 and admin.json()["data"]["forbid_self_approval"] is True
    assert off.json()["data"]["forbid_self_approval"] is False
    stored = await async_db.get(Workspace, ctx.workspace_id)
    await async_db.refresh(stored)
    assert stored.forbid_self_approval is None


async def test_a_requester_may_not_approve_their_own_request(async_client, async_db, ctx) -> None:
    await _workspace(async_db, ctx)
    allowed_before = await _open(async_client, ctx, "u_alice")
    assert (await async_client.get(f"/api/v1/observe/approvals/{allowed_before}")).json()["data"]["can_approve"]

    await _set(async_client, ctx, True, workspace_role="Admin")
    own = await _open(async_client, ctx, "u_alice")
    rejected_own = await _open(async_client, ctx, "u_alice")

    _as(ctx, "u_alice")
    seen = (await async_client.get(f"/api/v1/observe/approvals/{own}")).json()["data"]
    approve_own = await async_client.post(f"/api/v1/observe/approvals/{own}/resolve", json={"status": "approved"})
    reject_own = await async_client.post(
        f"/api/v1/observe/approvals/{rejected_own}/resolve", json={"status": "rejected"}
    )
    _as(ctx, "u_bob")
    seen_by_bob = (await async_client.get(f"/api/v1/observe/approvals/{own}")).json()["data"]
    approve_by_bob = await async_client.post(f"/api/v1/observe/approvals/{own}/resolve", json={"status": "approved"})

    assert (seen["can_decide"], seen["can_approve"], seen["can_cancel"]) == (True, False, True)
    assert approve_own.status_code == status.HTTP_403_FORBIDDEN
    assert "does not let requesters approve their own" in approve_own.json()["message"]
    assert reject_own.status_code == status.HTTP_200_OK
    assert seen_by_bob["can_approve"] is True
    assert approve_by_bob.status_code == status.HTTP_200_OK


async def test_the_chat_clients_resume_obeys_it_too(async_client, async_db, ctx) -> None:
    await _workspace(async_db, ctx)
    await _set(async_client, ctx, True, workspace_role="Admin")
    approval_id = await _open(async_client, ctx, "u_alice")
    alice = dataclasses.replace(ctx, user_id="u_alice", workspace_role="Dev", tenant_role="Member")

    service = build_observe_service(db=async_db, ctx=alice)
    with pytest.raises(ForbiddenError):
        await service.resolve_approvals([(approval_id, ApprovalResolve(status="approved"))])
    await async_db.rollback()
    [rejected] = await build_observe_service(db=async_db, ctx=alice).resolve_approvals(
        [(approval_id, ApprovalResolve(status="rejected"))]
    )
    assert rejected.status == "rejected"
