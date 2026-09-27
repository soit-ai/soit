"""A stream its consumer abandons still lands in the ledger."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anyio
import pytest

from app.kernel.commons.errors import ForbiddenError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ChatMessage, ChatResponse, ChatStreamChunk
from app.kernel.ports.llm.policy import STREAM_ABANDONED, LLMPolicyGateway
from app.kernel.safety.rules import RuleContentSafetyPort, SafetyAction

KEYED = RequestContext(
    tenant_id="t",
    workspace_id="w",
    user_id="u",
    workspace_role="Dev",
    scopes=frozenset({"read", "write"}),
    api_key_id="key_1",
    api_key_daily_token_quota=1_000_000,
)
MESSAGES = [ChatMessage(role="user", content="hello")]
# One unit per token, input 1 and output 2, so amounts read as token counts.
PRICING = {"currency": "USD", "input": "1", "output": "2", "unit": "token"}
# 4 message overhead + ceil(len("hello") / 4)
PROMPT_ESTIMATE = 6
TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"


class _Upstream:
    """A provider stream: deltas, then optionally a wait, then its usage."""

    def __init__(
        self,
        deltas: list[str],
        *,
        hang_before_first: bool = False,
        hang_after: bool = False,
        fail_after: bool = False,
        usage: tuple[int, int] | None = None,
    ) -> None:
        self.deltas = deltas
        self.hang_before_first = hang_before_first
        self.hang_after = hang_after
        self.fail_after = fail_after
        self.usage = usage
        self.waiting = asyncio.Event()
        self.closed = False

    async def stream_chat(self, **kwargs: Any) -> AsyncIterator[ChatStreamChunk]:
        del kwargs
        try:
            if self.hang_before_first:
                self.waiting.set()
                await asyncio.Event().wait()
            for delta in self.deltas:
                yield ChatStreamChunk(delta=delta)
            if self.hang_after:
                self.waiting.set()
                await asyncio.Event().wait()
            if self.fail_after:
                raise RuntimeError("the provider dropped the stream")
            if self.usage is not None:
                yield ChatStreamChunk(
                    done=True,
                    finish_reason="stop",
                    tokens_prompt=self.usage[0],
                    tokens_completion=self.usage[1],
                )
        finally:
            self.closed = True


class _Route:
    def __init__(self, port: _Upstream) -> None:
        self.port = port
        self.target = None
        self.timeout_seconds = 5.0
        self.max_retries = 0
        self.retry_backoff = "none"
        self.retryable_status_codes = ()
        self.pricing = PRICING


class _Router:
    def __init__(self, port: _Upstream) -> None:
        self.port = port

    def resolve_route(self, model: str, ctx: RequestContext, required: tuple[str, ...]) -> _Route:
        del model, ctx, required
        return _Route(self.port)

    def stream_chat(self, **kwargs: Any) -> Any:  # pragma: no cover - routed
        raise AssertionError("calls go through the resolved route")


class _Answering:
    """A model that answers whole, with a credential in its answer."""

    async def chat(self, **kwargs: Any) -> ChatResponse:
        del kwargs
        return ChatResponse(text=f"Your key is {TOKEN}.", tokens_prompt=7, tokens_completion=3, model="m")


class _Limiter:
    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        return True


class _Counter:
    def __init__(self) -> None:
        self.added: list[tuple[str, int]] = []

    async def total(self, key: str, *, now: Any = None) -> int:
        return 0

    async def add(self, key: str, amount: int, *, now: Any = None) -> None:
        self.added.append((key, amount))


def _writer() -> MagicMock:
    """A trace writer whose writes pass a cancellation checkpoint first."""

    writer = MagicMock()
    step = MagicMock()
    step.id = "step_1"
    writer.create_step = AsyncMock(return_value=step)
    writer.release_before_wait = AsyncMock()
    writer.status_updates = []
    writer.costs = []

    async def update_step_status(step_id: str, status: str, **kwargs: Any) -> None:
        await anyio.sleep(0)
        writer.status_updates.append((step_id, status, kwargs))

    async def record_cost(**kwargs: Any) -> None:
        await anyio.sleep(0)
        writer.costs.append(kwargs)

    writer.update_step_status = update_step_status
    writer.record_cost = record_cost
    return writer


def _gateway(
    upstream: Any,
    writer: MagicMock,
    counter: _Counter | None = None,
    **options: Any,
) -> LLMPolicyGateway:
    return LLMPolicyGateway(
        gateway=_Router(upstream),  # type: ignore[arg-type]
        ctx=KEYED,
        trace_writer=writer,
        rate_limiter=_Limiter(),  # type: ignore[arg-type]
        usage_counter=counter or _Counter(),  # type: ignore[arg-type]
        **options,
    )


@pytest.mark.asyncio
async def test_a_stream_closed_mid_way_is_charged_on_an_estimate() -> None:
    upstream = _Upstream(["Hello ", "world"], usage=(40, 50))
    writer = _writer()
    counter = _Counter()
    stream = _gateway(upstream, writer, counter).stream_chat(MESSAGES, "m", run_id="run_1")

    assert (await anext(stream)).delta == "Hello "
    assert (await anext(stream)).delta == "world"
    await stream.aclose()

    assert upstream.closed
    [(step_id, status, update)] = writer.status_updates
    assert (step_id, status) == ("step_1", "canceled")
    assert update["error_code"] == STREAM_ABANDONED
    completion = 3  # ceil(len("Hello world") / 4)
    assert update["metrics"]["usage_estimated"] is True
    assert (update["metrics"]["tokens_prompt"], update["metrics"]["tokens_completion"]) == (
        PROMPT_ESTIMATE,
        completion,
    )
    [cost] = writer.costs
    assert (cost["prompt_tokens"], cost["completion_tokens"]) == (PROMPT_ESTIMATE, completion)
    assert cost["amount"] == Decimal(PROMPT_ESTIMATE + 2 * completion)
    assert cost["currency"] == "USD"
    assert cost["pricing_snapshot_json"]["usage_estimated"] is True
    assert counter.added == [("tokens:api_key:key_1", PROMPT_ESTIMATE + completion)]


@pytest.mark.asyncio
async def test_a_consumer_cancelled_while_the_model_generates_is_still_charged() -> None:
    upstream = _Upstream(["partial "], hang_after=True)
    writer = _writer()
    received: list[str] = []

    async def consume() -> None:
        async for chunk in _gateway(upstream, writer).stream_chat(MESSAGES, "m", run_id="run_1"):
            received.append(chunk.delta)

    async with anyio.create_task_group() as group:
        group.start_soon(consume)
        await upstream.waiting.wait()
        group.cancel_scope.cancel()

    assert received == ["partial "]
    assert upstream.closed
    # The writes pass a checkpoint inside the cancelled scope, so they land
    # only because settling the stream is shielded.
    assert [status for _, status, _ in writer.status_updates] == ["canceled"]
    [cost] = writer.costs
    assert cost["completion_tokens"] == 2  # ceil(len("partial ") / 4)
    assert cost["pricing_snapshot_json"]["usage_estimated"] is True


@pytest.mark.asyncio
async def test_usage_the_provider_already_reported_is_recorded_as_it_is() -> None:
    upstream = _Upstream(["hi"], usage=(7, 3))
    writer = _writer()
    counter = _Counter()
    stream = _gateway(upstream, writer, counter).stream_chat(MESSAGES, "m", run_id="run_1")

    assert (await anext(stream)).delta == "hi"
    assert (await anext(stream)).done
    await stream.aclose()

    [(_, status, update)] = writer.status_updates
    assert status == "succeeded"
    assert "usage_estimated" not in update["metrics"]
    [cost] = writer.costs
    assert (cost["prompt_tokens"], cost["completion_tokens"]) == (7, 3)
    assert "usage_estimated" not in cost["pricing_snapshot_json"]
    assert counter.added == [("tokens:api_key:key_1", 10)]


@pytest.mark.asyncio
async def test_a_stream_cancelled_before_any_chunk_closes_its_step_without_a_cost() -> None:
    upstream = _Upstream(["never"], hang_before_first=True)
    writer = _writer()

    async def consume() -> None:
        async for _ in _gateway(upstream, writer).stream_chat(MESSAGES, "m", run_id="run_1"):
            pass

    async with anyio.create_task_group() as group:
        group.start_soon(consume)
        await upstream.waiting.wait()
        group.cancel_scope.cancel()

    [(_, status, update)] = writer.status_updates
    assert (status, update["error_code"]) == ("canceled", STREAM_ABANDONED)
    assert writer.costs == []


@pytest.mark.asyncio
async def test_a_stream_handed_to_another_task_is_charged_when_that_task_closes_it() -> None:
    # The gateway endpoint pulls the first chunk; the response task streams
    # the rest and is the one that closes the stream when the client leaves.
    upstream = _Upstream(["Hello ", "world"], usage=(1, 1))
    writer = _writer()
    stream = _gateway(upstream, writer).stream_chat(MESSAGES, "m", run_id="run_1")
    await anext(stream)

    async def respond() -> None:
        await stream.aclose()

    await asyncio.create_task(respond())

    assert [status for _, status, _ in writer.status_updates] == ["canceled"]
    assert len(writer.costs) == 1


@pytest.mark.asyncio
async def test_a_stream_nobody_closed_leaves_the_session_alone() -> None:
    # A stream collected while still open is closed by asyncio from a task
    # that only runs its aclose(), which shares nothing with its consumer.
    upstream = _Upstream(["Hello ", "world"], usage=(1, 1))
    writer = _writer()
    stream = _gateway(upstream, writer).stream_chat(MESSAGES, "m", run_id="run_1")
    await anext(stream)

    await asyncio.create_task(stream.aclose())

    assert writer.status_updates == []
    assert writer.costs == []


@pytest.mark.asyncio
async def test_a_stream_that_fails_part_way_is_charged_for_what_was_generated() -> None:
    upstream = _Upstream(["Hello ", "world"], fail_after=True)
    writer = _writer()
    counter = _Counter()
    stream = _gateway(upstream, writer, counter).stream_chat(MESSAGES, "m", run_id="run_1")

    with pytest.raises(RuntimeError):
        async for _ in stream:
            pass

    [(_, status, update)] = writer.status_updates
    assert (status, update["error_code"]) == ("failed", "LLM_ERROR")
    [cost] = writer.costs
    assert (cost["prompt_tokens"], cost["completion_tokens"]) == (PROMPT_ESTIMATE, 3)
    assert cost["pricing_snapshot_json"]["usage_estimated"] is True
    assert counter.added == [("tokens:api_key:key_1", PROMPT_ESTIMATE + 3)]


@pytest.mark.asyncio
async def test_a_stream_the_provider_never_reports_usage_for_is_charged_an_estimate() -> None:
    upstream = _Upstream(["Hello ", "world"])
    writer = _writer()

    chunks = [chunk async for chunk in _gateway(upstream, writer).stream_chat(MESSAGES, "m", run_id="run_1")]

    assert [chunk.delta for chunk in chunks] == ["Hello ", "world"]
    [(_, status, update)] = writer.status_updates
    assert status == "succeeded"
    assert update["metrics"]["usage_estimated"] is True
    [cost] = writer.costs
    assert (cost["prompt_tokens"], cost["completion_tokens"]) == (PROMPT_ESTIMATE, 3)


@pytest.mark.asyncio
async def test_a_consumer_leaving_after_the_model_finished_records_a_finished_call() -> None:
    # Outbound inspection holds back a partial sentence and releases it once
    # the provider stream has ended; the consumer leaves at that last chunk.
    upstream = _Upstream(["Hello ", "world"])
    writer = _writer()
    gateway = _gateway(upstream, writer, content_safety=RuleContentSafetyPort())
    stream = gateway.stream_chat(MESSAGES, "m", run_id="run_1")

    assert (await anext(stream)).delta == "Hello world"
    await stream.aclose()

    [(_, status, update)] = writer.status_updates
    assert status == "succeeded"
    assert update.get("error_code") is None
    assert len(writer.costs) == 1


@pytest.mark.asyncio
async def test_the_ledger_write_of_a_finished_stream_survives_a_cancellation() -> None:
    upstream = _Upstream(["Hello ", "world"], usage=(40, 50))
    writer = _writer()
    recording = asyncio.Event()

    async def record_cost(**kwargs: Any) -> None:
        recording.set()
        await anyio.sleep(0.05)
        writer.costs.append(kwargs)

    writer.record_cost = record_cost

    async def consume() -> None:
        async for _ in _gateway(upstream, writer).stream_chat(MESSAGES, "m", run_id="run_1"):
            pass

    async with anyio.create_task_group() as group:
        group.start_soon(consume)
        await recording.wait()
        group.cancel_scope.cancel()

    [cost] = writer.costs
    assert (cost["prompt_tokens"], cost["completion_tokens"]) == (40, 50)
    assert [status for _, status, _ in writer.status_updates] == ["succeeded"]


@pytest.mark.asyncio
async def test_an_answer_refused_by_outbound_inspection_is_still_charged() -> None:
    writer = _writer()
    counter = _Counter()
    gateway = _gateway(
        _Answering(),
        writer,
        counter,
        content_safety=RuleContentSafetyPort(secret_action=SafetyAction.BLOCK),
    )

    with pytest.raises(ForbiddenError):
        await gateway.chat(MESSAGES, "m", run_id="run_1")

    [(_, status, update)] = writer.status_updates
    assert (status, update["error_code"]) == ("failed", "LLM_ERROR")
    assert update["output_summary"] is None
    [cost] = writer.costs
    assert (cost["prompt_tokens"], cost["completion_tokens"]) == (7, 3)
    assert counter.added == [("tokens:api_key:key_1", 10)]


@pytest.mark.asyncio
async def test_a_finished_stream_is_charged_once_for_what_the_provider_reported() -> None:
    upstream = _Upstream(["Hello ", "world"], usage=(40, 50))
    writer = _writer()
    counter = _Counter()

    chunks = [
        chunk async for chunk in _gateway(upstream, writer, counter).stream_chat(MESSAGES, "m", run_id="run_1")
    ]

    assert [chunk.delta for chunk in chunks] == ["Hello ", "world", ""]
    [(_, status, _)] = writer.status_updates
    assert status == "succeeded"
    [cost] = writer.costs
    assert (cost["prompt_tokens"], cost["completion_tokens"]) == (40, 50)
    assert counter.added == [("tokens:api_key:key_1", 90)]


class _FailingCounter(_Counter):
    async def add(self, key: str, amount: int, *, now: Any = None) -> None:
        raise ConnectionError("the counter store is down")


class _Clean:
    """A model that answers whole."""

    async def chat(self, **kwargs: Any) -> ChatResponse:
        del kwargs
        return ChatResponse(text="Fine.", tokens_prompt=7, tokens_completion=3, model="m")


@pytest.mark.asyncio
async def test_a_failing_key_counter_never_keeps_a_call_out_of_the_ledger() -> None:
    writer = _writer()
    gateway = _gateway(_Clean(), writer, _FailingCounter())

    response = await gateway.chat(MESSAGES, "m", run_id="run_1")

    assert response.text == "Fine."
    [(_, status, _)] = writer.status_updates
    assert status == "succeeded"
    [cost] = writer.costs
    assert (cost["prompt_tokens"], cost["completion_tokens"]) == (7, 3)
