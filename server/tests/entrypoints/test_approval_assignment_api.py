"""Who decides an approval request: assignees, roles read now, delegation, history.

A request with no assignees is decided by any member who can write, as
before. An assigned request is decided only by an assigned member or a
current holder of an assigned role; a member who loses the role or the
membership can no longer decide it. An approver can delegate the request to
another member who can decide, and every decision, closing and delegation is
kept in the request's history.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from fastapi import status

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.workspace_access import WorkspaceAccess
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.observe.application.service import ObserveService
from app.wiring.services import build_observe_service

pytestmark = pytest.mark.asyncio

MEMBERS = {"u_alice": "Dev", "u_bob": "Dev", "u_carol": "Dev", "u_admin": "Admin", "u_viewer": "Viewer"}


class _Members:
    """The workspace's members, as the identity module would answer."""

    async def resolve(self, tenant_id, workspace_id, user_id, session_id=None):
        del tenant_id, workspace_id, session_id
        role = MEMBERS.get(user_id)
        return WorkspaceAccess(tenant_role="Member", workspace_role=role) if role else None


@pytest.fixture(autouse=True)
def _members(monkeypatch):
    def _build(*, db, ctx):
        return ObserveService(db=db, ctx=ctx, member_access=_Members())

    monkeypatch.setattr("app.api.v1.observe.dependencies.build_observe_service", _build)
    yield
    monkeypatch.setattr("app.api.v1.observe.dependencies.build_observe_service", build_observe_service)


@pytest.fixture
def act_as(ctx: RequestContext):
    def _act(user_id: str, role: str | None = None) -> None:
        member = replace(ctx, user_id=user_id, workspace_role=role or MEMBERS[user_id], tenant_role="Member")
        app.dependency_overrides[get_current_context] = lambda: member

    yield _act
    app.dependency_overrides[get_current_context] = lambda: ctx


async def _create(async_client, **body) -> str:
    response = await async_client.post("/api/v1/observe/approvals", json={"title": "Send the refund", **body})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]["id"]


async def _resolve(async_client, approval_id: str, decision: str):
    return await async_client.post(f"/api/v1/observe/approvals/{approval_id}/resolve", json={"status": decision})


async def _history(async_client, approval_id: str) -> list[tuple]:
    response = await async_client.get(f"/api/v1/observe/approvals/{approval_id}/decisions")
    assert response.status_code == status.HTTP_200_OK, response.text
    return [(item["action"], item["actor_id"]) for item in response.json()["data"]]


async def test_an_unassigned_request_is_decided_by_any_writer(async_client, act_as) -> None:
    approval_id = await _create(async_client)

    act_as("u_bob")
    response = await _resolve(async_client, approval_id, "approved")

    assert response.status_code == status.HTTP_200_OK, response.text
    assert await _history(async_client, approval_id) == [("approved", "u_bob")]


async def test_only_an_assigned_member_decides(async_client, act_as) -> None:
    approval_id = await _create(async_client, assignee_user_ids=["u_alice"])

    act_as("u_bob")
    refused = await _resolve(async_client, approval_id, "approved")
    act_as("u_admin")
    refused_admin = await _resolve(async_client, approval_id, "rejected")
    act_as("u_alice")
    decided = await _resolve(async_client, approval_id, "approved")

    assert refused.status_code == refused_admin.status_code == status.HTTP_403_FORBIDDEN
    assert decided.status_code == status.HTTP_200_OK, decided.text
    assert decided.json()["data"]["assignee_user_ids"] == ["u_alice"]
    assert await _history(async_client, approval_id) == [("approved", "u_alice")]


async def test_an_assigned_role_is_read_when_deciding(async_client, act_as) -> None:
    approval_id = await _create(async_client, assignee_roles=["admin"])

    act_as("u_admin", role="Dev")  # demoted since the request was made
    demoted = await _resolve(async_client, approval_id, "approved")
    act_as("u_admin", role="Admin")
    decided = await _resolve(async_client, approval_id, "approved")

    assert demoted.status_code == status.HTTP_403_FORBIDDEN
    assert decided.status_code == status.HTTP_200_OK, decided.text
    assert decided.json()["data"]["assignee_roles"] == ["Admin"]


async def test_the_requester_or_an_admin_cancels_but_does_not_approve(async_client, act_as) -> None:
    act_as("u_bob")
    approval_id = await _create(async_client, assignee_user_ids=["u_alice"])

    approved = await _resolve(async_client, approval_id, "approved")
    act_as("u_carol")
    canceled_by_other = await _resolve(async_client, approval_id, "canceled")
    act_as("u_bob")
    canceled = await _resolve(async_client, approval_id, "canceled")

    assert approved.status_code == canceled_by_other.status_code == status.HTTP_403_FORBIDDEN
    assert canceled.status_code == status.HTTP_200_OK, canceled.text
    assert await _history(async_client, approval_id) == [("canceled", "u_bob")]


async def test_an_approver_delegates_and_the_chain_is_kept(async_client, act_as) -> None:
    approval_id = await _create(async_client, assignee_user_ids=["u_alice"], assignee_roles=["Admin"])
    path = f"/api/v1/observe/approvals/{approval_id}/delegate"

    act_as("u_bob")
    not_an_approver = await async_client.post(path, json={"user_id": "u_carol"})
    act_as("u_alice")
    to_a_stranger = await async_client.post(path, json={"user_id": "u_mallory"})
    to_a_viewer = await async_client.post(path, json={"user_id": "u_viewer"})
    to_herself = await async_client.post(path, json={"user_id": "u_alice"})
    delegated = await async_client.post(path, json={"user_id": "u_carol", "note": "out this week"})
    after_handing_it_on = await _resolve(async_client, approval_id, "approved")
    act_as("u_carol")
    decided = await _resolve(async_client, approval_id, "rejected")
    closed = await async_client.post(path, json={"user_id": "u_bob"})

    assert not_an_approver.status_code == status.HTTP_403_FORBIDDEN
    assert [to_a_stranger.status_code, to_a_viewer.status_code, to_herself.status_code] == [400, 400, 400]
    assert delegated.status_code == status.HTTP_200_OK, delegated.text
    assert (delegated.json()["data"]["assignee_user_ids"], delegated.json()["data"]["assignee_roles"]) == (["u_carol"], [])
    assert after_handing_it_on.status_code == status.HTTP_403_FORBIDDEN
    assert decided.status_code == status.HTTP_200_OK
    assert closed.status_code == status.HTTP_409_CONFLICT
    history = (await async_client.get(f"/api/v1/observe/approvals/{approval_id}/decisions")).json()["data"]
    assert [(item["action"], item["actor_id"]) for item in history] == [("delegated", "u_alice"), ("rejected", "u_carol")]
    assert history[0]["assignees_before_json"] == {"user_ids": ["u_alice"], "roles": ["Admin"]}
    assert history[0]["assignees_after_json"] == {"user_ids": ["u_carol"], "roles": []}
    assert history[0]["note"] == "out this week"


async def test_a_request_is_made_with_valid_assignees_and_a_future_deadline(async_client) -> None:
    viewer_role = await async_client.post(
        "/api/v1/observe/approvals", json={"title": "t", "assignee_roles": ["Viewer"]}
    )
    past = await async_client.post(
        "/api/v1/observe/approvals", json={"title": "t", "expires_at": (utc_now() - timedelta(minutes=1)).isoformat()}
    )
    deadline = (utc_now() + timedelta(hours=1)).replace(microsecond=0)
    made = await async_client.post(
        "/api/v1/observe/approvals",
        json={"title": "t", "assignee_user_ids": ["u_alice", "u_alice"], "expires_at": deadline.isoformat()},
    )

    assert viewer_role.status_code == past.status_code == status.HTTP_400_BAD_REQUEST
    assert made.status_code == status.HTTP_201_CREATED, made.text
    assert made.json()["data"]["assignee_user_ids"] == ["u_alice"]
    assert made.json()["data"]["expires_at"].startswith(deadline.replace(tzinfo=None).isoformat())


async def test_a_client_resume_obeys_the_assignment_too(async_db, ctx) -> None:
    """The chat client's resume decides through the batch path; it checks the same rule."""

    from app.kernel.commons.errors import ForbiddenError
    from app.modules.observe.application.schemas import ApprovalCreate, ApprovalResolve

    owner = ObserveService(async_db, ctx)
    approval = await owner.create_approval(ApprovalCreate(title="t", assignee_user_ids=["u_alice"]))
    approval_id = approval.id
    runner = ObserveService(async_db, replace(ctx, user_id="u_bob", workspace_role="Dev", tenant_role="Member"))

    with pytest.raises(ForbiddenError):
        await runner.resolve_approvals([(approval_id, ApprovalResolve(status="approved"))])

    alice = ObserveService(async_db, replace(ctx, user_id="u_alice", workspace_role="Dev", tenant_role="Member"))
    [decided] = await alice.resolve_approvals([(approval_id, ApprovalResolve(status="approved"))])
    assert decided.status == "approved"
