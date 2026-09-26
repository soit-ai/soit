"""Ollama is a first-class provider: its catalog, health and test calls."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.adapters.llm.ollama import ollama_openai_base_url, ollama_root_url
from app.adapters.llm.router import _default_native_factory
from app.modules.modelhub.infra.providers import ProviderCatalogAdapter

BASE = "http://ollama.internal:11434"

TAGS = {
    "models": [
        {
            "name": "llama3.2:latest",
            "model": "llama3.2:latest",
            "details": {"family": "llama", "parameter_size": "3.2B", "quantization_level": "Q4_K_M"},
        },
        {"name": "nomic-embed-text:latest", "model": "nomic-embed-text:latest", "details": {"family": "nomic-bert"}},
        {"name": "qwen2.5vl:7b", "model": "qwen2.5vl:7b", "details": {"family": "qwen25vl"}},
        {"name": "old-embedder:latest", "model": "old-embedder:latest", "details": {"families": ["bert"]}},
        {"name": "broken:latest", "model": "broken:latest", "details": {"family": "llama"}},
    ]
}

SHOW: dict[str, dict[str, Any]] = {
    "llama3.2:latest": {
        "capabilities": ["completion", "tools"],
        "model_info": {"general.architecture": "llama", "llama.context_length": 131072},
        "details": {"family": "llama"},
        "license": "a long licence the catalog must not keep",
    },
    "nomic-embed-text:latest": {
        "capabilities": ["embedding"],
        "model_info": {"nomic-bert.context_length": 2048},
    },
    "qwen2.5vl:7b": {
        "capabilities": ["completion", "vision"],
        "model_info": {"qwen25vl.context_length": 128000},
    },
    # A server too old to report capabilities.
    "old-embedder:latest": {"model_info": {}},
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


def _ollama(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/tags":
        return httpx.Response(200, json=TAGS)
    if request.url.path == "/api/show":
        name = json.loads(request.content)["model"]
        if name in SHOW:
            return httpx.Response(200, json=SHOW[name])
        return httpx.Response(500, json={"error": "model failed to load"})
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "0.12.3"})
    return httpx.Response(404)


def test_either_address_an_operator_pastes_finds_both_apis() -> None:
    for pasted in (BASE, f"{BASE}/", f"{BASE}/v1", f"{BASE}/v1/"):
        assert ollama_root_url(pasted) == BASE
        assert ollama_openai_base_url(pasted) == f"{BASE}/v1"
    assert ollama_root_url(None) == "http://localhost:11434"


@pytest.mark.asyncio
async def test_the_catalog_lists_models_with_their_context_and_capabilities(monkeypatch, ctx) -> None:
    seen = _serve(monkeypatch, _ollama)
    adapter = ProviderCatalogAdapter(egress_guard=AllowEgressGuard())  # type: ignore[arg-type]

    models = await adapter.list_models(ctx=ctx, provider_kind="ollama", api_key=None, base_url=f"{BASE}/v1")

    by_id = {item["model_id"]: item for item in models}
    assert list(by_id) == [tag["model"] for tag in TAGS["models"]]
    # The native API sits at the root even when the /v1 address was pasted.
    assert {str(request.url).split("/api/")[0] for request in seen} == {BASE}
    assert all("authorization" not in request.headers for request in seen)

    llama = by_id["llama3.2:latest"]
    assert llama["context_window"] == 131072
    assert llama["capabilities_json"]["model_type"] == "llm"
    assert llama["capabilities_json"]["capabilities"] == ["chat", "tools"]
    matrix = llama["raw_meta"]["modelhub"]["capability_matrix_json"]
    assert {name: entry["merged"] for name, entry in matrix.items()} == {
        "chat": True,
        "embeddings": False,
        "tools": True,
        "vision": False,
    }
    assert llama["raw_meta"]["modelhub"]["architecture_json"]["parameter_size"] == "3.2B"
    assert "license" not in json.dumps(llama["raw_meta"])

    embedder = by_id["nomic-embed-text:latest"]
    assert embedder["capabilities_json"]["model_type"] == "embedding"
    assert embedder["raw_meta"]["modelhub"]["diagnostics_json"] == {
        "test_chat_supported": False,
        "test_embeddings_supported": True,
    }
    assert by_id["qwen2.5vl:7b"]["capabilities_json"]["model_type"] == "multimodal"
    # Without reported capabilities the family decides, and a model /api/show
    # could not describe still lists as a chat model.
    assert by_id["old-embedder:latest"]["capabilities_json"]["model_type"] == "embedding"
    broken = by_id["broken:latest"]
    assert broken["capabilities_json"]["capabilities"] == ["chat"]
    assert broken["context_window"] is None


@pytest.mark.asyncio
async def test_a_key_is_sent_to_a_server_behind_a_proxy(monkeypatch, ctx) -> None:
    seen = _serve(monkeypatch, _ollama)
    adapter = ProviderCatalogAdapter(egress_guard=AllowEgressGuard())  # type: ignore[arg-type]

    await adapter.healthcheck(ctx=ctx, provider_kind="ollama", api_key="proxy-key", base_url=BASE)

    assert [request.url.path for request in seen] == ["/api/version"]
    assert seen[0].headers["authorization"] == "Bearer proxy-key"


@pytest.mark.asyncio
async def test_an_unreachable_server_fails_the_healthcheck(monkeypatch, ctx) -> None:
    _serve(monkeypatch, lambda request: httpx.Response(502))
    adapter = ProviderCatalogAdapter(egress_guard=AllowEgressGuard())  # type: ignore[arg-type]

    with pytest.raises(httpx.HTTPStatusError):
        await adapter.healthcheck(ctx=ctx, provider_kind="ollama", api_key=None, base_url=BASE)


@pytest.mark.asyncio
async def test_chat_and_embedding_tests_use_the_openai_compatible_address(monkeypatch, ctx) -> None:
    calls: list[tuple[str, str | None, str]] = []

    class FakeClient:
        def __init__(self, api_key: str, base_url: str | None = None, **kwargs: Any) -> None:
            del kwargs
            self.api_key = api_key
            self.base_url = base_url
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))
            self.embeddings = SimpleNamespace(create=self._embed)

        async def _chat(self, **kwargs: Any) -> Any:
            calls.append(("chat", self.base_url, self.api_key))
            return SimpleNamespace(
                id="chatcmpl-ollama",
                usage=SimpleNamespace(prompt_tokens=4, completion_tokens=2),
                choices=[SimpleNamespace(message=SimpleNamespace(content="pong"))],
            )

        async def _embed(self, **kwargs: Any) -> Any:
            calls.append(("embed", self.base_url, self.api_key))
            return SimpleNamespace(id=None, usage=SimpleNamespace(total_tokens=3))

    monkeypatch.setattr("app.modules.modelhub.infra.providers.AsyncOpenAI", FakeClient)
    adapter = ProviderCatalogAdapter(egress_guard=AllowEgressGuard())  # type: ignore[arg-type]

    chat = await adapter.test_chat(
        ctx=ctx, provider_kind="ollama", api_key=None, base_url=BASE, model_id="llama3.2", input_text="ping"
    )
    await adapter.test_embeddings(
        ctx=ctx,
        provider_kind="ollama",
        api_key=None,
        base_url=BASE,
        model_id="nomic-embed-text",
        input_text="ping",
    )

    assert chat["response"] == "pong"
    assert calls == [("chat", f"{BASE}/v1", "ollama"), ("embed", f"{BASE}/v1", "ollama")]


def test_the_native_backend_calls_ollama_through_its_v1() -> None:
    config = SimpleNamespace(kind="ollama", base_url=BASE, slug="local-ollama")

    port = _default_native_factory(config, {})  # type: ignore[arg-type]

    assert port.egress_base_url == f"{BASE}/v1"  # type: ignore[attr-defined]
