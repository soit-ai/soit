"""DeepSeek is a first-class provider: its catalog, health and test calls."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.adapters.llm.deepseek import DeepSeekLLMPort
from app.kernel.commons.errors import ValidationError
from app.modules.modelhub.application.service import ModelHubService
from app.modules.modelhub.infra.providers import (
    DEEPSEEK_DEFAULT_BASE_URL,
    ProviderCatalogAdapter,
)

MODELS = {
    "object": "list",
    "data": [
        {"id": "deepseek-chat", "object": "model", "owned_by": "deepseek"},
        {"id": "deepseek-reasoner", "object": "model", "owned_by": "deepseek"},
        {"object": "model", "owned_by": "deepseek"},
    ],
}


class AllowEgressGuard:
    async def authorize(self, *args: Any, **kwargs: Any) -> None:
        return None


def _serve(monkeypatch, handler: Callable[[httpx.Request], httpx.Response]) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    @asynccontextmanager
    async def client(**kwargs: Any) -> AsyncIterator[httpx.AsyncClient]:
        del kwargs
        async with httpx.AsyncClient(transport=httpx.MockTransport(recording)) as http:
            yield http

    monkeypatch.setattr("app.modules.modelhub.infra.providers.governed_httpx_client", client)
    return seen


def _deepseek(request: httpx.Request) -> httpx.Response:
    if request.headers.get("authorization") != "Bearer sk-deepseek":
        return httpx.Response(401, json={"error": {"message": "Authentication Fails"}})
    if request.url.path.endswith("/models"):
        return httpx.Response(200, json=MODELS)
    return httpx.Response(404)


def _adapter() -> ProviderCatalogAdapter:
    return ProviderCatalogAdapter(egress_guard=AllowEgressGuard())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_the_catalog_lists_the_models_deepseek_answers(monkeypatch, ctx) -> None:
    seen = _serve(monkeypatch, _deepseek)

    models = await _adapter().list_models(
        ctx=ctx, provider_kind="deepseek", api_key="sk-deepseek", base_url=None
    )

    assert [str(request.url) for request in seen] == [f"{DEEPSEEK_DEFAULT_BASE_URL}/models"]
    # An item without an id is not a model.
    assert [item["model_id"] for item in models] == ["deepseek-chat", "deepseek-reasoner"]

    chat = models[0]
    assert chat["display_name"] == "deepseek-chat"
    assert chat["capabilities_json"] == {
        "model_type": "llm",
        "capabilities": ["chat"],
        "chat_supported": True,
        "embeddings_supported": False,
    }
    # The listing carries no limits, and none are invented.
    assert chat["context_window"] is None
    assert chat["max_output_tokens"] is None
    assert chat["lifecycle_status"] == "stable"
    assert chat["raw_meta"]["owned_by"] == "deepseek"
    meta = chat["raw_meta"]["modelhub"]
    assert {name: entry["merged"] for name, entry in meta["capability_matrix_json"].items()} == {
        "chat": True,
        "embeddings": False,
    }
    assert meta["diagnostics_json"] == {
        "test_chat_supported": True,
        "test_embeddings_supported": False,
    }
    assert meta["parameter_config_json"]["limits"]["context_window"] is None
    assert meta["pricing_json"] is None


@pytest.mark.asyncio
async def test_a_pasted_base_url_is_used_as_it_stands(monkeypatch, ctx) -> None:
    seen = _serve(monkeypatch, _deepseek)

    for pasted in ("https://gateway.example/v1", "https://gateway.example/v1/"):
        models = await _adapter().list_models(
            ctx=ctx, provider_kind="deepseek", api_key="sk-deepseek", base_url=pasted
        )
        assert len(models) == 2

    assert [str(request.url) for request in seen] == ["https://gateway.example/v1/models"] * 2


@pytest.mark.asyncio
async def test_a_rejected_key_fails_the_catalog_and_the_healthcheck(monkeypatch, ctx) -> None:
    seen = _serve(monkeypatch, _deepseek)

    with pytest.raises(httpx.HTTPStatusError) as listing:
        await _adapter().list_models(ctx=ctx, provider_kind="deepseek", api_key="wrong", base_url=None)
    with pytest.raises(httpx.HTTPStatusError) as health:
        await _adapter().healthcheck(ctx=ctx, provider_kind="deepseek", api_key="wrong", base_url=None)

    assert listing.value.response.status_code == 401
    assert health.value.response.status_code == 401
    # The healthcheck is the catalog call; nothing else is probed.
    assert [request.url.path for request in seen] == ["/models", "/models"]


@pytest.mark.asyncio
async def test_the_chat_test_calls_deepseek_through_the_openai_client(monkeypatch, ctx) -> None:
    calls: list[tuple[str | None, str, str]] = []

    class FakeClient:
        def __init__(self, api_key: str, base_url: str | None = None, **kwargs: Any) -> None:
            del kwargs
            self.api_key = api_key
            self.base_url = base_url
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))

        async def _chat(self, **kwargs: Any) -> Any:
            calls.append((self.base_url, self.api_key, kwargs["model"]))
            assert kwargs["max_tokens"] == 32
            return SimpleNamespace(
                id="chatcmpl-deepseek",
                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=1),
                choices=[SimpleNamespace(message=SimpleNamespace(content="pong"))],
            )

    monkeypatch.setattr("app.modules.modelhub.infra.providers.AsyncOpenAI", FakeClient)

    result = await _adapter().test_chat(
        ctx=ctx,
        provider_kind="deepseek",
        api_key="sk-deepseek",
        base_url=None,
        model_id="deepseek-chat",
        input_text="ping",
    )

    assert result["response"] == "pong"
    assert result["request_id"] == "chatcmpl-deepseek"
    assert calls == [(DEEPSEEK_DEFAULT_BASE_URL, "sk-deepseek", "deepseek-chat")]


@pytest.mark.asyncio
async def test_the_embeddings_test_says_deepseek_offers_none(monkeypatch, ctx) -> None:
    seen = _serve(monkeypatch, _deepseek)

    with pytest.raises(ValueError) as refused:
        await _adapter().test_embeddings(
            ctx=ctx,
            provider_kind="deepseek",
            api_key="sk-deepseek",
            base_url=None,
            model_id="deepseek-chat",
            input_text="hello",
        )

    assert "DeepSeek offers no embeddings endpoint" in str(refused.value)
    # Nothing is probed: the answer is known before any call.
    assert seen == []


@pytest.mark.asyncio
async def test_the_runtime_port_refuses_to_embed_or_rerank() -> None:
    port = DeepSeekLLMPort(api_key="sk-deepseek")

    with pytest.raises(ValidationError, match="no embeddings endpoint"):
        await port.embed(["hello"], model="deepseek-chat")
    with pytest.raises(ValidationError, match="cannot rerank"):
        await port.rerank("query", ["a", "b"], model="deepseek-chat")


def test_the_support_matrix_advertises_the_catalog_and_not_embeddings() -> None:
    deepseek = next(
        item for item in ModelHubService.PROVIDER_SUPPORT_MATRIX if item["provider_kind"] == "deepseek"
    )

    assert deepseek["catalog_supported"] is True
    assert deepseek["chat_supported"] is True
    assert deepseek["embeddings_supported"] is False
    assert "no embeddings endpoint" in str(deepseek["notes"])
