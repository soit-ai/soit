"""Tests for AgentVerifier with structured output via function calling."""

import pytest

from app.adapters.llm.memory import InMemoryLLMPort
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ToolCall,
)
from app.modules.agent.runtime.verifier import AgentVerifier


class MockVerifierLLM(InMemoryLLMPort):
    """LLM that returns a verify_response tool call."""

    def __init__(self, ok: bool, reason: str = ""):
        self._ok = ok
        self._reason = reason
        self.messages = []

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        self.messages = messages
        return ChatResponse(
            text=None,
            tokens_prompt=10,
            tokens_completion=5,
            finish_reason="tool_calls",
            tool_calls=[
                ToolCall(
                    id="call_verify",
                    name="verify_response",
                    arguments={"ok": self._ok, "reason": self._reason},
                )
            ],
        )


@pytest.mark.asyncio
async def test_verifier_ok():
    llm = MockVerifierLLM(ok=True, reason="looks good")
    verifier = AgentVerifier(llm)
    result = await verifier.verify(
        messages=[ChatMessage(role="user", content="hello")],
        response="The answer is 42.",
        model="test-model",
        run_id="run_1",
    )
    assert result.ok is True
    assert result.reason == "looks good"
    assert result.tokens_prompt == 10
    review_prompt = llm.messages[-1].content
    assert "Original conversation" in review_prompt
    assert "user: hello" in review_prompt
    assert "Candidate response" in review_prompt
    assert "The answer is 42." in review_prompt


@pytest.mark.asyncio
async def test_verifier_not_ok():
    verifier = AgentVerifier(MockVerifierLLM(ok=False, reason="incomplete answer"))
    result = await verifier.verify(
        messages=[ChatMessage(role="user", content="hello")],
        response="I don't know.",
        model="test-model",
        run_id="run_1",
    )
    assert result.ok is False
    assert result.reason == "incomplete answer"


@pytest.mark.asyncio
async def test_verifier_no_llm_port():
    """When no LLM port, verification passes by default."""
    verifier = AgentVerifier(None)
    result = await verifier.verify(
        messages=[ChatMessage(role="user", content="hello")],
        response="ok",
        model="test-model",
        run_id="run_1",
    )
    assert result.ok is True
    assert result.tokens_prompt == 0
