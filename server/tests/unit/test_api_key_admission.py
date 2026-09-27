"""One API key, one budget: the admission model calls and tool calls share."""

from __future__ import annotations

from typing import Any

import pytest

from app.kernel.commons.errors import RateLimitExceededError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.common.api_key_admission import ApiKeyAdmission
from app.kernel.ports.llm.interface import ChatMessage, ChatResponse
from app.kernel.ports.llm.policy import LLMPolicyGateway

KEYED = RequestContext(
    tenant_id="t",
    workspace_id="w",
    user_id="u",
    workspace_role="Dev",
    scopes=frozenset({"read", "write"}),
    api_key_id="key_1",
    api_key_rate_limit_per_minute=5,
    api_key_daily_request_quota=100,
)


class _Limiter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int]] = []

    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        self.calls.append((key, limit, window_seconds))
        if sum(1 for call in self.calls if call[0] == key) > limit:
            raise RateLimitExceededError(
                f"Rate limit exceeded: {limit} requests per {window_seconds} seconds",
                {"limit": limit, "window_seconds": window_seconds, "retry_after": 12},
            )
        return True


class _Counter:
    def __init__(self) -> None:
        self.read: list[str] = []

    async def total(self, key: str, *, now: Any = None) -> int:
        self.read.append(key)
        return 0

    async def add(self, key: str, amount: int, *, now: Any = None) -> None:
        return None


class _Model:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, **kwargs: Any) -> ChatResponse:
        self.calls += 1
        return ChatResponse(text="hi", tokens_prompt=1, tokens_completion=1, model="m")


def _admission(ctx: RequestContext = KEYED, limiter: _Limiter | None = None) -> ApiKeyAdmission:
    return ApiKeyAdmission(ctx, rate_limiter=limiter or _Limiter(), usage_counter=_Counter())


@pytest.mark.asyncio
async def test_a_request_spends_the_keys_rate_and_daily_quota() -> None:
    limiter, counter = _Limiter(), _Counter()
    admission = ApiKeyAdmission(KEYED, rate_limiter=limiter, usage_counter=counter)

    await admission.admit_request()

    # The counter names predate tool calls sharing them; renaming them would
    # reset every key's windows.
    assert limiter.calls == [("llm:api_key:key_1", 5, 60), ("quota:llm:api_key:key_1", 100, 86400)]
    assert counter.read == []


@pytest.mark.asyncio
async def test_the_rate_and_the_daily_quota_are_spent_separately() -> None:
    limiter = _Limiter()

    await _admission(limiter=limiter).admit_rate()
    await _admission(limiter=limiter).admit_daily_request()

    assert [call[0] for call in limiter.calls] == ["llm:api_key:key_1", "quota:llm:api_key:key_1"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limits", "spend", "quota"),
    [
        ({"api_key_rate_limit_per_minute": 1}, "admit_rate", "per_minute"),
        ({"api_key_daily_request_quota": 1}, "admit_daily_request", "daily_requests"),
    ],
)
async def test_a_refusal_says_which_key_limit_and_when_to_retry(limits, spend, quota) -> None:
    ctx = RequestContext(
        tenant_id="t", workspace_id="w", user_id="u", workspace_role="Dev", api_key_id="key_1", **limits
    )
    admission = _admission(ctx)
    await getattr(admission, spend)()

    with pytest.raises(RateLimitExceededError) as refused:
        await getattr(admission, spend)()

    assert refused.value.code == "RATE_LIMIT_EXCEEDED"
    assert refused.value.details["quota"] == quota
    assert refused.value.details["retry_after"] == 12
    assert refused.value.details["limit"] == 1
    # The limiter's own wording stays, so /v1 answers as it did.
    assert refused.value.message.startswith("Rate limit exceeded")


@pytest.mark.asyncio
async def test_a_context_without_a_key_spends_nothing() -> None:
    limiter = _Limiter()
    session = RequestContext(
        tenant_id="t",
        workspace_id="w",
        user_id="u",
        workspace_role="Dev",
        api_key_rate_limit_per_minute=1,
        api_key_daily_request_quota=1,
    )

    await _admission(session, limiter).admit_request()

    assert limiter.calls == []


@pytest.mark.asyncio
async def test_a_tool_call_spends_what_a_model_call_needs() -> None:
    # The tool path's admission and the model gateway meet on the same
    # counter: one call a minute is one call, whichever kind it is.
    limiter = _Limiter()
    ctx = RequestContext(
        tenant_id="t",
        workspace_id="w",
        user_id="u",
        workspace_role="Dev",
        scopes=frozenset({"read", "write"}),
        api_key_id="key_1",
        api_key_rate_limit_per_minute=1,
    )
    model = _Model()
    gateway = LLMPolicyGateway(
        model,  # type: ignore[arg-type]
        ctx,
        rate_limiter=limiter,  # type: ignore[arg-type]
        usage_counter=_Counter(),  # type: ignore[arg-type]
        trace_writer=None,
        max_retries=0,
    )

    await ApiKeyAdmission(ctx, rate_limiter=limiter).admit_rate()  # type: ignore[arg-type]
    with pytest.raises(RateLimitExceededError):
        await gateway.chat([ChatMessage(role="user", content="hi")], model="model:test:chat")

    assert model.calls == 0
