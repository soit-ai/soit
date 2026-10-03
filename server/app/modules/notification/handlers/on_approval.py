"""Notifications for approval requests: who has one to decide, and when one lapsed.

A request waited silently in **Govern › Approvals** until someone happened to
look. Now:

- an opened request notifies the members who may decide it: its assigned
  members and the current holders of its assigned roles, or, with no
  assignees, the workspace's Owners and Admins other than whoever opened it;
- a delegated request notifies the member it was handed to;
- a request that expired undecided notifies whoever opened it.

Members' notification preferences apply (category ``task``), and the
workspace's own channels hear about opened requests. Each event notifies once:
a consumer slot is claimed before anything is written, so a redelivered event
changes nothing.
"""

from __future__ import annotations

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.events.checkpoint import try_claim_consumer_slot
from app.kernel.runtime.db.models.events import EventOutbox
from app.modules.notification.application.fanout import (
    members_with_roles,
    notify_users,
    notify_workspace_endpoints,
)

REQUESTED_CONSUMER = "notification.approval.requested"
DELEGATED_CONSUMER = "notification.approval.delegated"
EXPIRED_CONSUMER = "notification.approval.expired"

_CATEGORY = "task"
_UNASSIGNED_ROLES = ("Owner", "Admin")
_SYSTEM = "system"
_TARGET = "/govern/approvals"


def _scope(row: EventOutbox, payload: dict[str, Any]) -> tuple[str, str]:
    return (
        str(payload.get("tenant_id") or row.tenant_id or ""),
        str(payload.get("workspace_id") or row.workspace_id or ""),
    )


def _meta(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload.get(key)
        for key in ("approval_id", "run_id", "task_id", "expires_at")
        if payload.get(key)
    }


async def _claim(db: AsyncSession, consumer: str, row: EventOutbox) -> bool:
    return await try_claim_consumer_slot(db, consumer_name=consumer, event_id=row.event_id, result=consumer)


async def handle_approval_requested_notification(db: AsyncSession, row: EventOutbox) -> None:
    payload = row.payload_json or {}
    tenant_id, workspace_id = _scope(row, payload)
    if not tenant_id or not workspace_id or not await _claim(db, REQUESTED_CONSUMER, row):
        return
    users = [str(item) for item in payload.get("assignee_user_ids") or []]
    roles = [str(item) for item in payload.get("assignee_roles") or []]
    requester = payload.get("requested_by")
    if users or roles:
        recipients = list(dict.fromkeys([*users, *await members_with_roles(db, tenant_id, workspace_id, roles)]))
    else:
        recipients = [
            user_id
            for user_id in await members_with_roles(db, tenant_id, workspace_id, _UNASSIGNED_ROLES)
            if user_id != requester
        ]
    title = f"Approval needed: {payload.get('title') or 'a request'}"
    content = "A tool call is waiting for your decision."
    if payload.get("expires_at"):
        content = f"{content} Decide before {payload['expires_at']}; undecided, it expires and is refused."
    await notify_users(
        db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_ids=recipients,
        category=_CATEGORY,
        title=title,
        content=content,
        severity="warning",
        source_module="observe",
        action={"type": "open", "target": _TARGET},
        meta=_meta(payload),
    )
    await notify_workspace_endpoints(
        db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        category=_CATEGORY,
        title=title,
        content=content,
        severity="warning",
        source_module="observe",
        meta=_meta(payload),
    )
    await db.flush()


async def handle_approval_delegated_notification(db: AsyncSession, row: EventOutbox) -> None:
    payload = row.payload_json or {}
    tenant_id, workspace_id = _scope(row, payload)
    if not tenant_id or not workspace_id or not await _claim(db, DELEGATED_CONSUMER, row):
        return
    delegated_by = payload.get("delegated_by") or "Someone"
    content = f"{delegated_by} handed you this request to decide."
    if payload.get("note"):
        content = f"{content} Note: {payload['note']}"
    await notify_users(
        db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_ids=[str(item) for item in payload.get("assignee_user_ids") or []],
        category=_CATEGORY,
        title=f"Approval delegated to you: {payload.get('title') or 'a request'}",
        content=content,
        severity="warning",
        source_module="observe",
        action={"type": "open", "target": _TARGET},
        meta=_meta(payload),
    )
    await db.flush()


async def handle_approval_expired_notification(db: AsyncSession, row: EventOutbox) -> None:
    payload = row.payload_json or {}
    tenant_id, workspace_id = _scope(row, payload)
    requester = payload.get("requested_by")
    if not tenant_id or not workspace_id or not requester or requester == _SYSTEM:
        return
    if not await _claim(db, EXPIRED_CONSUMER, row):
        return
    await notify_users(
        db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_ids=[str(requester)],
        category=_CATEGORY,
        title=f"Approval expired: {payload.get('title') or 'a request'}",
        content="Nobody decided before the deadline, so the call was refused.",
        severity="warning",
        source_module="observe",
        action={"type": "open", "target": _TARGET},
        meta=_meta(payload),
    )
    await db.flush()
