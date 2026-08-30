"""LLM provider router with additive workspace LiteLLM selection."""

from __future__ import annotations

import inspect
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    ImageGenerationResponse,
    LLMPort,
    LLMRuntimeTarget,
    RerankResponse,
)
from app.kernel.ports.llm.runtime_config import PROVIDER_CAPABILITY_PRESETS
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.security.egress import GovernedEgressGuard
from app.settings.settings import settings

_PROVIDER_EGRESS_BASE_URLS = {
    "anthropic": "https://api.anthropic.com",
    "dashscope": "https://dashscope.aliyuncs.com",
    "deepseek": "https://api.deepseek.com",
    "gemini": "https://generativelanguage.googleapis.com",
    "openai": "https://api.openai.com/v1",
    "openai_compatible": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


@dataclass(frozen=True)
class RuntimeProviderConfig:
    """Runtime-safe subset of a workspace provider configuration."""

    slug: str
    kind: str
    adapter_backend: str
    status: str
    base_url: str | None = None
    credential_secret_id: str | None = None
    timeout: float = 60.0
    max_retries: int = 3
    provider_id: str | None = None
    retry_backoff: str = "exponential"
    retryable_status_codes: tuple[int, ...] = (408, 409, 429, 500, 502, 503, 504)
    litellm_provider: str | None = None
    litellm_params: dict[str, Any] = field(default_factory=dict)
    secret_bindings: dict[str, str] = field(default_factory=dict)
    provider_model_id: str | None = None
    model_id: str | None = None
    model_status: str = "active"
    model_sync_status: str | None = None
    capability_matrix: dict[str, Any] = field(default_factory=dict)
    provider_capabilities: dict[str, Any] = field(default_factory=dict)
    pricing: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedLLMRoute:
    """Provider port and canonical SOIT runtime identity."""

    port: LLMPort
    target: LLMRuntimeTarget
    timeout_seconds: float | None = None
    max_retries: int | None = None
    retry_backoff: str = "exponential"
    retryable_status_codes: tuple[int, ...] = (408, 409, 429, 500, 502, 503, 504)
    pricing: dict[str, Any] = field(default_factory=dict)


ProviderResolver = Callable[
    [RequestContext, str, str],
    RuntimeProviderConfig | None | Awaitable[RuntimeProviderConfig | None],
]
SecretsResolver = Callable[[RequestContext], SecretsPort]
LiteLLMFactory = Callable[[RuntimeProviderConfig, dict[str, str]], LLMPort]
NativeLLMFactory = Callable[[RuntimeProviderConfig, dict[str, str]], LLMPort]


def _default_native_factory(
    config: RuntimeProviderConfig,
    credentials: dict[str, str],
) -> LLMPort:
    api_key = credentials.get("api_key")
    if config.kind in {"openai", "openai_compatible"}:
        from app.adapters.llm.openai import OpenAILLMPort

        return OpenAILLMPort(
            api_key=api_key,
            base_url=config.base_url,
            use_responses_api=config.kind == "openai",
        )
    if config.kind == "deepseek":
        from app.adapters.llm.deepseek import DeepSeekLLMPort

        return DeepSeekLLMPort(api_key=api_key, base_url=config.base_url)
    if config.kind == "anthropic":
        from app.adapters.llm.anthropic import AnthropicLLMPort

        if not api_key:
            raise KernelError(
                "MODEL_PROVIDER_CREDENTIAL_REQUIRED",
                f"Provider credential is required: {config.slug}",
            )
        return AnthropicLLMPort(api_key=api_key, base_url=config.base_url)
    raise KernelError(
        "MODEL_ADAPTER_UNSUPPORTED",
        f"Native LLM adapter is unsupported: {config.kind}",
    )


def _default_litellm_factory(
    config: RuntimeProviderConfig,
    credentials: dict[str, str],
) -> LLMPort:
    from app.adapters.llm.litellm import LiteLLMPort

    extra_credentials = {
        key: value for key, value in credentials.items() if key != "api_key"
    }
    return LiteLLMPort(
        provider_kind=config.kind,
        litellm_provider=config.litellm_provider,
        litellm_params={**config.litellm_params, **extra_credentials},
        api_key=credentials.get("api_key"),
        api_base=config.base_url,
        timeout=config.timeout,
        max_retries=config.max_retries,
    )


class LLMRouterPort(LLMPort):
    """Route to existing native ports or an explicitly configured LiteLLM adapter."""

    def __init__(
        self,
        providers: dict[str, LLMPort],
        *,
        provider_resolver: ProviderResolver | None = None,
        secrets_resolver: SecretsResolver | None = None,
        litellm_factory: LiteLLMFactory | None = None,
        native_factory: NativeLLMFactory | None = None,
        egress_guard: GovernedEgressGuard | None = None,
        unrouted_provider_keys: Iterable[str] = (),
    ) -> None:
        self.providers = providers
        self.provider_resolver = provider_resolver
        self.secrets_resolver = secrets_resolver
        # Provider keys that are allowed to answer without a workspace route.
        # Only deterministic in-process adapters belong here: a workspace can
        # never own a route to one, so requiring it would make the adapter
        # unreachable. Production registers none, so routing stays
        # authoritative for every provider that leaves the process.
        self.unrouted_provider_keys = frozenset(unrouted_provider_keys)
        self.litellm_factory = litellm_factory or _default_litellm_factory
        self.native_factory = native_factory or _default_native_factory
        self.egress_guard = egress_guard or GovernedEgressGuard()

    async def _authorize_provider_target(
        self,
        ctx: RequestContext,
        *,
        provider_slug: str,
        provider_kind: str,
        base_url: str | None,
        provider_params: dict[str, Any] | None = None,
    ) -> None:
        url = base_url or _PROVIDER_EGRESS_BASE_URLS.get(provider_kind)
        if not url and provider_kind == "bedrock":
            params = provider_params or {}
            region = str(
                params.get("aws_region_name")
                or params.get("region_name")
                or "us-east-1"
            )
            if not re.fullmatch(r"[a-z0-9-]+", region):
                raise ValidationError("Invalid Bedrock region for governed egress")
            url = f"https://bedrock-runtime.{region}.amazonaws.com"
        if not url:
            raise KernelError(
                "MODEL_PROVIDER_EGRESS_TARGET_REQUIRED",
                f"Provider requires an explicit governed base URL: {provider_slug}",
            )
        await self.egress_guard.authorize(
            ctx,
            f"model-provider:{provider_slug}",
            url,
        )

    def _may_bypass_routing(self, provider_key: str) -> bool:
        """Return whether this provider may answer without a workspace route."""
        return (
            provider_key in self.unrouted_provider_keys
            and provider_key in self.providers
        )

    @staticmethod
    def _model_provider_key(model: str) -> str | None:
        if model.startswith("model:"):
            parts = model.split(":", 2)
            if len(parts) == 3 and parts[1]:
                return parts[1]
        return None

    @staticmethod
    def _model_id(model: str) -> str:
        if model.startswith("model:"):
            parts = model.split(":", 2)
            if len(parts) == 3 and parts[2]:
                return parts[2]
        return model

    def _static_provider_key(self, model: str) -> str:
        model_provider = self._model_provider_key(model)
        if model_provider:
            return model_provider
        if ":" in model:
            prefix = model.split(":", 1)[0]
            if prefix in self.providers:
                return prefix
        return settings.default_llm_provider

    @staticmethod
    def _runtime_target(
        model: str,
        *,
        provider_id: str | None,
        provider_slug: str,
        provider_kind: str,
        adapter_backend: str,
        provider_model_id: str | None = None,
    ) -> LLMRuntimeTarget:
        model_id = model
        if model.startswith("model:"):
            parts = model.split(":", 2)
            if len(parts) == 3:
                model_id = parts[2]
        elif model.startswith(f"{provider_kind}:"):
            model_id = model.split(":", 1)[1]
        return LLMRuntimeTarget(
            provider_id=provider_id,
            provider_slug=provider_slug,
            provider_kind=provider_kind,
            adapter_backend=adapter_backend,
            model_ref=f"model:{provider_slug}:{model_id}",
            model_id=model_id,
            provider_model_id=provider_model_id,
        )

    @staticmethod
    def _capability_value(config: RuntimeProviderConfig, capability: str) -> bool:
        aliases = {
            "embedding": "embeddings",
            "embed": "embeddings",
        }
        normalized = aliases.get(capability, capability)
        entry = config.capability_matrix.get(normalized)
        if entry is None and normalized == "embeddings":
            entry = config.capability_matrix.get("embedding")
        if isinstance(entry, dict) and isinstance(entry.get("merged"), bool):
            return entry["merged"]

        provider_value = config.provider_capabilities.get(normalized)
        if provider_value is None and normalized == "embeddings":
            provider_value = config.provider_capabilities.get("embedding")
        if isinstance(provider_value, bool):
            return provider_value
        return PROVIDER_CAPABILITY_PRESETS.get(config.kind, {}).get(normalized, False)

    @classmethod
    def _validate_runtime_config(
        cls,
        config: RuntimeProviderConfig,
        required_capabilities: tuple[str, ...],
    ) -> None:
        if config.status != "active":
            raise KernelError(
                "MODEL_PROVIDER_DISABLED",
                f"Workspace provider is {config.status}: {config.slug}",
            )
        if config.model_status != "active" or config.model_sync_status in {
            "platform_removed",
            "user_removed",
        }:
            raise KernelError(
                "MODEL_RUNTIME_DISABLED",
                f"Workspace model is {config.model_status}: {config.model_id}",
            )
        for capability in required_capabilities:
            if not cls._capability_value(config, capability):
                raise KernelError(
                    "MODEL_CAPABILITY_UNAVAILABLE",
                    f"Model capability is unavailable: {capability}",
                    {
                        "provider_slug": config.slug,
                        "model_id": config.model_id,
                        "capability": capability,
                    },
                )

    async def _resolve_credentials(
        self,
        ctx: RequestContext,
        config: RuntimeProviderConfig,
    ) -> dict[str, str]:
        secret_bindings = dict(config.secret_bindings)
        if config.credential_secret_id and "api_key" not in secret_bindings:
            secret_bindings["api_key"] = config.credential_secret_id
        if not secret_bindings:
            if settings.environment == "production" and config.kind not in {
                "bedrock",
                "ollama",
            }:
                raise KernelError(
                    "MODEL_PROVIDER_CREDENTIAL_REQUIRED",
                    f"Provider credential is required: {config.slug}",
                )
            return {}
        if self.secrets_resolver is None:
            raise KernelError(
                "MODEL_PROVIDER_SECRETS_UNAVAILABLE",
                f"Provider requires a secrets resolver: {config.slug}",
            )
        secrets = self.secrets_resolver(ctx)
        credentials: dict[str, str] = {}
        for parameter, secret_id in secret_bindings.items():
            credentials[parameter] = await secrets.get_secret(secret_id=secret_id)
        return credentials

    async def resolve_route(
        self,
        model: str,
        ctx: RequestContext | None,
        required_capabilities: tuple[str, ...] = (),
    ) -> ResolvedLLMRoute:
        if (
            ctx is not None
            and self.provider_resolver is not None
            and settings.environment == "production"
            and not model.startswith("model:")
        ):
            raise KernelError(
                "MODEL_REF_INVALID",
                "Production LLM calls require a canonical model:{provider}:{model_id} reference",
                {"model": model},
            )
        provider_key = self._model_provider_key(model)
        if ctx is not None and provider_key and self.provider_resolver is not None:
            model_id = self._model_id(model)
            config = self.provider_resolver(ctx, provider_key, model_id)
            if inspect.isawaitable(config):
                config = await config
            if config is None and not self._may_bypass_routing(provider_key):
                raise KernelError(
                    "MODEL_RUNTIME_NOT_FOUND",
                    f"Active workspace model route was not found: {model}",
                )
            if config is not None:
                self._validate_runtime_config(config, required_capabilities)
                await self._authorize_provider_target(
                    ctx,
                    provider_slug=config.slug,
                    provider_kind=config.kind,
                    base_url=config.base_url,
                    provider_params=config.litellm_params,
                )
                if config.adapter_backend == "native":
                    credentials = await self._resolve_credentials(ctx, config)
                    port = self.native_factory(config, credentials)
                    return ResolvedLLMRoute(
                        port=port,
                        target=self._runtime_target(
                            model,
                            provider_id=config.provider_id,
                            provider_slug=config.slug,
                            provider_kind=config.kind,
                            adapter_backend=config.adapter_backend,
                            provider_model_id=config.provider_model_id,
                        ),
                        timeout_seconds=config.timeout,
                        max_retries=config.max_retries,
                        retry_backoff=config.retry_backoff,
                        retryable_status_codes=config.retryable_status_codes,
                        pricing=config.pricing,
                    )
                if config.adapter_backend == "litellm":
                    credentials = await self._resolve_credentials(ctx, config)
                    return ResolvedLLMRoute(
                        port=self.litellm_factory(config, credentials),
                        target=self._runtime_target(
                            model,
                            provider_id=config.provider_id,
                            provider_slug=config.slug,
                            provider_kind=config.kind,
                            adapter_backend=config.adapter_backend,
                            provider_model_id=config.provider_model_id,
                        ),
                        timeout_seconds=config.timeout,
                        max_retries=config.max_retries,
                        retry_backoff=config.retry_backoff,
                        retryable_status_codes=config.retryable_status_codes,
                        pricing=config.pricing,
                    )
                raise ValidationError(
                    f"Unsupported LLM adapter backend: {config.adapter_backend}"
                )

        static_key = self._static_provider_key(model)
        port = self.providers.get(static_key)
        if port is None:
            raise ValidationError(f"Unsupported LLM provider: {static_key}")
        egress_base_url = getattr(port, "egress_base_url", None)
        if ctx is not None and egress_base_url:
            await self._authorize_provider_target(
                ctx,
                provider_slug=static_key,
                provider_kind=static_key,
                base_url=str(egress_base_url),
            )
        return ResolvedLLMRoute(
            port=port,
            target=self._runtime_target(
                model,
                provider_id=None,
                provider_slug=static_key,
                provider_kind=static_key,
                adapter_backend="native",
            ),
        )

    @staticmethod
    def _downstream_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
        downstream = dict(kwargs)
        downstream.pop("ctx", None)
        return downstream

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        capabilities = ("chat", "tools") if kwargs.get("tools") else ("chat",)
        route = await self.resolve_route(model, kwargs.get("ctx"), capabilities)
        response = await route.port.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **self._downstream_kwargs(kwargs),
        )
        response.runtime_target = route.target
        return response

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatStreamChunk]:
        capabilities = ("chat", "tools") if kwargs.get("tools") else ("chat",)
        route = await self.resolve_route(model, kwargs.get("ctx"), capabilities)
        stream = route.port.stream_chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **self._downstream_kwargs(kwargs),
        )
        if inspect.isawaitable(stream):
            stream = await stream
        async for chunk in stream:
            chunk.runtime_target = route.target
            yield chunk

    async def embed(self, texts: list[str], model: str, **kwargs: Any) -> EmbeddingResponse:
        route = await self.resolve_route(model, kwargs.get("ctx"), ("embeddings",))
        response = await route.port.embed(
            texts=texts,
            model=model,
            **self._downstream_kwargs(kwargs),
        )
        response.runtime_target = route.target
        return response

    async def generate_image(
        self,
        prompt: str,
        model: str,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> ImageGenerationResponse:
        route = await self.resolve_route(model, kwargs.get("ctx"), ("image_generation",))
        response = await route.port.generate_image(
            prompt=prompt,
            model=model,
            n=n,
            size=size,
            **self._downstream_kwargs(kwargs),
        )
        response.runtime_target = route.target
        return response

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        route = await self.resolve_route(model, kwargs.get("ctx"), ("rerank",))
        response = await route.port.rerank(
            query=query,
            documents=documents,
            model=model,
            top_n=top_n,
            **self._downstream_kwargs(kwargs),
        )
        response.runtime_target = route.target
        return response
