from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.modelhub.infra.providers import ProviderCatalogAdapter


class AllowEgressGuard:
    async def authorize(self, *args, **kwargs) -> None:
        return None


@pytest.mark.asyncio
async def test_openai_chat_test_uses_openai_client(monkeypatch, ctx):
    adapter = ProviderCatalogAdapter(egress_guard=AllowEgressGuard())

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
        def __init__(
            self,
            api_key: str,
            base_url: str | None = None,
            **kwargs,
        ):
            assert api_key == "test-key"
            assert base_url == "https://example.com/v1"
            self.chat = FakeChat()

    monkeypatch.setattr("app.modules.modelhub.infra.providers.AsyncOpenAI", FakeClient)

    result = await adapter.test_chat(
        ctx=ctx,
        provider_kind="openai_compatible",
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
async def test_anthropic_chat_test_uses_http_api(monkeypatch, ctx):
    adapter = ProviderCatalogAdapter(egress_guard=AllowEgressGuard())

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

    monkeypatch.setattr(
        "app.modules.modelhub.infra.providers.governed_httpx_client",
        lambda **kwargs: FakeClient(),
    )

    result = await adapter.test_chat(
        ctx=ctx,
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
async def test_anthropic_embedding_test_is_unsupported(ctx):
    adapter = ProviderCatalogAdapter()

    with pytest.raises(ValueError) as exc_info:
        await adapter.test_embeddings(
            ctx=ctx,
            provider_kind="anthropic",
            api_key="anthropic-key",
            base_url=None,
            model_id="claude-sonnet-4-6",
            input_text="hello",
        )

    assert "Embedding test not supported for provider: anthropic" in str(exc_info.value)


@pytest.mark.asyncio
async def test_anthropic_model_catalog_enriches_latest_claude_metadata(monkeypatch, ctx):
    adapter = ProviderCatalogAdapter(egress_guard=AllowEgressGuard())

    class FakeHttpResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {
                        "id": "claude-opus-4-8",
                        "display_name": "Claude Opus 4.8",
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                    {
                        "id": "claude-sonnet-4-6",
                        "display_name": "Claude Sonnet 4.6",
                    },
                    {
                        "id": "claude-haiku-4-5-20251001",
                        "display_name": "Claude Haiku 4.5",
                    },
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            assert url == "https://api.anthropic.com/v1/models?limit=200"
            assert headers["x-api-key"] == "anthropic-key"
            assert headers["anthropic-version"] == "2023-06-01"
            return FakeHttpResponse()

    monkeypatch.setattr(
        "app.modules.modelhub.infra.providers.governed_httpx_client",
        lambda **kwargs: FakeClient(),
    )

    result = await adapter.list_models(
        ctx=ctx,
        provider_kind="anthropic",
        api_key="anthropic-key",
        base_url=None,
    )

    by_id = {item["model_id"]: item for item in result}
    assert by_id["claude-opus-4-8"]["context_window"] == 1_000_000
    assert by_id["claude-opus-4-8"]["max_output_tokens"] == 128_000
    assert by_id["claude-opus-4-8"]["capabilities_json"]["modalities"]["input"] == ["text", "image"]
    assert by_id["claude-opus-4-8"]["raw_meta"]["modelhub"]["pricing_json"] == {
        "currency": "USD",
        "unit": "mtok",
        "input": 5.0,
        "output": 25.0,
    }
    assert by_id["claude-sonnet-4-6"]["context_window"] == 1_000_000
    assert by_id["claude-haiku-4-5-20251001"]["context_window"] == 200_000


@pytest.mark.asyncio
async def test_gemini_chat_test_uses_http_api(monkeypatch, ctx):
    adapter = ProviderCatalogAdapter(egress_guard=AllowEgressGuard())

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

    monkeypatch.setattr(
        "app.modules.modelhub.infra.providers.governed_httpx_client",
        lambda **kwargs: FakeClient(),
    )

    result = await adapter.test_chat(
        ctx=ctx,
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
