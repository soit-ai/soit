"""Rule verdicts are remembered per text and configuration, so history is scanned once."""

from __future__ import annotations

import pytest

from app.kernel.ports.safety.interface import SafetyDecision, SafetyDirection
from app.kernel.safety import rules
from app.kernel.safety.rules import RuleContentSafetyPort, SafetyAction


@pytest.fixture(autouse=True)
def _fresh_cache():
    rules._verdict_cache.clear()
    yield
    rules._verdict_cache.clear()


@pytest.fixture
def scans(monkeypatch) -> list[str]:
    seen: list[str] = []
    real = rules.scan_text

    def counting(text: str):
        seen.append(text)
        return real(text)

    monkeypatch.setattr(rules, "scan_text", counting)
    return seen


@pytest.mark.asyncio
async def test_the_same_text_is_scanned_once(scans) -> None:
    port = RuleContentSafetyPort()
    text = "reach me at someone@example.com"

    first = await port.inspect(text, direction=SafetyDirection.INBOUND)
    second = await RuleContentSafetyPort().inspect(text, direction=SafetyDirection.INBOUND)

    assert scans == [text]
    assert second == first
    assert [f.category for f in second.findings] == [f.category for f in first.findings]


@pytest.mark.asyncio
async def test_a_different_configuration_or_direction_is_scanned_again(scans) -> None:
    text = "token sk-abcdefghijklmnopqrstuvwx1234 for someone@example.com"

    observing = await RuleContentSafetyPort(secret_action=SafetyAction.OBSERVE).inspect(
        text, direction=SafetyDirection.INBOUND
    )
    blocking = await RuleContentSafetyPort(secret_action=SafetyAction.BLOCK).inspect(
        text, direction=SafetyDirection.INBOUND
    )
    await RuleContentSafetyPort(secret_action=SafetyAction.BLOCK).inspect(
        text, direction=SafetyDirection.OUTBOUND
    )

    assert len(scans) == 3
    assert observing.decision is not SafetyDecision.BLOCK
    assert blocking.decision is SafetyDecision.BLOCK


@pytest.mark.asyncio
async def test_the_cache_holds_digests_not_text_and_is_bounded(monkeypatch) -> None:
    monkeypatch.setattr(rules, "_VERDICT_CACHE_SIZE", 3)
    port = RuleContentSafetyPort()
    secret_text = "password is hunter2 and card 4111111111111111"
    await port.inspect(secret_text, direction=SafetyDirection.INBOUND)
    for i in range(5):
        await port.inspect(f"message {i}", direction=SafetyDirection.INBOUND)

    assert len(rules._verdict_cache) == 3
    for key in rules._verdict_cache:
        assert isinstance(key[0], bytes) and secret_text.encode() not in key[0]
