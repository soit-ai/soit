"""Unit tests for the Anthropic LLM adapter."""

from __future__ import annotations

import pytest

from app.adapters.llm.anthropic import AnthropicLLMPort
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import ChatMessage


@pytest.mark.asyncio
async def test_anthropic_llm_chat_uses_messages_api(monkeypatch):
    captured = {}

    class FakeHttpResponse:
        headers = {"request-id": "req_header_123"}

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "msg_123",
                "model": "claude-sonnet-4-6",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "hello from claude"}],
                "usage": {"input_tokens": 21, "output_tokens": 8},
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeHttpResponse()

    monkeypatch.setattr("app.adapters.llm.anthropic.httpx.AsyncClient", FakeClient)
    port = AnthropicLLMPort(api_key="anthropic-key")

    response = await port.chat(
        messages=[
            ChatMessage(role="system", content="Be concise."),
            ChatMessage(role="user", content="Hello"),
        ],
        model="model:anthropic:claude-sonnet-4-6",
        temperature=0.2,
        max_tokens=128,
    )

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "anthropic-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"] == {
        "model": "claude-sonnet-4-6",
        "system": "Be concise.",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 128,
        "temperature": 0.2,
    }
    assert response.text == "hello from claude"
    assert response.tokens_prompt == 21
    assert response.tokens_completion == 8
    assert response.model == "claude-sonnet-4-6"
    assert response.finish_reason == "end_turn"


@pytest.mark.asyncio
async def test_anthropic_llm_stream_chat_yields_text_and_usage(monkeypatch):
    class FakeByteStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            lines = [
                'event: content_block_delta',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hel"}}',
                '',
                'event: content_block_delta',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"lo"}}',
                '',
                'event: message_delta',
                'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}}',
                '',
                'event: message_stop',
                'data: {"type":"message_stop"}',
                '',
            ]
            for line in lines:
                yield line

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, headers=None, json=None):
            assert method == "POST"
            assert json["stream"] is True
            assert json["model"] == "claude-sonnet-4-6"
            return FakeByteStream()

    monkeypatch.setattr("app.adapters.llm.anthropic.httpx.AsyncClient", FakeClient)
    port = AnthropicLLMPort(api_key="anthropic-key")

    chunks = [
        chunk
        async for chunk in port.stream_chat(
            messages=[ChatMessage(role="user", content="Hello")],
            model="model:anthropic:claude-sonnet-4-6",
            max_tokens=64,
        )
    ]

    assert [chunk.delta for chunk in chunks] == ["hel", "lo", ""]
    assert chunks[-1].done is True
    assert chunks[-1].tokens_completion == 2
    assert chunks[-1].finish_reason == "end_turn"


@pytest.mark.asyncio
async def test_anthropic_llm_embed_and_rerank_are_unsupported():
    port = AnthropicLLMPort(api_key="anthropic-key")

    with pytest.raises(ValidationError) as embed_error:
        await port.embed(["hello"], model="model:anthropic:claude-sonnet-4-6")

    with pytest.raises(ValidationError) as rerank_error:
        await port.rerank("hello", ["doc"], model="model:anthropic:claude-sonnet-4-6")

    assert "Embeddings are not supported" in embed_error.value.message
    assert "Rerank is not supported" in rerank_error.value.message


@pytest.mark.asyncio
async def test_anthropic_llm_chat_exposes_provider_thinking(monkeypatch):
    class FakeHttpResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "claude-sonnet-4-6",
                "stop_reason": "end_turn",
                "content": [
                    {"type": "thinking", "thinking": "Checked the evidence."},
                    {"type": "text", "text": "Done."},
                ],
                "usage": {"input_tokens": 3, "output_tokens": 2},
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeHttpResponse()

    monkeypatch.setattr("app.adapters.llm.anthropic.httpx.AsyncClient", FakeClient)
    port = AnthropicLLMPort(api_key="anthropic-key")

    response = await port.chat(
        [ChatMessage(role="user", content="Check this")],
        model="model:anthropic:claude-sonnet-4-6",
    )

    assert response.reasoning == "Checked the evidence."


@pytest.mark.asyncio
async def test_anthropic_llm_stream_exposes_thinking_delta(monkeypatch):
    class FakeByteStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield 'data: {"type":"content_block_delta","delta":{"type":"thinking_delta","thinking":"Checking."}}'
            yield 'data: {"type":"message_stop"}'

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, *args, **kwargs):
            return FakeByteStream()

    monkeypatch.setattr("app.adapters.llm.anthropic.httpx.AsyncClient", FakeClient)
    port = AnthropicLLMPort(api_key="anthropic-key")

    chunks = [
        chunk
        async for chunk in port.stream_chat(
            [ChatMessage(role="user", content="Check this")],
            model="model:anthropic:claude-sonnet-4-6",
        )
    ]

    assert chunks[0].reasoning_delta == "Checking."
