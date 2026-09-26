"""An API key's own limits apply to every model call made with it."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any

import pytest

from app.kernel.commons.errors import ForbiddenError, RateLimitExceededError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
)
from app.kernel.ports.llm.policy import LLMPolicyGateway

KEYED = RequestContext(
    tenant_id="t",
    workspace_id="w",
    user_id="u",
    workspace_role="Dev",
    scopes=frozenset({"read", "write"}),
    api_key_id="key_1",
)
MESSAGES = [ChatMessage(role="user", content="hello")]


class _Limiter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int]] = []

    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        self.calls.append((key, limit, window_seconds))
        if sum(1 for call in self.calls if call[0] == key) > limit:
            raise RateLimitExceededError("Rate limit exceeded", {"retry_after": 1})
        return True


class _Counter:
    def __init__(self, totals: dict[str, int] | None = None) -> None:
        self.totals = dict(totals or {})
        self.added: list[tuple[str, int]] = []

    async def total(self, key: str, *, now: Any = None) -> int:
        return self.totals.get(key, 0)

    async def add(self, key: str, amount: int, *, now: Any = None) -> None:
        self.added.append((key, amount))


class _Model:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, **kwargs: Any) -> ChatResponse:
        self.calls += 1
        return ChatResponse(text="hi", tokens_prompt=10, tokens_completion=20, model="m")

    async def stream_chat(self, **kwargs: Any) -> AsyncIterator[ChatStreamChunk]:
        self.calls += 1
        yield ChatStreamChunk(delta="hi", done=True, tokens_prompt=5, tokens_completion=7)

    async def embed(self, **kwargs: Any) -> EmbeddingResponse:
        self.calls += 1
        return EmbeddingResponse(embeddings=[[0.0]], tokens_used=4, model="e")


def _gateway(
    ctx: RequestContext,
    *,
    limiter: _Limiter | None = None,
    counter: _Counter | None = None,
    model: _Model | None = None,
    **options: Any,
) -> LLMPolicyGateway:
    return LLMPolicyGateway(
        gateway=model or _Model(),  # type: ignore[arg-type]
        ctx=ctx,
        rate_limiter=limiter or _Limiter(),  # type: ignore[arg-type]
        usage_counter=counter or _Counter(),  # type: ignore[arg-type]
        **options,
    )


@pytest.mark.asyncio
async def test_a_model_outside_the_keys_list_is_refused_before_any_limit_is_spent() -> None:
    limiter = _Limiter()
    model = _Model()
    gateway = _gateway(
        replace(KEYED, allowed_models=frozenset({"model:openai:gpt-allowed"})),
        limiter=limiter,
        model=model,
        rate_limit_per_minute=10,
    )

    with pytest.raises(ForbiddenError) as refused:
        await gateway.chat(MESSAGES, "model:openai:gpt-other")

    assert refused.value.details["reason"] == "model_not_allowed"
    assert refused.value.details["param"] == "model"
    assert limiter.calls == []
    assert model.calls == 0
    await gateway.chat(MESSAGES, "model:openai:gpt-allowed")
    assert model.calls == 1


@pytest.mark.asyncio
async def test_the_keys_rate_applies_beside_the_members_own() -> None:
    limiter = _Limiter()
    gateway = _gateway(
        replace(KEYED, api_key_rate_limit_per_minute=1),
        limiter=limiter,
        rate_limit_per_minute=100,
    )

    await gateway.chat(MESSAGES, "m")
    with pytest.raises(RateLimitExceededError):
        await gateway.chat(MESSAGES, "m")

    assert ("llm:chat:t:w:u", 100, 60) in limiter.calls
    assert ("llm:api_key:key_1", 1, 60) in limiter.calls


@pytest.mark.asyncio
async def test_the_daily_request_quota_counts_every_operation_of_the_key() -> None:
    limiter = _Limiter()
    gateway = _gateway(replace(KEYED, api_key_daily_request_quota=2), limiter=limiter)

    await gateway.chat(MESSAGES, "m")
    await gateway.embed(["x"], "e")
    with pytest.raises(RateLimitExceededError):
        await gateway.chat(MESSAGES, "m")

    assert set(limiter.calls) == {("quota:llm:api_key:key_1", 2, 86400)}


@pytest.mark.asyncio
async def test_a_spent_token_quota_refuses_until_the_next_utc_day() -> None:
    counter = _Counter({"tokens:api_key:key_1": 1000})
    model = _Model()
    gateway = _gateway(
        replace(KEYED, api_key_daily_token_quota=1000), counter=counter, model=model
    )

    with pytest.raises(RateLimitExceededError) as refused:
        await gateway.chat(MESSAGES, "m")

    assert refused.value.details["quota"] == "daily_tokens"
    assert 0 < refused.value.details["retry_after"] <= 86400
    assert model.calls == 0


@pytest.mark.asyncio
async def test_finished_calls_add_their_tokens_to_the_keys_day() -> None:
    counter = _Counter()
    gateway = _gateway(replace(KEYED, api_key_daily_token_quota=1_000_000), counter=counter)

    await gateway.chat(MESSAGES, "m")
    async for _ in gateway.stream_chat(MESSAGES, "m"):
        pass
    await gateway.embed(["x"], "e")

    assert counter.added == [
        ("tokens:api_key:key_1", 30),
        ("tokens:api_key:key_1", 12),
        ("tokens:api_key:key_1", 4),
    ]


@pytest.mark.asyncio
async def test_a_session_without_a_key_meets_only_the_members_limits() -> None:
    limiter = _Limiter()
    counter = _Counter()
    session = RequestContext(tenant_id="t", workspace_id="w", user_id="u", workspace_role="Dev")
    gateway = _gateway(session, limiter=limiter, counter=counter, rate_limit_per_minute=5)

    await gateway.chat(MESSAGES, "any-model")

    assert limiter.calls == [("llm:chat:t:w:u", 5, 60)]
    assert counter.added == []
