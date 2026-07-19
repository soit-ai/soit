"""Shared ToolSpec approval policy resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.kernel.contracts.context import RequestContext
from app.kernel.registry.deps import get_registry


@dataclass(frozen=True)
class ToolApprovalRule:
    """Normalized approval rule for one governed tool."""

    mode: str = "none"
    risk_level: str = "normal"

    @property
    def required(self) -> bool:
        return self.mode == "required"


def tool_approval_rule(policy: dict[str, Any] | None) -> ToolApprovalRule:
    """Normalize an optional ToolSpec policy into an execution rule."""

    approval = (policy or {}).get("approval") or {}
    return ToolApprovalRule(
        mode=str(approval.get("mode") or "none"),
        risk_level=str(approval.get("risk_level") or "normal"),
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
