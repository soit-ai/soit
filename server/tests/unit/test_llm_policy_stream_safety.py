"""Content safety inspects streamed chat both ways, as it does a whole reply."""

from __future__ import annotations

import pytest

from app.kernel.commons.errors import ForbiddenError
from app.kernel.ports.llm.interface import ChatMessage, ChatStreamChunk, ToolCallDelta
from app.kernel.ports.llm.policy import LLMPolicyGateway, _stream_cut_point
from app.kernel.safety.rules import RuleContentSafetyPort, SafetyAction

TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"


class _StreamingLLM:
    """Streams the given deltas and records the prompt it was sent."""

    def __init__(self, deltas: list[str], *, tool_delta: bool = False) -> None:
        self.deltas = deltas
        self.tool_delta = tool_delta
        self.seen: list[str | None] = []
        self.called = False

    async def chat(self, *args, **kwargs):  # pragma: no cover - streaming only
        raise AssertionError("chat is not used")

    async def stream_chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        self.called = True
        self.seen = [message.content for message in messages]
        for delta in self.deltas:
            yield ChatStreamChunk(delta=delta)
        if self.tool_delta:
            yield ChatStreamChunk(
                tool_call_deltas=[ToolCallDelta(index=0, id="call_1", name="lookup", arguments_delta="{}")]
            )
        yield ChatStreamChunk(done=True, finish_reason="stop", tokens_prompt=3, tokens_completion=5)


def _gateway(llm, ctx, **safety) -> LLMPolicyGateway:
    return LLMPolicyGateway(gateway=llm, ctx=ctx, content_safety=RuleContentSafetyPort(**safety))


async def _collect(gateway: LLMPolicyGateway, content: str = "hello") -> list[ChatStreamChunk]:
    return [
        chunk
        async for chunk in gateway.stream_chat(
            [ChatMessage(role="user", content=content)], model="model:test:primary"
        )
    ]


@pytest.mark.asyncio
async def test_a_credential_split_across_deltas_never_reaches_the_client(ctx) -> None:
    llm = _StreamingLLM(["Your key is ", TOKEN[:10], TOKEN[10:], " and more.\n", "Done."])

    chunks = await _collect(_gateway(llm, ctx))
    text = "".join(chunk.delta for chunk in chunks)

    assert TOKEN not in text
    assert TOKEN[:10] not in text
    assert "[redacted:" in text
    assert text.endswith("Done.")


@pytest.mark.asyncio
async def test_a_blocking_policy_ends_the_stream_before_the_text_leaves(ctx) -> None:
    llm = _StreamingLLM(["Safe opening. ", f"then {TOKEN} leaks.\n"])
    released: list[str] = []

    with pytest.raises(ForbiddenError):
        async for chunk in _gateway(llm, ctx, secret_action=SafetyAction.BLOCK).stream_chat(
            [ChatMessage(role="user", content="go")], model="model:test:primary"
        ):
            released.append(chunk.delta)

    assert TOKEN not in "".join(released)
    assert "Safe opening." in "".join(released)


@pytest.mark.asyncio
async def test_the_prompt_is_inspected_before_the_stream_starts(ctx) -> None:
    llm = _StreamingLLM(["ok"])

    await _collect(_gateway(llm, ctx), content=f"deploy with {TOKEN}")

    assert llm.called
    assert TOKEN not in str(llm.seen)

    blocked = _StreamingLLM(["ok"])
    with pytest.raises(ForbiddenError):
        await _collect(_gateway(blocked, ctx, secret_action=SafetyAction.BLOCK), content=f"use {TOKEN}")
    assert blocked.called is False


@pytest.mark.asyncio
async def test_tool_call_and_usage_chunks_pass_through(ctx) -> None:
    llm = _StreamingLLM(["Looking it up"], tool_delta=True)

    chunks = await _collect(_gateway(llm, ctx))

    assert any(chunk.tool_call_deltas for chunk in chunks)
    final = chunks[-1]
    assert final.done and final.tokens_completion == 5
    assert "".join(chunk.delta for chunk in chunks) == "Looking it up"


@pytest.mark.asyncio
async def test_without_content_safety_the_stream_is_untouched(ctx) -> None:
    llm = _StreamingLLM(["a", "b", "c"])
    gateway = LLMPolicyGateway(gateway=llm, ctx=ctx)

    chunks = await _collect(gateway)

    assert [chunk.delta for chunk in chunks[:3]] == ["a", "b", "c"]


def test_cut_points_keep_tokens_with_dots_whole() -> None:
    assert _stream_cut_point("Version 1.2.3 is out") is None
    assert _stream_cut_point("First sentence. Second") == len("First sentence.")
    assert _stream_cut_point("line one\nline") == len("line one\n")
    jwt_like = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc"
    assert _stream_cut_point(jwt_like) is None
    long_text = "word " * 100
    cut = _stream_cut_point(long_text)
    assert cut is not None and long_text[cut - 1] == " "
