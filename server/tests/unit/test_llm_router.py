"""Unit tests for LLMRouterPort."""

from unittest.mock import MagicMock

import pytest

from app.adapters.llm.router import LLMRouterPort, RuntimeProviderConfig
from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
)
from app.kernel.security.egress import GovernedEgressGuard
from app.settings.settings import settings


@pytest.fixture(autouse=True)
def _configure_router_unit_environment(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")

    async def allow_egress(*_args, **_kwargs):
        return None

    monkeypatch.setattr(GovernedEgressGuard, "authorize", allow_egress)


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

    def resolve_provider(request_ctx, slug, model_id):
        assert request_ctx is ctx
        assert slug == "team-gateway"
        assert model_id == "gpt-4.1-mini"
        return RuntimeProviderConfig(
            slug=slug,
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
            base_url="https://llm.example.com/v1",
            credential_secret_id="sec_team_gateway",
            timeout=45.0,
            max_retries=4,
            provider_model_id="model-1",
            model_id=model_id,
            model_status="active",
            capability_matrix={"chat": {"merged": True}},
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

    async def resolve_provider(request_ctx, slug, model_id):
        assert request_ctx is ctx
        return RuntimeProviderConfig(
            slug=slug,
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
            provider_model_id="model-1",
            model_id=model_id,
            model_status="active",
            capability_matrix={"chat": {"merged": True}},
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
        async def get_secret(self, *, secret_id):
            return {
                "sec_aws_access": "access-value",
                "sec_aws_secret": "secret-value",
            }[secret_id]

    router = LLMRouterPort(
        providers={},
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            slug=slug,
            kind="bedrock",
            adapter_backend="litellm",
            status="active",
            litellm_provider="bedrock",
            secret_bindings={
                "aws_access_key_id": "sec_aws_access",
                "aws_secret_access_key": "sec_aws_secret",
            },
            provider_model_id="model-1",
            model_id=model_id,
            model_status="active",
            capability_matrix={"chat": {"merged": True}},
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
    assert kwargs["secret_id"] == "sec_team_gateway"
    return "resolved-secret"


@pytest.mark.asyncio
async def test_llm_router_builds_native_port_from_scoped_provider_config(ctx):
    ports = [DummyPort(), DummyPort()]
    captured = []

    class _Secrets:
        async def get_secret(self, *, secret_id):
            return {
                "sec_team_openai_a": "key-a",
                "sec_team_openai_b": "key-b",
            }[secret_id]

    def resolve_provider(_request_ctx, slug, model_id):
        suffix = slug.rsplit("-", 1)[-1]
        return RuntimeProviderConfig(
            slug=slug,
            kind="openai",
            adapter_backend="native",
            status="active",
            base_url=f"https://{suffix}.example.com/v1",
            credential_secret_id=f"sec_team_openai_{suffix}",
            provider_model_id=f"model-{suffix}",
            model_id=model_id,
            model_status="active",
            capability_matrix={"chat": {"merged": True}},
        )

    def make_native(config, credentials):
        captured.append((config, credentials))
        return ports[len(captured) - 1]

    router = LLMRouterPort(
        providers={},
        provider_resolver=resolve_provider,
        secrets_resolver=lambda request_ctx: _Secrets(),
        native_factory=make_native,
    )

    await router.chat(
        [ChatMessage(role="user", content="hi")],
        model="model:team-openai-a:gpt-4.1-mini",
        ctx=ctx,
    )
    await router.chat(
        [ChatMessage(role="user", content="hi")],
        model="model:team-openai-b:gpt-4.1-mini",
        ctx=ctx,
    )

    assert ports[0].calls == [("chat", "model:team-openai-a:gpt-4.1-mini")]
    assert ports[1].calls == [("chat", "model:team-openai-b:gpt-4.1-mini")]
    assert captured[0][0].base_url == "https://a.example.com/v1"
    assert captured[1][0].base_url == "https://b.example.com/v1"
    assert captured[0][1] == {"api_key": "key-a"}
    assert captured[1][1] == {"api_key": "key-b"}


@pytest.mark.asyncio
async def test_llm_router_rejects_disabled_workspace_provider(ctx):
    router = LLMRouterPort(
        providers={"openai": DummyPort()},
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            slug=slug,
            kind="openai",
            adapter_backend="native",
            status="disabled",
            provider_model_id="model-1",
            model_id=model_id,
            model_status="active",
        ),
    )

    with pytest.raises(KernelError) as exc_info:
        await router.chat(
            [ChatMessage(role="user", content="hi")],
            model="model:team-openai:gpt-4.1-mini",
            ctx=ctx,
        )

    assert exc_info.value.code == "MODEL_PROVIDER_DISABLED"


@pytest.mark.asyncio
async def test_llm_router_rejects_inactive_model_with_stable_code(ctx):
    router = LLMRouterPort(
        providers={},
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            slug=slug,
            kind="openai",
            adapter_backend="native",
            status="active",
            provider_model_id="model-disabled",
            model_id=model_id,
            model_status="disabled",
        ),
    )

    with pytest.raises(KernelError) as exc_info:
        await router.chat(
            [ChatMessage(role="user", content="hi")],
            model="model:team-openai:gpt-disabled",
            ctx=ctx,
        )

    assert exc_info.value.code == "MODEL_RUNTIME_DISABLED"


@pytest.mark.asyncio
async def test_llm_router_rejects_explicitly_unsupported_capability(ctx):
    router = LLMRouterPort(
        providers={},
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            slug=slug,
            kind="openai",
            adapter_backend="native",
            status="active",
            provider_model_id="model-chat-only",
            model_id=model_id,
            model_status="active",
            capability_matrix={"embeddings": {"merged": False}},
        ),
    )

    with pytest.raises(KernelError) as exc_info:
        await router.embed(
            ["hello"],
            model="model:team-openai:gpt-chat-only",
            ctx=ctx,
        )

    assert exc_info.value.code == "MODEL_CAPABILITY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_llm_router_uses_provider_preset_only_for_unspecified_capability(ctx):
    port = DummyPort()
    router = LLMRouterPort(
        providers={},
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            slug=slug,
            kind="openai",
            adapter_backend="native",
            status="active",
            provider_model_id="model-without-matrix",
            model_id=model_id,
            model_status="active",
        ),
        native_factory=lambda config, credentials: port,
    )

    await router.embed(
        ["hello"],
        model="model:team-openai:text-embedding-3-small",
        ctx=ctx,
    )

    assert port.calls == [("embed", "model:team-openai:text-embedding-3-small")]


@pytest.mark.asyncio
async def test_llm_router_defaults_unknown_provider_capability_to_false(ctx):
    router = LLMRouterPort(
        providers={},
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            slug=slug,
            kind="company_gateway",
            adapter_backend="native",
            status="active",
            provider_model_id="model-unknown",
            model_id=model_id,
            model_status="active",
        ),
    )

    with pytest.raises(KernelError) as exc_info:
        await router.chat(
            [ChatMessage(role="user", content="hi")],
            model="model:company:model-a",
            ctx=ctx,
        )

    assert exc_info.value.code == "MODEL_CAPABILITY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_llm_router_requires_canonical_model_ref_in_production(ctx, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    router = LLMRouterPort(
        providers={"openai": DummyPort()},
        provider_resolver=lambda request_ctx, slug, model_id: None,
    )

    with pytest.raises(KernelError) as exc_info:
        await router.chat(
            [ChatMessage(role="user", content="hi")],
            model="gpt-4.1-mini",
            ctx=ctx,
        )

    assert exc_info.value.code == "MODEL_REF_INVALID"


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
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            provider_id="provider-team-gateway",
            slug=slug,
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
            provider_model_id="model-1",
            model_id=model_id,
            model_status="active",
            capability_matrix={"chat": {"merged": True}},
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
        call for call in writer.record_cost.call_args_list if call.kwargs["billing_basis"] == "tokens"
    )
    assert token_cost.kwargs["provider"] == "openai_compatible"
    assert token_cost.kwargs["provider_id"] == "provider-team-gateway"
    assert token_cost.kwargs["provider_slug"] == "team-gateway"
    assert token_cost.kwargs["provider_kind"] == "openai_compatible"
    assert token_cost.kwargs["model_ref"] == "model:team-gateway:gpt-4.1-mini"
    assert token_cost.kwargs["upstream_model"] == "gpt-4.1-mini-2025-04-14"


@pytest.mark.asyncio
async def test_llm_policy_records_one_priced_usage_row_for_valid_model_pricing(ctx):
    from decimal import Decimal

    from app.kernel.ports.llm.policy import LLMPolicyGateway

    port = UpstreamNamedPort()
    router = LLMRouterPort(
        providers={},
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            provider_id="provider-priced",
            slug=slug,
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
            provider_model_id="model-priced",
            model_id=model_id,
            model_status="active",
            capability_matrix={"chat": {"merged": True}},
            pricing={
                "currency": "USD",
                "pricing_source": "catalog",
                "prompt": {"amount": 1, "unit": "1M_tokens"},
                "completion": {"amount": 2, "unit": "1M_tokens"},
            },
        ),
        litellm_factory=lambda config, credentials: port,
    )
    writer = MagicMock()
    writer.create_step.return_value.id = "step-priced"
    gateway = LLMPolicyGateway(router, ctx, trace_writer=writer)

    await gateway.chat(
        [ChatMessage(role="user", content="hi")],
        model="model:priced:gpt-priced",
        run_id="run-priced",
    )

    usages = [
        call
        for call in writer.record_cost.call_args_list
        if call.kwargs.get("billing_basis") == "tokens"
    ]
    assert len(usages) == 1
    assert usages[0].kwargs.get("entry_type") is None
    assert usages[0].kwargs["currency"] == "USD"
    assert usages[0].kwargs["amount"] == Decimal("0.000013")
    snapshot = usages[0].kwargs["pricing_snapshot_json"]
    assert snapshot["model"] == {
        "requested": "model:priced:gpt-priced",
        "resolved": "model:priced:gpt-priced",
        "upstream": "gpt-4.1-mini-2025-04-14",
    }
    assert snapshot["billing_basis"] == "tokens"
    assert snapshot["billing_unit"] == "1m_tokens"
    assert snapshot["unit_size"] == 1_000_000
    assert snapshot["rates"]["input"]["price"] == "1"
    assert snapshot["rates"]["output"]["price"] == "2"
    assert snapshot["configured_pricing"]["pricing_source"] == "catalog"
    assert snapshot["configured_pricing"]["prompt"] == {
        "amount": 1,
        "unit": "1M_tokens",
    }


@pytest.mark.asyncio
async def test_llm_policy_keeps_unpriced_usage_when_chat_pricing_is_incomplete(ctx):
    from app.kernel.ports.llm.policy import LLMPolicyGateway

    port = UpstreamNamedPort()
    router = LLMRouterPort(
        providers={},
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            provider_id="provider-partial-priced",
            slug=slug,
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
            provider_model_id="model-partial",
            model_id=model_id,
            model_status="active",
            capability_matrix={"chat": {"merged": True}},
            pricing={
                "currency": "USD",
                "unit": "mtok",
                "input": 1,
            },
        ),
        litellm_factory=lambda config, credentials: port,
    )
    writer = MagicMock()
    writer.create_step.return_value.id = "step-partial"
    gateway = LLMPolicyGateway(router, ctx, trace_writer=writer)

    await gateway.chat(
        [ChatMessage(role="user", content="hi")],
        model="model:partial:gpt-partial",
        run_id="run-partial",
    )

    usages = [
        call
        for call in writer.record_cost.call_args_list
        if call.kwargs.get("billing_basis") == "tokens"
    ]
    assert len(usages) == 1
    assert usages[0].kwargs["currency"] is None
    assert usages[0].kwargs["amount"] is None
    snapshot = usages[0].kwargs["pricing_snapshot_json"]
    assert snapshot["priced"] is False
    assert snapshot["reason"] == "unsupported_pricing_config"
    assert snapshot["configured_pricing"]["input"] == 1


@pytest.mark.asyncio
async def test_llm_policy_records_one_priced_embed_usage_row(ctx):
    from decimal import Decimal

    from app.kernel.ports.llm.policy import LLMPolicyGateway

    class MeteredEmbedPort(DummyPort):
        async def embed(self, texts, model, **kwargs):
            self.calls.append(("embed", model))
            return EmbeddingResponse(
                embeddings=[[0.0]],
                tokens_used=1000,
                model=model,
            )

    port = MeteredEmbedPort()
    router = LLMRouterPort(
        providers={},
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            provider_id="provider-embed",
            slug=slug,
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
            provider_model_id="model-embed",
            model_id=model_id,
            model_status="active",
            capability_matrix={"embeddings": {"merged": True}},
            pricing={
                "currency": "USD",
                "unit": "mtok",
                "input": 0.1,
            },
        ),
        litellm_factory=lambda config, credentials: port,
    )
    writer = MagicMock()
    writer.create_step.return_value.id = "step-embed-priced"
    gateway = LLMPolicyGateway(router, ctx, trace_writer=writer)

    await gateway.embed(
        ["hello"],
        model="model:embed-priced:embedder",
        run_id="run-embed-priced",
    )

    usages = [
        call
        for call in writer.record_cost.call_args_list
        if call.kwargs.get("billing_basis") == "embeddings"
    ]
    assert len(usages) == 1
    assert usages[0].kwargs["prompt_tokens"] == 1000
    assert usages[0].kwargs["total_tokens"] == 1000
    assert usages[0].kwargs["currency"] == "USD"
    assert usages[0].kwargs["amount"] == Decimal("0.0001")
    assert usages[0].kwargs["billed_quantity"] == 1
    snapshot = usages[0].kwargs["pricing_snapshot_json"]
    assert snapshot["billing_basis"] == "tokens"
    assert snapshot["unit_size"] == 1_000_000
    assert snapshot["quantities"]["prompt_tokens"] == 1000


@pytest.mark.asyncio
async def test_llm_policy_records_one_priced_rerank_usage_row(ctx):
    from decimal import Decimal

    from app.kernel.ports.llm.policy import LLMPolicyGateway

    class MeteredRerankPort(DummyPort):
        async def rerank(self, query, documents, model, top_n=None, **kwargs):
            self.calls.append(("rerank", model))
            return RerankResponse(results=[], tokens_used=500, model=model)

    port = MeteredRerankPort()
    router = LLMRouterPort(
        providers={},
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            provider_id="provider-rerank",
            slug=slug,
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
            provider_model_id="model-rerank",
            model_id=model_id,
            model_status="active",
            capability_matrix={"rerank": {"merged": True}},
            pricing={
                "currency": "USD",
                "search": 2.0,
                "search_unit": "1k_searches",
            },
        ),
        litellm_factory=lambda config, credentials: port,
    )
    writer = MagicMock()
    writer.create_step.return_value.id = "step-rerank-priced"
    gateway = LLMPolicyGateway(router, ctx, trace_writer=writer)

    await gateway.rerank(
        "query",
        ["a", "b", "c", "d"],
        model="model:rerank-priced:reranker",
        run_id="run-rerank-priced",
    )

    usages = [
        call
        for call in writer.record_cost.call_args_list
        if call.kwargs.get("billing_basis") == "rerank"
    ]
    assert len(usages) == 1
    assert usages[0].kwargs["prompt_tokens"] == 500
    assert usages[0].kwargs["total_tokens"] == 500
    assert usages[0].kwargs["currency"] == "USD"
    assert usages[0].kwargs["amount"] == Decimal("0.008")
    assert usages[0].kwargs["billed_quantity"] == 4
    snapshot = usages[0].kwargs["pricing_snapshot_json"]
    assert snapshot["billing_basis"] == "searches"
    assert snapshot["billing_unit"] == "1k_searches"
    assert snapshot["unit_size"] == 1000
    assert snapshot["quantities"] == {"searches": 4, "total_tokens": 500}


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

    def resolve_provider(_request_ctx, slug, model_id):
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
            provider_model_id="model-1",
            model_id=model_id,
            model_status="active",
            capability_matrix={"chat": {"merged": True}},
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
