from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.modelhub.infra.providers import ProviderCatalogAdapter


@pytest.mark.asyncio
async def test_openai_chat_test_uses_openai_client(monkeypatch):
    adapter = ProviderCatalogAdapter()

    class FakeResponse:
        id = "resp_openai"
        usage = SimpleNamespace(prompt_tokens=11, completion_tokens=7)
        choices = [SimpleNamespace(message=SimpleNamespace(content="ok from openai"))]

    class FakeCompletions:
        async def create(self, **kwargs):
            assert kwargs["model"] == "gpt-4o-mini"
            assert kwargs["messages"][0]["content"] == "hello"
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, api_key: str, base_url: str | None = None):
            assert api_key == "test-key"
            assert base_url == "https://example.com/v1"
            self.chat = FakeChat()

    monkeypatch.setattr("app.modules.modelhub.infra.providers.AsyncOpenAI", FakeClient)

    result = await adapter.test_chat(
        provider_kind="openai_compat",
        api_key="test-key",
        base_url="https://example.com/v1",
        model_id="gpt-4o-mini",
        input_text="hello",
    )

    assert result["response"] == "ok from openai"
    assert result["tokens_prompt"] == 11
    assert result["tokens_completion"] == 7
    assert result["request_id"] == "resp_openai"


@pytest.mark.asyncio
async def test_anthropic_chat_test_uses_http_api(monkeypatch):
    adapter = ProviderCatalogAdapter()

    class FakeHttpResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "msg_123",
                "content": [{"type": "text", "text": "hello from anthropic"}],
                "usage": {
                    "input_tokens": 19,
                    "output_tokens": 13,
                },
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            assert url == "https://api.anthropic.com/v1/messages"
            assert headers["x-api-key"] == "anthropic-key"
            assert json["model"] == "claude-3-7-sonnet"
            return FakeHttpResponse()

    monkeypatch.setattr("app.modules.modelhub.infra.providers.httpx.AsyncClient", FakeClient)

    result = await adapter.test_chat(
        provider_kind="anthropic",
        api_key="anthropic-key",
        base_url=None,
        model_id="claude-3-7-sonnet",
        input_text="hello",
    )

    assert result["response"] == "hello from anthropic"
    assert result["tokens_prompt"] == 19
    assert result["tokens_completion"] == 13
    assert result["request_id"] == "msg_123"


@pytest.mark.asyncio
async def test_gemini_chat_test_uses_http_api(monkeypatch):
    adapter = ProviderCatalogAdapter()

    class FakeHttpResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "responseId": "gem_456",
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "hello from gemini"}],
                        }
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 17,
                    "candidatesTokenCount": 9,
                },
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, params=None, json=None):
            assert "gemini-2.0-flash:generateContent" in url
            assert params == {"key": "gemini-key"}
            assert json["contents"][0]["parts"][0]["text"] == "hello"
            return FakeHttpResponse()

    monkeypatch.setattr("app.modules.modelhub.infra.providers.httpx.AsyncClient", FakeClient)

    result = await adapter.test_chat(
        provider_kind="gemini",
        api_key="gemini-key",
        base_url=None,
        model_id="gemini-2.0-flash",
        input_text="hello",
    )

    assert result["response"] == "hello from gemini"
    assert result["tokens_prompt"] == 17
    assert result["tokens_completion"] == 9
    assert result["request_id"] == "gem_456"
