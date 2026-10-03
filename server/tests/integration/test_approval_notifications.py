"""Approval requests notify the people who have to act on them, once.

An opened request reaches its assigned members and the current holders of its
assigned roles, or, with nobody assigned, the workspace's Owners and Admins
other than whoever opened it. A delegated request reaches the member it was
handed to, and a request that expired undecided reaches whoever opened it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
import pytest_asyncio
from sqlmodel import select

from app.kernel.commons.time import utc_now
from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.identity.workspace_access import WorkspaceAccess
from app.kernel.runtime.db.models.events import EventOutbox
from app.modules.identity.domain.models import WorkspaceMembership
from app.modules.notification.domain.models import Notification
from app.modules.notification.handlers.on_approval import (
    handle_approval_requested_notification,
)
from app.modules.observe.application.approval_sweeper import expire_overdue_approvals
from app.modules.observe.application.schemas import ApprovalCreate, ApprovalDelegate
from app.modules.observe.application.service import ObserveService
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers

pytestmark = pytest.mark.asyncio

ROLES = {"u_owner": "Owner", "u_admin": "Admin", "u_alice": "Dev", "u_dev": "Dev", "u_viewer": "Viewer"}


class _Members:
    async def resolve(self, tenant_id, workspace_id, user_id, session_id=None):
        del tenant_id, workspace_id, session_id
        role = ROLES.get(user_id)
        return WorkspaceAccess(tenant_role="Member", workspace_role=role) if role else None


@pytest_asyncio.fixture
async def members(async_db, ctx):
    for user_id, role in ROLES.items():
        async_db.add(
            WorkspaceMembership(tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, user_id=user_id, role=role)
        )
    await async_db.commit()
    register_outbox_handlers()
    return replace(ctx, user_id="u_owner", workspace_role="Owner")


def _service(async_db, ctx, user_id: str) -> ObserveService:
    member = replace(ctx, user_id=user_id, workspace_role=ROLES[user_id], tenant_role="Member")
    return ObserveService(async_db, member, member_access=_Members())


async def _deliver(async_db) -> None:
    await OutboxDispatcher(async_db, get_outbox_registry()).run_once(batch_limit=50)
    await async_db.commit()


async def _inbox(async_db) -> dict[str, list[str]]:
    rows = (await async_db.exec(select(Notification))).all()
    inbox: dict[str, list[str]] = {}
    for row in rows:
        notification = row if isinstance(row, Notification) else row[0]
        inbox.setdefault(notification.user_id, []).append(notification.title)
    return inbox


async def test_an_assigned_request_notifies_its_approvers_once(async_db, members) -> None:
    owner = _service(async_db, members, "u_owner")
    await owner.create_approval(
        ApprovalCreate(title="Send the refund", assignee_user_ids=["u_alice", "svc_bot"], assignee_roles=["Admin"])
    )
    await _deliver(async_db)

    inbox = await _inbox(async_db)
    assert sorted(inbox) == ["u_admin", "u_alice"]
    assert inbox["u_alice"] == ["Approval needed: Send the refund"]

    # The same event again notifies nobody twice.
    row = (await async_db.exec(select(EventOutbox).where(EventOutbox.event_type == "approval.requested"))).first()
    await handle_approval_requested_notification(async_db, row if isinstance(row, EventOutbox) else row[0])
    await async_db.commit()
    assert await _inbox(async_db) == inbox


async def test_an_unassigned_request_notifies_the_owners_and_admins_but_its_requester(async_db, members) -> None:
    await _service(async_db, members, "u_owner").create_approval(ApprovalCreate(title="Drop the table"))
    await _deliver(async_db)

    assert sorted(await _inbox(async_db)) == ["u_admin"]


async def test_a_delegated_request_notifies_the_new_approver(async_db, members) -> None:
    approval = await _service(async_db, members, "u_owner").create_approval(
        ApprovalCreate(title="Send the refund", assignee_user_ids=["u_alice"])
    )
    approval_id = approval.id
    await _deliver(async_db)

    await _service(async_db, members, "u_alice").delegate_approval(
        approval_id, ApprovalDelegate(user_id="u_dev", note="Out this week")
    )
    await _deliver(async_db)

    inbox = await _inbox(async_db)
    assert inbox["u_dev"] == ["Approval delegated to you: Send the refund"]


async def test_an_expired_request_notifies_its_requester(async_db, members) -> None:
    approval = await _service(async_db, members, "u_alice").create_approval(
        ApprovalCreate(title="Send the refund", assignee_roles=["Admin"], expires_at=utc_now() + timedelta(hours=1))
    )
    approval.expires_at = utc_now() - timedelta(seconds=1)
    async_db.add(approval)
    await async_db.commit()
    await _deliver(async_db)

    assert await expire_overdue_approvals(async_db) == 1
    await _deliver(async_db)

    inbox = await _inbox(async_db)
    assert inbox["u_alice"] == ["Approval expired: Send the refund"]
