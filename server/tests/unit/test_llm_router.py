"""Unit tests for LLMRouterPort."""

import pytest

from app.adapters.llm.router import LLMRouterPort
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
)
from app.settings.settings import settings


class DummyPort(LLMPort):
    """Simple LLM port stub for routing tests."""

    def __init__(self):
        self.calls = []

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        self.calls.append(("chat", model))
        return ChatResponse(text="ok", model=model)

    async def embed(self, texts, model, **kwargs):
        self.calls.append(("embed", model))
        return EmbeddingResponse(embeddings=[[0.0]], model=model)

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        self.calls.append(("rerank", model))
        return RerankResponse(results=[], model=model)


@pytest.mark.asyncio
async def test_llm_router_routes_by_model_prefix(monkeypatch):
    monkeypatch.setattr(settings, "default_llm_provider", "openai")
    port = DummyPort()
    router = LLMRouterPort(providers={"openai": port})

    await router.chat([ChatMessage(role="user", content="hi")], model="model:openai:gpt-4")
    assert port.calls[-1] == ("chat", "model:openai:gpt-4")

    await router.embed(["hi"], model="openai:text-embedding")
    assert port.calls[-1] == ("embed", "openai:text-embedding")


@pytest.mark.asyncio
async def test_llm_router_uses_default_provider(monkeypatch):
    monkeypatch.setattr(settings, "default_llm_provider", "openai")
    port = DummyPort()
    router = LLMRouterPort(providers={"openai": port})

    await router.rerank("q", ["a"], model="gpt-4")
    assert port.calls[-1] == ("rerank", "gpt-4")


@pytest.mark.asyncio
async def test_llm_router_uses_default_provider_for_non_provider_colon_model(monkeypatch):
    monkeypatch.setattr(settings, "default_llm_provider", "openai")
    port = DummyPort()
    router = LLMRouterPort(providers={"openai": port})

    await router.chat([ChatMessage(role="user", content="hi")], model="deepseek-r1:8b")
    assert port.calls[-1] == ("chat", "deepseek-r1:8b")


@pytest.mark.asyncio
async def test_llm_router_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(settings, "default_llm_provider", "openai")
    router = LLMRouterPort(providers={})

    with pytest.raises(ValidationError):
        await router.chat([ChatMessage(role="user", content="hi")], model="model:unknown:gpt-4")
