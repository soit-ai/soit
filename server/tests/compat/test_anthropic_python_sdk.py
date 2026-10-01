"""The official Anthropic Python SDK works against SOIT's /v1/messages unchanged.

These tests drive the SDK itself, not raw HTTP, so a change that breaks what
the SDK sends or parses fails here: response models, the named SSE events the
stream helper accumulates, tool use blocks, token counting, the models list and
error classes. Claude Code is built on this client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import contextmanager
from typing import Any

import anthropic
import httpx2
import pytest
import pytest_asyncio

from app.kernel.commons.errors import RateLimitExceededError
from app.kernel.ports.llm.interface import ChatStreamChunk, ToolCallDelta
from app.main import app
from app.modules.modelhub.domain.models import Provider, ProviderModel
from app.wiring import get_container

pytestmark = pytest.mark.asyncio

CHAT = "model:test:chat"

LOOKUP_ORDER: anthropic.types.ToolParam = {
    "name": "lookup_order",
    "description": "Find an order",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}


@pytest_asyncio.fixture
async def sdk(async_client) -> AsyncIterator[anthropic.AsyncAnthropic]:
    """An SDK client pointed at the app, as a user would point it at SOIT.

    ``async_client`` installs the test caller in place of API key auth; the
    SDK still sends its own ``x-api-key`` header.
    """
    del async_client
    # The SDK runs on httpx2, a fork of httpx, and refuses an httpx client.
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield anthropic.AsyncAnthropic(
            api_key="sk-compat-not-a-real-key",
            base_url="http://testserver",
            http_client=http,
            max_retries=0,
        )


class _ScriptedStream:
    """A model whose stream is scripted, for what the echo model cannot say."""

    def __init__(self, chunks: list[ChatStreamChunk], error: Exception | None = None) -> None:
        self.chunks = chunks
        self.error = error

    async def stream_chat(self, *args: Any, **kwargs: Any) -> AsyncIterator[ChatStreamChunk]:
        del args, kwargs
        for chunk in self.chunks:
            yield chunk
        if self.error is not None:
            raise self.error


@contextmanager
def _llm_port(port: object) -> Any:
    container = get_container()
    original = container.get("llm_port")
    container.register_singleton("llm_port", port)
    try:
        yield
    finally:
        container.register_singleton("llm_port", original)


async def test_a_message_parses_into_the_sdk_types(sdk: anthropic.AsyncAnthropic) -> None:
    raw = await sdk.messages.with_raw_response.create(
        model=CHAT,
        max_tokens=128,
        system="Be brief.",
        messages=[{"role": "user", "content": "hello sdk"}],
    )
    message = await raw.parse()

    assert message.type == "message" and message.role == "assistant"
    assert message.content[0].type == "text"
    assert message.content[0].text == "hello sdk"  # type: ignore[union-attr]
    assert message.stop_reason == "end_turn"
    assert message.usage.input_tokens > 0 and message.usage.output_tokens > 0
    # Every call is a governed run the caller can look up.
    assert message.id == f"msg_{raw.headers['x-soit-run-id']}"


async def test_a_stream_accumulates_into_the_final_message(sdk: anthropic.AsyncAnthropic) -> None:
    async with sdk.messages.stream(
        model=CHAT,
        max_tokens=128,
        messages=[{"role": "user", "content": "stream this please"}],
    ) as stream:
        text = "".join([part async for part in stream.text_stream])
        final = await stream.get_final_message()

    assert text == "stream this please"
    assert final.stop_reason == "end_turn"
    assert final.content[0].text == "stream this please"  # type: ignore[union-attr]
    assert final.usage.output_tokens > 0


async def test_tool_use_parses_into_a_tool_use_block(sdk: anthropic.AsyncAnthropic) -> None:
    message = await sdk.messages.create(
        model=CHAT,
        max_tokens=128,
        messages=[{"role": "user", "content": "find order 42"}],
        tools=[LOOKUP_ORDER],
        tool_choice={"type": "auto"},
    )

    assert message.stop_reason == "tool_use"
    block = message.content[-1]
    assert block.type == "tool_use"
    assert block.name == "lookup_order"  # type: ignore[union-attr]
    assert block.input == {"query": "find order 42"}  # type: ignore[union-attr]


async def test_a_tool_result_turn_round_trips(sdk: anthropic.AsyncAnthropic) -> None:
    first = await sdk.messages.create(
        model=CHAT,
        max_tokens=128,
        messages=[{"role": "user", "content": "find order 42"}],
        tools=[LOOKUP_ORDER],
    )
    call = first.content[-1]
    assert call.type == "tool_use"

    second = await sdk.messages.create(
        model=CHAT,
        max_tokens=128,
        messages=[
            {"role": "user", "content": "find order 42"},
            {"role": "assistant", "content": first.content},  # type: ignore[typeddict-item]
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,  # type: ignore[union-attr]
                        "content": "order 42 shipped",
                    }
                ],
            },
        ],
        tools=[LOOKUP_ORDER],
    )

    assert second.type == "message"


async def test_a_streamed_tool_call_assembles_its_input(sdk: anthropic.AsyncAnthropic) -> None:
    port = _ScriptedStream(
        [
            ChatStreamChunk(
                tool_call_deltas=[
                    ToolCallDelta(index=0, id="call_9", name="lookup_order", arguments_delta='{"query"')
                ]
            ),
            ChatStreamChunk(tool_call_deltas=[ToolCallDelta(index=0, arguments_delta=': "42"}')]),
            ChatStreamChunk(done=True, tokens_prompt=12, tokens_completion=6, finish_reason="tool_calls"),
        ]
    )
    with _llm_port(port):
        async with sdk.messages.stream(
            model=CHAT,
            max_tokens=128,
            messages=[{"role": "user", "content": "find order 42"}],
            tools=[LOOKUP_ORDER],
        ) as stream:
            final = await stream.get_final_message()

    assert final.stop_reason == "tool_use"
    block = final.content[-1]
    assert block.type == "tool_use"
    assert (block.id, block.name, block.input) == (  # type: ignore[union-attr]
        "call_9",
        "lookup_order",
        {"query": "42"},
    )
    assert (final.usage.input_tokens, final.usage.output_tokens) == (12, 6)


async def test_count_tokens_returns_an_estimate(sdk: anthropic.AsyncAnthropic) -> None:
    counted = await sdk.messages.count_tokens(
        model=CHAT,
        system="Be brief.",
        messages=[{"role": "user", "content": "how many tokens is this message"}],
        tools=[LOOKUP_ORDER],
    )

    assert counted.input_tokens > 10


async def test_models_list_parses_into_model_infos(
    sdk: anthropic.AsyncAnthropic, async_db, ctx
) -> None:
    scope = {"tenant_id": ctx.tenant_id, "workspace_id": ctx.workspace_id}
    provider = Provider(**scope, kind="openai", slug="compat", name="Compat")
    async_db.add(provider)
    async_db.add(
        ProviderModel(**scope, provider_id=provider.id, provider_kind="openai", model_id="lister")
    )
    await async_db.commit()

    page = await sdk.models.list()

    ids = [model.id for model in page.data]
    assert "model:compat:lister" in ids
    listed = next(model for model in page.data if model.id == "model:compat:lister")
    assert listed.type == "model" and listed.display_name
    assert listed.created_at is not None
    assert page.has_more is False


async def test_refusals_raise_the_sdks_error_classes(sdk: anthropic.AsyncAnthropic) -> None:
    with pytest.raises(anthropic.BadRequestError) as caught:
        await sdk.messages.create(
            model=CHAT,
            max_tokens=8,
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
        )
    assert caught.value.status_code == 400

    port = _ScriptedStream([], error=RateLimitExceededError("Slow down", {"retry_after": 9}))
    with _llm_port(port), pytest.raises(anthropic.RateLimitError) as limited:
        await sdk.messages.create(
            model=CHAT,
            max_tokens=8,
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
        )
    assert limited.value.status_code == 429
    assert limited.value.response.headers["retry-after"] == "9"
