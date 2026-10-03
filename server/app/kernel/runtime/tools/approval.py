"""Shared ToolSpec approval policy resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.kernel.contracts.context import RequestContext
from app.kernel.registry.deps import get_registry


@dataclass(frozen=True)
class ToolApprovalRule:
    """Normalized approval rule for one governed tool."""

    mode: str = "none"
    risk_level: str = "normal"
    approver_user_ids: tuple[str, ...] = field(default_factory=tuple)
    approver_roles: tuple[str, ...] = field(default_factory=tuple)
    timeout_seconds: int | None = None

    @property
    def required(self) -> bool:
        return self.mode == "required"

    def assignment(self, now: datetime) -> dict[str, Any]:
        """Who decides a request this rule opens at ``now``, and when it expires."""

        return {
            "assignee_user_ids": self.approver_user_ids,
            "assignee_roles": self.approver_roles,
            "expires_at": now + timedelta(seconds=self.timeout_seconds) if self.timeout_seconds else None,
        }


def tool_approval_rule(policy: dict[str, Any] | None) -> ToolApprovalRule:
    """Normalize an optional ToolSpec policy into an execution rule."""

    approval = (policy or {}).get("approval") or {}
    approvers = approval.get("approvers") if isinstance(approval.get("approvers"), dict) else {}
    timeout = approval.get("timeout_seconds")
    return ToolApprovalRule(
        mode=str(approval.get("mode") or "none"),
        risk_level=str(approval.get("risk_level") or "normal"),
        approver_user_ids=tuple(str(item) for item in approvers.get("users") or [] if str(item).strip()),
        approver_roles=tuple(str(item) for item in approvers.get("roles") or [] if str(item).strip()),
        timeout_seconds=int(timeout) if isinstance(timeout, int | float) and timeout > 0 else None,
    )


def resolve_tool_policy(
    *,
    tool_ref: str,
    ctx: RequestContext,
    tool_port: Any | None,
) -> dict[str, Any]:
    """Resolve ToolSpec policy through a port capability or scoped registry."""

    get_policy = getattr(tool_port, "get_tool_policy", None)
    if get_policy is not None:
        policy = get_policy(tool_ref, ctx)
        if policy:
            return dict(policy)

    register_builtin = getattr(tool_port, "register_builtin", None)
    if register_builtin is not None:
        register_builtin(tool_ref, ctx)

    found = get_registry().get_latest(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name=tool_ref,
    )
    if not found:
        return {}
    _, payload = found
    return dict(((payload or {}).get("tool_spec") or {}).get("policy") or {})
