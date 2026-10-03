"""Who may decide an approval request.

A request with no assignees keeps the workspace rule: any member who can
write (an Owner, Admin or Dev) decides it. A request with assignees is
decided only by an assigned member or service principal, or by a holder of
an assigned role. Roles are read from the caller's context, which is
resolved from the membership on every request, so an approver who is
removed from the workspace or loses the role can no longer decide.

Canceling is not deciding: the requester and the workspace's Owners and
Admins may also cancel an assigned request.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.kernel.contracts.context import RequestContext

APPROVER_ROLES = ("Owner", "Admin", "Dev")
"""Roles that may be assigned: the ones whose holders can write."""


def normalize_roles(roles: list[str] | None) -> list[str]:
    """Assigned roles in canonical spelling, without duplicates; unknown ones raise."""

    canonical = {role.lower(): role for role in APPROVER_ROLES}
    out: list[str] = []
    for role in roles or []:
        name = canonical.get(str(role).strip().lower())
        if name is None:
            raise ValueError(
                f"Role {role!r} cannot be assigned an approval; use one of {', '.join(APPROVER_ROLES)}"
            )
        if name not in out:
            out.append(name)
    return out


def normalize_users(user_ids: list[str] | None) -> list[str]:
    out: list[str] = []
    for user_id in user_ids or []:
        value = str(user_id).strip()
        if value and value not in out:
            out.append(value)
    return out


def assignees(approval: Any) -> dict[str, list[str]]:
    return {
        "user_ids": list(getattr(approval, "assignee_user_ids", None) or []),
        "roles": list(getattr(approval, "assignee_roles", None) or []),
    }


def is_assigned(approval: Any) -> bool:
    current = assignees(approval)
    return bool(current["user_ids"] or current["roles"])


def may_decide(approval: Any, ctx: RequestContext) -> bool:
    """Whether ``ctx`` may approve or reject ``approval`` now."""

    if not ctx.can_write():
        return False
    if not is_assigned(approval):
        return True
    current = assignees(approval)
    return (ctx.user_id or "") in current["user_ids"] or (ctx.workspace_role or "") in current["roles"]


def assigned_to(approval: Any, ctx: RequestContext) -> bool:
    """Whether ``approval`` names ``ctx``, as a member or by a role they hold now."""

    if not is_assigned(approval):
        return False
    current = assignees(approval)
    return (ctx.user_id or "") in current["user_ids"] or (ctx.workspace_role or "") in current["roles"]


def is_own_request(approval: Any, ctx: RequestContext) -> bool:
    """Whether ``ctx`` opened ``approval``."""

    requester = getattr(approval, "requested_by", None)
    return bool(requester) and requester == ctx.user_id


def may_approve(approval: Any, ctx: RequestContext, *, forbid_self_approval: bool) -> bool:
    """Whether ``ctx`` may approve ``approval`` now; rejecting needs only ``may_decide``."""

    if forbid_self_approval and is_own_request(approval, ctx):
        return False
    return may_decide(approval, ctx)


def reminder_time(created_at: datetime, expires_at: datetime, lead_seconds: float) -> datetime | None:
    """When the approvers of a request are reminded of its deadline.

    ``lead_seconds`` before it, or half-way through a request too short for
    that, so a request is never reminded about the moment it is opened.
    """

    if lead_seconds <= 0:
        return None
    created = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    expires = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
    life = expires - created
    if life <= timedelta(0):
        return None
    return expires - min(timedelta(seconds=lead_seconds), life / 2)


def may_cancel(approval: Any, ctx: RequestContext) -> bool:
    """Whether ``ctx`` may close ``approval`` without a decision."""

    if may_decide(approval, ctx):
        return True
    requester = getattr(approval, "requested_by", None)
    return ctx.can_write() and (ctx.can_govern() or (bool(requester) and requester == ctx.user_id))
