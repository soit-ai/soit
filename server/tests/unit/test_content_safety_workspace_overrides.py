"""A workspace can set what the built-in rules do with personal data."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest

from app.kernel.ports.safety.interface import SafetyDecision, SafetyDirection
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.safety.rules import RuleContentSafetyPort, SafetyAction
from app.modules.identity.domain.models import Tenant, Workspace
from app.settings.settings import settings
from app.wiring import get_container

EMAIL = "please write to dana@example.com"


def _overrides(**actions: str | None) -> Callable[[], Awaitable[dict[str, str | None]]]:
    async def lookup() -> dict[str, str | None]:
        return dict(actions)

    return lookup


@pytest.mark.asyncio
async def test_each_direction_takes_its_own_action_read_once() -> None:
    calls = 0

    async def lookup() -> dict[str, str | None]:
        nonlocal calls
        calls += 1
        return {"inbound": "block", "outbound": None}

    port = RuleContentSafetyPort(pii_action=SafetyAction.OBSERVE, pii_overrides=lookup)

    inbound = await port.inspect(EMAIL, direction=SafetyDirection.INBOUND)
    outbound = await port.inspect(EMAIL, direction=SafetyDirection.OUTBOUND)
    again = await port.inspect("or to erin@example.com", direction=SafetyDirection.INBOUND)

    assert inbound.decision is SafetyDecision.BLOCK
    # A null override follows the deployment, which only records personal data.
    assert outbound.decision is SafetyDecision.ALLOW
    assert [finding.category for finding in outbound.findings] == ["pii.email"]
    assert again.decision is SafetyDecision.BLOCK
    assert calls == 1


@pytest.mark.asyncio
async def test_credentials_keep_the_deployment_action() -> None:
    port = RuleContentSafetyPort(pii_overrides=_overrides(inbound="observe"))

    verdict = await port.inspect(
        "deploy with sk-abcdefghijklmnopqrstuvwxyz12", direction=SafetyDirection.INBOUND
    )

    assert verdict.decision is SafetyDecision.REDACT


@pytest.mark.asyncio
async def test_an_unreadable_or_unknown_override_leaves_the_deployment_action() -> None:
    async def broken() -> dict[str, str | None]:
        raise RuntimeError("database unavailable")

    unreadable = RuleContentSafetyPort(pii_action=SafetyAction.REDACT, pii_overrides=broken)
    unknown = RuleContentSafetyPort(
        pii_action=SafetyAction.REDACT, pii_overrides=_overrides(inbound="shred")
    )

    for port in (unreadable, unknown):
        verdict = await port.inspect(EMAIL, direction=SafetyDirection.INBOUND)
        assert verdict.decision is SafetyDecision.REDACT


@pytest.mark.asyncio
async def test_a_remembered_verdict_is_never_reused_under_another_action() -> None:
    text = "forward it to frank@example.com"

    deployment = await RuleContentSafetyPort().inspect(text, direction=SafetyDirection.INBOUND)
    workspace = await RuleContentSafetyPort(pii_overrides=_overrides(inbound="redact")).inspect(
        text, direction=SafetyDirection.INBOUND
    )

    assert deployment.decision is SafetyDecision.ALLOW
    assert workspace.decision is SafetyDecision.REDACT
    assert "frank@example.com" not in (workspace.redacted_text or "")


@pytest.mark.asyncio
async def test_the_container_reads_the_workspace_through_the_run_session(
    async_db, ctx, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "content_safety_enabled", True)
    monkeypatch.setattr(settings, "content_safety_provider", "builtin")
    monkeypatch.setattr(settings, "content_safety_pii_action", "observe")
    async_db.add(Tenant(id=ctx.tenant_id, name="tenant"))
    async_db.add(
        Workspace(
            id=ctx.workspace_id,
            tenant_id=ctx.tenant_id,
            name="workspace",
            pii_action_outbound="redact",
        )
    )
    await async_db.commit()

    port = get_container().get_content_safety_port(ctx, TraceWriter(async_db, ctx))
    assert port is not None
    inbound = await port.inspect(EMAIL, direction=SafetyDirection.INBOUND)
    outbound = await port.inspect(EMAIL, direction=SafetyDirection.OUTBOUND)

    assert inbound.decision is SafetyDecision.ALLOW
    assert outbound.decision is SafetyDecision.REDACT
