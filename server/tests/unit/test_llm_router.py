"""Unit tests for LLMRouterPort."""

from unittest.mock import MagicMock

import pytest

from app.adapters.llm.router import LLMRouterPort, RuntimeProviderConfig
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
        self.last_kwargs = {}

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        self.calls.append(("chat", model))
        self.last_kwargs = kwargs
        return ChatResponse(text="ok", model=model)

    async def embed(self, texts, model, **kwargs):
        self.calls.append(("embed", model))
        return EmbeddingResponse(embeddings=[[0.0]], model=model)

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        self.calls.append(("rerank", model))
        return RerankResponse(results=[], model=model)


class UpstreamNamedPort(DummyPort):
    """Return a provider-native model name instead of the SOIT model reference."""

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        self.calls.append(("chat", model))
        self.last_kwargs = kwargs
        return ChatResponse(
            text="ok",
            model="gpt-4.1-mini-2025-04-14",
            tokens_prompt=7,
            tokens_completion=3,
        )


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


@pytest.mark.asyncio
async def test_llm_router_adds_litellm_adapter_for_workspace_provider(ctx):
    litellm_port = DummyPort()
    secrets = type(
        "Secrets",
        (),
        {"get_secret": lambda self, **kwargs: _secret_value(kwargs)},
    )()

    def resolve_provider(request_ctx, slug):
        assert request_ctx is ctx
        assert slug == "team-gateway"
        return RuntimeProviderConfig(
            slug=slug,
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
            base_url="https://llm.example.com/v1",
            credential_ref="secret:team-gateway",
            timeout=45.0,
            max_retries=4,
        )

    captured = {}

    def make_litellm(config, credentials):
        captured.update(config=config, credentials=credentials)
        return litellm_port

    router = LLMRouterPort(
        providers={"openai": DummyPort()},
        provider_resolver=resolve_provider,
        secrets_resolver=lambda request_ctx: secrets,
        litellm_factory=make_litellm,
    )

    await router.chat(
        [ChatMessage(role="user", content="hi")],
        model="model:team-gateway:gpt-4.1-mini",
        ctx=ctx,
    )

    assert litellm_port.calls == [("chat", "model:team-gateway:gpt-4.1-mini")]
    assert captured["credentials"] == {"api_key": "resolved-secret"}
    assert captured["config"].base_url == "https://llm.example.com/v1"


@pytest.mark.asyncio
async def test_llm_router_awaits_async_workspace_provider_resolver(ctx):
    port = DummyPort()

    async def resolve_provider(request_ctx, slug):
        assert request_ctx is ctx
        return RuntimeProviderConfig(
            slug=slug,
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
        )

    router = LLMRouterPort(
        providers={},
        provider_resolver=resolve_provider,
        litellm_factory=lambda config, api_key: port,
    )

    await router.chat(
        [ChatMessage(role="user", content="hi")],
        model="model:async-provider:gpt-test",
        ctx=ctx,
    )

    assert port.calls == [("chat", "model:async-provider:gpt-test")]


@pytest.mark.asyncio
async def test_llm_router_resolves_multiple_litellm_secret_bindings(ctx):
    port = DummyPort()
    captured = {}

    class _Secrets:
        async def get_secret(self, *, secret_ref):
            return {
                "secret:aws-access": "access-value",
                "secret:aws-secret": "secret-value",
            }[secret_ref]

    router = LLMRouterPort(
        providers={},
        provider_resolver=lambda request_ctx, slug: RuntimeProviderConfig(
            slug=slug,
            kind="bedrock",
            adapter_backend="litellm",
            status="active",
            litellm_provider="bedrock",
            secret_bindings={
                "aws_access_key_id": "secret:aws-access",
                "aws_secret_access_key": "secret:aws-secret",
            },
        ),
        secrets_resolver=lambda request_ctx: _Secrets(),
        litellm_factory=lambda config, credentials: (
            captured.update(config=config, credentials=credentials) or port
        ),
    )

    await router.chat(
        [ChatMessage(role="user", content="hi")],
        model="model:bedrock-main:anthropic.claude-3-5-sonnet",
        ctx=ctx,
    )

    assert captured["config"].litellm_provider == "bedrock"
    assert captured["credentials"] == {
        "aws_access_key_id": "access-value",
        "aws_secret_access_key": "secret-value",
    }


async def _secret_value(kwargs):
    assert kwargs["secret_ref"] == "secret:team-gateway"
    return "resolved-secret"


@pytest.mark.asyncio
async def test_llm_router_keeps_native_ports_for_native_workspace_provider(ctx):
    native = DummyPort()
    router = LLMRouterPort(
        providers={"openai": native},
        provider_resolver=lambda request_ctx, slug: RuntimeProviderConfig(
            slug=slug,
            kind="openai",
            adapter_backend="native",
            status="active",
        ),
    )

    await router.chat(
        [ChatMessage(role="user", content="hi")],
        model="model:team-openai:gpt-4.1-mini",
        ctx=ctx,
    )

    assert native.calls == [("chat", "model:team-openai:gpt-4.1-mini")]


@pytest.mark.asyncio
async def test_llm_router_rejects_disabled_workspace_provider(ctx):
    router = LLMRouterPort(
        providers={"openai": DummyPort()},
        provider_resolver=lambda request_ctx, slug: RuntimeProviderConfig(
            slug=slug,
            kind="openai",
            adapter_backend="native",
            status="disabled",
        ),
    )

    with pytest.raises(ValidationError, match="disabled"):
        await router.chat(
            [ChatMessage(role="user", content="hi")],
            model="model:team-openai:gpt-4.1-mini",
            ctx=ctx,
        )


@pytest.mark.asyncio
async def test_llm_policy_gateway_passes_request_context_to_router(ctx):
    from app.kernel.ports.llm.policy import LLMPolicyGateway

    port = DummyPort()
    gateway = LLMPolicyGateway(port, ctx, max_retries=0)

    await gateway.chat([ChatMessage(role="user", content="hi")], model="model:openai:gpt-4")

    assert port.last_kwargs["ctx"] is ctx


@pytest.mark.asyncio
async def test_llm_policy_records_runtime_identity_separately_from_upstream_model(ctx):
    from app.kernel.ports.llm.policy import LLMPolicyGateway

    port = UpstreamNamedPort()
    router = LLMRouterPort(
        providers={"openai": DummyPort()},
        provider_resolver=lambda request_ctx, slug: RuntimeProviderConfig(
            provider_id="provider-team-gateway",
            slug=slug,
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
        ),
        litellm_factory=lambda config, api_key: port,
    )
    writer = MagicMock()
    step = MagicMock()
    step.id = "step-runtime-identity"
    writer.create_step.return_value = step
    gateway = LLMPolicyGateway(router, ctx, trace_writer=writer, max_retries=1)

    await gateway.chat(
        [ChatMessage(role="user", content="hi")],
        model="model:team-gateway:gpt-4.1-mini",
        run_id="run-runtime-identity",
    )

    token_cost = next(
        call for call in writer.record_cost.call_args_list if call.kwargs["unit"] == "tokens"
    )
    assert token_cost.kwargs["provider"] == "openai_compatible"
    assert token_cost.kwargs["provider_id"] == "provider-team-gateway"
    assert token_cost.kwargs["provider_slug"] == "team-gateway"
    assert token_cost.kwargs["provider_kind"] == "openai_compatible"
    assert token_cost.kwargs["model_ref"] == "model:team-gateway:gpt-4.1-mini"
    assert token_cost.kwargs["upstream_model"] == "gpt-4.1-mini-2025-04-14"


@pytest.mark.asyncio
async def test_llm_policy_uses_resolved_provider_timeout_and_retry_policy(ctx):
    import asyncio

    from app.kernel.commons.errors import TimeoutError
    from app.kernel.ports.llm.policy import LLMPolicyGateway

    attempts = 0
    resolutions = 0

    class SlowPort(DummyPort):
        async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
            nonlocal attempts
            attempts += 1
            await asyncio.sleep(0.02)
            return ChatResponse(text="late", model="upstream-model")

    def resolve_provider(_request_ctx, slug):
        nonlocal resolutions
        resolutions += 1
        return RuntimeProviderConfig(
            provider_id="provider-timeout",
            slug=slug,
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
            timeout=0.001,
            max_retries=1,
            retry_backoff="none",
        )

    router = LLMRouterPort(
        providers={},
        provider_resolver=resolve_provider,
        litellm_factory=lambda config, api_key: SlowPort(),
    )
    gateway = LLMPolicyGateway(
        router,
        ctx,
        timeout_seconds=1,
        max_retries=0,
        retry_backoff_base_seconds=0,
    )

    with pytest.raises(TimeoutError):
        await gateway.chat(
            [ChatMessage(role="user", content="hi")],
            model="model:timeout-provider:gpt-timeout",
        )

    assert resolutions == 1
    assert attempts == 2
