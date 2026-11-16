"""Model provider ports reuse one pooled HTTP client per event loop."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from app.adapters.http import shared_client
from app.adapters.http.shared_client import (
    close_shared_http_clients,
    pooled_http_client,
    shared_http_client,
)
from app.adapters.llm import anthropic as anthropic_module
from app.adapters.llm.anthropic import AnthropicLLMPort
from app.adapters.llm.openai import OpenAILLMPort
from app.kernel.ports.llm.interface import ChatMessage


@pytest.mark.asyncio
async def test_one_client_per_loop_and_timeout() -> None:
    first = shared_http_client(10.0)
    assert shared_http_client(10.0) is first
    assert shared_http_client(20.0) is not first
    async with pooled_http_client(10.0) as client:
        assert client is first
    # Leaving the context keeps the shared client open.
    assert not first.is_closed

    await close_shared_http_clients()

    assert first.is_closed
    assert shared_http_client(10.0) is not first
    await close_shared_http_clients()


def test_a_fresh_loop_gets_its_own_client() -> None:
    async def grab() -> httpx.AsyncClient:
        client = shared_http_client(5.0)
        await close_shared_http_clients()
        return client

    assert asyncio.run(grab()) is not asyncio.run(grab())


def test_no_running_loop_is_an_error() -> None:
    with pytest.raises(RuntimeError):
        shared_http_client()


@pytest.mark.asyncio
async def test_openai_ports_built_per_request_share_the_pool() -> None:
    first = OpenAILLMPort(api_key="k1", base_url="https://one.example/v1")
    second = OpenAILLMPort(api_key="k2", base_url="https://two.example/v1")

    assert first.client._client is second.client._client
    assert first.client._client is shared_http_client()
    await close_shared_http_clients()


def test_openai_port_built_outside_a_loop_keeps_its_own_client() -> None:
    port = OpenAILLMPort(api_key="k", base_url="https://static.example/v1")

    assert isinstance(port.client._client, httpx.AsyncClient)


@pytest.mark.asyncio
async def test_anthropic_calls_reuse_the_pooled_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[dict[str, Any]] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "msg_1",
                "model": "claude",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "hi"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    real = httpx.AsyncClient

    class Client(real):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            built.append(kwargs)
            super().__init__(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(anthropic_module.httpx, "AsyncClient", Client)
    monkeypatch.setattr(shared_client.httpx, "AsyncClient", Client)
    hello = [ChatMessage(role="user", content="hi")]

    for _ in range(3):
        port = AnthropicLLMPort(api_key="key", timeout=30)
        await port.chat(hello, model="claude", max_tokens=8)

    assert len(built) == 1
    assert built[0]["follow_redirects"] is False
    await close_shared_http_clients()
