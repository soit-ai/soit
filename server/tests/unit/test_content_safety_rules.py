"""test_content_safety_rules

The built-in provider has to be worth switching on by default: it must find
credentials reliably, must not rewrite ordinary work by accident, and must
never write what it found into the evidence it produces.
"""

import pytest

from app.kernel.ports.safety.interface import SafetyDecision, SafetyDirection
from app.kernel.safety.rules import RuleContentSafetyPort, SafetyAction


async def _inspect(text: str, **kwargs):
    port = RuleContentSafetyPort(**kwargs)
    return await port.inspect(text, direction=SafetyDirection.OUTBOUND)


@pytest.mark.asyncio
async def test_a_credential_is_redacted_by_default():
    """A string shaped exactly like a key has no business in a prompt."""
    verdict = await _inspect("use sk-abcdefghijklmnopqrstuvwxyz12 to authenticate")

    assert verdict.decision is SafetyDecision.REDACT
    assert "sk-abcdefghijklmnopqrstuvwxyz12" not in (verdict.redacted_text or "")
    assert "[redacted:secret.openai_api_key]" in (verdict.redacted_text or "")


@pytest.mark.asyncio
async def test_a_private_key_block_is_found_whole():
    body = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA1234567890\n"
        "-----END RSA PRIVATE KEY-----"
    )
    verdict = await _inspect(f"here it is:\n{body}\nthanks")

    assert verdict.decision is SafetyDecision.REDACT
    assert "MIIEowIBAAKCAQEA" not in (verdict.redacted_text or "")
    assert "thanks" in (verdict.redacted_text or "")


@pytest.mark.asyncio
async def test_personal_data_is_reported_without_being_rewritten():
    """A support agent reading a customer's email address is the job."""
    verdict = await _inspect("reply to alice@example.com about the refund")

    assert verdict.decision is SafetyDecision.ALLOW
    assert [finding.category for finding in verdict.findings] == ["pii.email"]
    assert verdict.redacted_text is None


@pytest.mark.asyncio
async def test_personal_data_can_be_escalated_by_configuration():
    verdict = await _inspect(
        "reply to alice@example.com",
        pii_action=SafetyAction.REDACT,
    )

    assert verdict.decision is SafetyDecision.REDACT
    assert "alice@example.com" not in (verdict.redacted_text or "")


@pytest.mark.asyncio
async def test_blocking_is_available_and_says_what_it_blocked():
    verdict = await _inspect(
        "token ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        secret_action=SafetyAction.BLOCK,
    )

    assert verdict.decision is SafetyDecision.BLOCK
    assert verdict.findings[0].category == "secret.github_token"


@pytest.mark.asyncio
async def test_a_card_shaped_number_that_is_not_a_card_is_not_a_finding():
    """Order ids are card-shaped; the checksum is what tells them apart."""
    verdict = await _inspect("order 1234567812345678 shipped")

    assert verdict.findings == []


@pytest.mark.asyncio
async def test_a_real_card_number_is_a_finding():
    verdict = await _inspect("card 4111 1111 1111 1111 on file")

    assert [finding.category for finding in verdict.findings] == ["pii.credit_card"]


@pytest.mark.asyncio
async def test_evidence_never_carries_the_matched_text():
    """Recording detected data would recreate the exposure being checked for."""
    verdict = await _inspect("alice@example.com and sk-abcdefghijklmnopqrstuvwxyz12")

    rendered = str(verdict.evidence())
    assert "alice@example.com" not in rendered
    assert "sk-abcdefghijklmnopqrstuvwxyz12" not in rendered
    assert "pii.email" in rendered


@pytest.mark.asyncio
async def test_ordinary_text_costs_nothing_and_finds_nothing():
    verdict = await _inspect("Summarise the incident and draft a reply.")

    assert verdict.decision is SafetyDecision.ALLOW
    assert verdict.findings == []


@pytest.mark.asyncio
async def test_the_provider_names_itself_in_every_verdict():
    """Evidence has to say who decided, not only what was decided."""
    verdict = await _inspect("alice@example.com")

    assert verdict.provider == "builtin.rules"


class _StubLLM:
    """Answers with whatever text the test wants inspected."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.seen: list[str | None] = []

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        from app.kernel.ports.llm.interface import ChatResponse

        self.seen = [message.content for message in messages]
        return ChatResponse(
            text=self.text, tokens_prompt=1, tokens_completion=1, finish_reason="stop"
        )


def _gateway(llm, ctx, **kwargs):
    from app.kernel.ports.llm.policy import LLMPolicyGateway

    return LLMPolicyGateway(
        gateway=llm,
        ctx=ctx,
        content_safety=RuleContentSafetyPort(**kwargs),
    )


@pytest.mark.asyncio
async def test_a_credential_in_a_prompt_never_reaches_the_provider(ctx):
    from app.kernel.ports.llm.interface import ChatMessage

    llm = _StubLLM("done")
    gateway = _gateway(llm, ctx)

    await gateway.chat(
        [ChatMessage(role="user", content="deploy with sk-abcdefghijklmnopqrstuvwxyz12")],
        model="model:test:primary",
    )

    assert "sk-abcdefghijklmnopqrstuvwxyz12" not in str(llm.seen)
    assert "[redacted:secret.openai_api_key]" in str(llm.seen)


@pytest.mark.asyncio
async def test_a_credential_in_a_completion_never_reaches_the_caller(ctx):
    from app.kernel.ports.llm.interface import ChatMessage

    llm = _StubLLM("your key is ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    gateway = _gateway(llm, ctx)

    response = await gateway.chat(
        [ChatMessage(role="user", content="what is the key")],
        model="model:test:primary",
    )

    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in (response.text or "")


@pytest.mark.asyncio
async def test_inspection_can_be_turned_off_per_direction(ctx):
    from app.kernel.ports.llm.interface import ChatMessage
    from app.kernel.ports.llm.policy import LLMPolicyGateway

    llm = _StubLLM("done")
    gateway = LLMPolicyGateway(
        gateway=llm,
        ctx=ctx,
        content_safety=RuleContentSafetyPort(),
        inspect_inbound=False,
    )

    await gateway.chat(
        [ChatMessage(role="user", content="deploy with sk-abcdefghijklmnopqrstuvwxyz12")],
        model="model:test:primary",
    )

    assert "sk-abcdefghijklmnopqrstuvwxyz12" in str(llm.seen)


@pytest.mark.asyncio
async def test_a_blocking_policy_refuses_the_call(ctx):
    from app.kernel.commons.errors import ForbiddenError
    from app.kernel.ports.llm.interface import ChatMessage

    llm = _StubLLM("done")
    gateway = _gateway(llm, ctx, secret_action=SafetyAction.BLOCK)

    with pytest.raises(ForbiddenError):
        await gateway.chat(
            [ChatMessage(role="user", content="deploy with sk-abcdefghijklmnopqrstuvwxyz12")],
            model="model:test:primary",
        )
