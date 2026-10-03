"""A ToolSpec's approval policy: who decides the requests a tool opens, and by when."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.kernel.runtime.tools.approval import tool_approval_rule
from app.kernel.specs.validator import SpecValidator

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def test_approvers_and_a_timeout_assign_the_request_and_set_its_deadline() -> None:
    rule = tool_approval_rule(
        {
            "approval": {
                "mode": "required",
                "risk_level": "high",
                "approvers": {"users": ["u_alice", " "], "roles": ["Admin"]},
                "timeout_seconds": 900,
            }
        }
    )

    assert rule.required
    assert rule.assignment(NOW) == {
        "assignee_user_ids": ("u_alice",),
        "assignee_roles": ("Admin",),
        "expires_at": NOW + timedelta(minutes=15),
    }


def test_a_policy_without_them_assigns_nobody_and_never_expires() -> None:
    rule = tool_approval_rule({"approval": {"mode": "required", "risk_level": "normal"}})

    assert rule.assignment(NOW) == {"assignee_user_ids": (), "assignee_roles": (), "expires_at": None}


def _spec(approval: dict) -> dict:
    return {
        "name": "gated",
        "description": "A gated tool",
        "adapter": "function",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "policy": {"audit_level": "basic", "approval": approval},
        "function": {"entrypoint": "app.utils.builtin_tools:random_int"},
    }


def test_the_toolspec_schema_takes_approvers_and_a_timeout() -> None:
    def issues(document: dict) -> list:
        return SpecValidator().validate("tool_spec", document, raise_on_error=False)

    good = _spec(
        {"mode": "required", "risk_level": "high", "approvers": {"roles": ["Dev"]}, "timeout_seconds": 3600}
    )
    viewer = _spec({"mode": "required", "risk_level": "high", "approvers": {"roles": ["Viewer"]}})
    too_short = _spec({"mode": "required", "risk_level": "high", "timeout_seconds": 5})

    assert issues(good) == []
    assert issues(viewer)
    assert issues(too_short)
