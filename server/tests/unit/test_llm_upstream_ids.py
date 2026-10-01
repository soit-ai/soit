"""Each adapter hands on the provider's own ids for a call, and never one an SDK made up."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.adapters.llm import gemini
from app.adapters.llm.anthropic import AnthropicLLMPort
from app.adapters.llm.openai import OpenAILLMPort
from app.adapters.llm.upstream_ids import clean_id, header_id, litellm_ids
from app.kernel.ports.llm.interface import ChatMessage

HELLO = [ChatMessage(role="user", content="Hello")]


def test_an_id_litellm_made_up_is_dropped_and_a_real_one_kept() -> None:
    made_up = SimpleNamespace(id="chatcmpl-1b4e28ba-2fa1-41d2-883f-0016d3cca427", _hidden_params={})
    real = SimpleNamespace(
        id="chatcmpl-AbC123",
        _hidden_params={"additional_headers": {"llm_provider-x-request-id": "req_42"}},
    )

    assert litellm_ids(made_up) == (None, None)
    assert litellm_ids(real) == ("chatcmpl-AbC123", "req_42")


def test_litellm_never_keeps_an_anthropic_response_id_but_keeps_its_request_id() -> None:
    response = SimpleNamespace(
        id="chatcmpl-whatever",
        _hidden_params={
            "custom_llm_provider": "anthropic",
            "additional_headers": {"llm_provider-request-id": "req_011"},
        },
    )

    assert litellm_ids(response) == (None, "req_011")


def test_ids_are_trimmed_and_capped() -> None:
    assert clean_id("  ") is None
    assert clean_id(7) is None
    assert clean_id("x" * 300) == "x" * 255
    assert header_id({"request-id": " req_1 "}, "x-request-id", "request-id") == "req_1"
    assert header_id(None, "x-request-id") is None


@pytest.mark.asyncio
async def test_openai_chat_carries_the_completion_id_and_the_request_id() -> None:
    port = OpenAILLMPort(api_key="test-key")
    completion = SimpleNamespace(
        id="chatcmpl-9xYz",
        _request_id="req_abc",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="hi", tool_calls=None),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=1),
    )
    port.client = MagicMock()
    port.client.chat.completions.create = AsyncMock(return_value=completion)

    response = await port.chat(HELLO, model="gpt-4")

    assert (response.upstream_id, response.upstream_request_id) == ("chatcmpl-9xYz", "req_abc")


@pytest.mark.asyncio
async def test_openai_stream_chunks_carry_the_completion_id_and_the_request_id() -> None:
    class Stream:
        response = SimpleNamespace(headers={"x-request-id": "req_stream"})

        def __aiter__(self):
            async def events():
                yield SimpleNamespace(
                    id="chatcmpl-s1",
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="hi", tool_calls=None), finish_reason="stop")],
                    usage=None,
                )

            return events()

    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.chat.completions.create = AsyncMock(return_value=Stream())

    chunks = [chunk async for chunk in port.stream_chat(HELLO, model="gpt-4")]

    assert {(chunk.upstream_id, chunk.upstream_request_id) for chunk in chunks} == {("chatcmpl-s1", "req_stream")}


class _AnthropicStream:
    headers = {"request-id": "req_stream_01"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in (
            'data: {"type":"message_start","message":{"id":"msg_01Stream","model":"claude-sonnet-4-6","usage":{"input_tokens":5}}}',
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hi"}}',
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":1}}',
            'data: {"type":"message_stop"}',
        ):
            yield line


@pytest.mark.asyncio
async def test_anthropic_chat_and_stream_carry_the_message_id_and_the_request_id(monkeypatch) -> None:
    class Response:
        headers = {"request-id": "req_01"}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "id": "msg_01ABC",
                "model": "claude-sonnet-4-6",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "hi"}],
                "usage": {"input_tokens": 5, "output_tokens": 1},
            }

    class Client:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc: Any) -> bool:
            return False

        async def post(self, *args: Any, **kwargs: Any) -> Response:
            return Response()

        def stream(self, *args: Any, **kwargs: Any) -> _AnthropicStream:
            return _AnthropicStream()

    monkeypatch.setattr("app.adapters.llm.anthropic.httpx.AsyncClient", Client)
    port = AnthropicLLMPort(api_key="anthropic-key")

    response = await port.chat(HELLO, model="model:anthropic:claude-sonnet-4-6", max_tokens=16)
    chunks = [
        chunk
        async for chunk in port.stream_chat(HELLO, model="model:anthropic:claude-sonnet-4-6", max_tokens=16)
    ]

    assert (response.upstream_id, response.upstream_request_id) == ("msg_01ABC", "req_01")
    assert chunks[-1].done is True
    assert {(chunk.upstream_id, chunk.upstream_request_id) for chunk in chunks} == {("msg_01Stream", "req_stream_01")}


@pytest.mark.asyncio
async def test_gemini_chat_carries_the_response_id(monkeypatch) -> None:
    real = httpx.AsyncClient

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "responseId": "gem-resp-7",
                "candidates": [{"content": {"role": "model", "parts": [{"text": "hi"}]}, "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 1},
            },
        )

    class Client(real):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(gemini.httpx, "AsyncClient", Client)

    response = await gemini.GeminiLLMPort(api_key="gk").chat(HELLO, "model:gemini:gemini-2.5-flash")

    assert response.upstream_id == "gem-resp-7"
    assert response.upstream_request_id is None
