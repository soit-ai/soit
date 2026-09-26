"""The official OpenAI Python SDK works against SOIT's /v1 unchanged.

These tests drive the SDK itself, not raw HTTP, so a change that breaks what
the SDK sends or parses fails here: response models, SSE framing, base64
embeddings, multipart image edits and error classes. LangChain's ChatOpenAI
and the OpenAI Agents SDK's chat-completions model call this same client, so
the request shapes they send are exercised here too.
"""

from __future__ import annotations

import base64
import io
import json
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import openai
import pytest
import pytest_asyncio
from PIL import Image
from pydantic import BaseModel

from app.kernel.ports.llm.interface import ChatStreamChunk, ToolCallDelta
from app.main import app
from app.modules.modelhub.domain.models import Provider, ProviderModel
from app.wiring import get_container

pytestmark = pytest.mark.asyncio

CHAT = "model:test:chat"
EMBEDDER = "model:test:embedder"
PAINTER = "model:test:painter"

LOOKUP_ORDER = {
    "type": "function",
    "function": {
        "name": "lookup_order",
        "description": "Find an order",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}


@pytest_asyncio.fixture
async def sdk(async_client) -> AsyncIterator[openai.AsyncOpenAI]:
    """An SDK client pointed at the app, as a user would point it at SOIT.

    ``async_client`` installs the test caller in place of API key auth; the
    SDK still sends its own ``Authorization: Bearer`` header.
    """
    del async_client
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield openai.AsyncOpenAI(
            api_key="sk-compat-not-a-real-key",
            base_url="http://testserver/v1",
            http_client=http,
            max_retries=0,
        )


class _ScriptedStream:
    """A model whose stream is scripted, for what the echo model cannot say."""

    def __init__(self, chunks: list[ChatStreamChunk]) -> None:
        self.chunks = chunks

    async def stream_chat(self, *args: Any, **kwargs: Any) -> AsyncIterator[ChatStreamChunk]:
        del args, kwargs
        for chunk in self.chunks:
            yield chunk


@contextmanager
def _llm_port(port: object) -> Iterator[None]:
    container = get_container()
    original = container.get("llm_port")
    container.register_singleton("llm_port", port)
    try:
        yield
    finally:
        container.register_singleton("llm_port", original)


def _png(color: tuple[int, int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (64, 64), color).save(buffer, format="PNG")
    return buffer.getvalue()


async def test_a_chat_completion_parses_into_the_sdk_types(sdk: openai.AsyncOpenAI) -> None:
    raw = await sdk.chat.completions.with_raw_response.create(
        model=CHAT,
        messages=[
            {"role": "developer", "content": "Be brief."},
            {"role": "user", "content": "hello sdk"},
        ],
        temperature=0.2,
        seed=7,
    )
    completion = raw.parse()

    assert completion.object == "chat.completion"
    assert completion.choices[0].message.content == "hello sdk"
    assert completion.choices[0].finish_reason == "stop"
    assert completion.usage is not None and completion.usage.total_tokens > 0
    # Every call is a governed run the caller can look up.
    assert completion.id == f"chatcmpl-{raw.headers['x-soit-run-id']}"


async def test_a_stream_yields_chunks_and_a_usage_chunk(sdk: openai.AsyncOpenAI) -> None:
    stream = await sdk.chat.completions.create(
        model=CHAT,
        messages=[{"role": "user", "content": "stream through the sdk"}],
        stream=True,
        stream_options={"include_usage": True},
    )
    chunks = [chunk async for chunk in stream]

    text = "".join(chunk.choices[0].delta.content or "" for chunk in chunks if chunk.choices)
    assert text == "stream through the sdk"
    assert chunks[-1].choices == []
    assert chunks[-1].usage is not None and chunks[-1].usage.total_tokens > 0


async def test_the_stream_helper_accumulates_the_final_message(sdk: openai.AsyncOpenAI) -> None:
    async with sdk.chat.completions.stream(
        model=CHAT, messages=[{"role": "user", "content": "accumulate me"}]
    ) as stream:
        async for _event in stream:
            pass
        final = await stream.get_final_completion()

    assert final.choices[0].message.content == "accumulate me"


async def test_a_tool_call_round_trip(sdk: openai.AsyncOpenAI) -> None:
    first = await sdk.chat.completions.create(
        model=CHAT,
        messages=[{"role": "user", "content": "find order 42"}],
        tools=[LOOKUP_ORDER],  # type: ignore[list-item]
        tool_choice="auto",
        # The OpenAI Agents SDK and LangChain send these alongside tools.
        parallel_tool_calls=False,
    )
    message = first.choices[0].message
    assert first.choices[0].finish_reason == "tool_calls"
    assert message.tool_calls is not None
    call = message.tool_calls[0]
    assert call.type == "function"
    assert call.function.name == "lookup_order"
    assert json.loads(call.function.arguments) == {"query": "find order 42"}

    second = await sdk.chat.completions.create(
        model=CHAT,
        messages=[
            {"role": "user", "content": "find order 42"},
            message.model_dump(exclude_none=True),  # type: ignore[list-item]
            {"role": "tool", "tool_call_id": call.id, "content": "order 42 shipped"},
        ],
        tools=[LOOKUP_ORDER],  # type: ignore[list-item]
    )
    assert second.choices[0].message.content == "order 42 shipped"


async def test_a_streamed_tool_call_arrives_whole(sdk: openai.AsyncOpenAI) -> None:
    # Providers stream a call as a name, then its arguments in fragments.
    scripted = _ScriptedStream(
        [
            ChatStreamChunk(
                tool_call_deltas=[
                    ToolCallDelta(index=0, id="call_7", name="lookup_order", arguments_delta='{"query"')
                ]
            ),
            ChatStreamChunk(tool_call_deltas=[ToolCallDelta(index=0, arguments_delta=': "order 7"}')]),
            ChatStreamChunk(done=True, finish_reason="tool_calls", tokens_prompt=5, tokens_completion=3),
        ]
    )
    names: list[str] = []
    arguments = ""
    finish: str | None = None
    with _llm_port(scripted):
        stream = await sdk.chat.completions.create(
            model=CHAT,
            messages=[{"role": "user", "content": "find order 7"}],
            tools=[LOOKUP_ORDER],  # type: ignore[list-item]
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            for choice in chunk.choices:
                for delta in choice.delta.tool_calls or []:
                    if delta.function and delta.function.name:
                        names.append(delta.function.name)
                    if delta.function and delta.function.arguments:
                        arguments += delta.function.arguments
                finish = choice.finish_reason or finish

    assert names == ["lookup_order"]
    assert json.loads(arguments) == {"query": "order 7"}
    assert finish == "tool_calls"


class Trip(BaseModel):
    city: str
    days: int


async def test_structured_output_parses_into_a_pydantic_model(sdk: openai.AsyncOpenAI) -> None:
    # The test model echoes; echoing JSON stands in for a model that obeys
    # the schema, which is what the SDK then validates.
    completion = await sdk.chat.completions.parse(
        model=CHAT,
        messages=[{"role": "user", "content": '{"city": "Lisbon", "days": 3}'}],
        response_format=Trip,
    )

    assert completion.choices[0].message.parsed == Trip(city="Lisbon", days=3)


async def test_embeddings_decode_from_the_sdk_default_base64(sdk: openai.AsyncOpenAI) -> None:
    # Without encoding_format the SDK asks for base64 and decodes it itself.
    result = await sdk.embeddings.create(model=EMBEDDER, input=["alpha", "beta"])
    as_floats = await sdk.embeddings.create(
        model=EMBEDDER, input=["alpha", "beta"], encoding_format="float"
    )

    assert [item.index for item in result.data] == [0, 1]
    assert all(len(item.embedding) > 0 for item in result.data)
    for decoded, plain in zip(result.data, as_floats.data, strict=True):
        assert decoded.embedding == pytest.approx(plain.embedding, rel=1e-6)
    assert result.usage.prompt_tokens > 0


async def test_models_lists_what_a_call_can_name(sdk: openai.AsyncOpenAI, async_db, ctx) -> None:
    scope = {"tenant_id": ctx.tenant_id, "workspace_id": ctx.workspace_id}
    provider = Provider(**scope, kind="openai", slug="openai-main", name="OpenAI main")
    async_db.add(provider)
    await async_db.flush()
    async_db.add(
        ProviderModel(**scope, provider_id=provider.id, provider_kind="openai", model_id="gpt-5.5")
    )
    await async_db.commit()

    ids = [model.id async for model in sdk.models.list()]

    assert "model:openai-main:gpt-5.5" in ids


async def test_images_generate_and_edit_through_the_sdk(sdk: openai.AsyncOpenAI) -> None:
    generated = await sdk.images.generate(
        model=PAINTER, prompt="a red dot", size="256x256", response_format="b64_json"
    )
    assert generated.data is not None and generated.data[0].b64_json
    Image.open(io.BytesIO(base64.b64decode(generated.data[0].b64_json))).verify()

    edited = await sdk.images.edit(
        model=PAINTER,
        image=("room.png", _png((200, 200, 200, 255)), "image/png"),
        mask=("mask.png", _png((0, 0, 0, 0)), "image/png"),
        prompt="paint the wall blue",
        response_format="b64_json",
    )
    assert edited.data is not None and edited.data[0].b64_json


async def test_refusals_raise_the_sdk_error_classes(sdk: openai.AsyncOpenAI) -> None:
    with pytest.raises(openai.BadRequestError) as too_many:
        await sdk.chat.completions.create(
            model=CHAT, messages=[{"role": "user", "content": "x"}], n=2
        )
    assert too_many.value.status_code == 400
    assert isinstance(too_many.value.body, dict) and too_many.value.body.get("message")

    with pytest.raises(openai.BadRequestError):
        await sdk.images.generate(model=PAINTER, prompt="x", size="9999x9999")  # type: ignore[arg-type]
