"""LLM provider router with additive workspace LiteLLM selection."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    LLMPort,
    LLMRuntimeTarget,
    RerankResponse,
)
from app.kernel.ports.secrets.interface import SecretsPort
from app.settings.settings import settings


@dataclass(frozen=True)
class RuntimeProviderConfig:
    """Runtime-safe subset of a workspace provider configuration."""

    slug: str
    kind: str
    adapter_backend: str
    status: str
    base_url: str | None = None
    credential_ref: str | None = None
    timeout: float = 60.0
    max_retries: int = 3
    provider_id: str | None = None
    retry_backoff: str = "exponential"
    retryable_status_codes: tuple[int, ...] = (408, 409, 429, 500, 502, 503, 504)
    litellm_provider: str | None = None
    litellm_params: dict[str, Any] = field(default_factory=dict)
    secret_bindings: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedLLMRoute:
    """Provider port and canonical SOIT runtime identity."""

    port: LLMPort
    target: LLMRuntimeTarget
    timeout_seconds: float | None = None
    max_retries: int | None = None
    retry_backoff: str = "exponential"
    retryable_status_codes: tuple[int, ...] = (408, 409, 429, 500, 502, 503, 504)


ProviderResolver = Callable[
    [RequestContext, str],
    RuntimeProviderConfig | None | Awaitable[RuntimeProviderConfig | None],
]
SecretsResolver = Callable[[RequestContext], SecretsPort]
LiteLLMFactory = Callable[[RuntimeProviderConfig, dict[str, str]], LLMPort]


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
    ) -> None:
        self.providers = providers
        self.provider_resolver = provider_resolver
        self.secrets_resolver = secrets_resolver
        self.litellm_factory = litellm_factory or _default_litellm_factory

    @staticmethod
    def _model_provider_key(model: str) -> str | None:
        if model.startswith("model:"):
            parts = model.split(":", 2)
            if len(parts) == 3 and parts[1]:
                return parts[1]
        return None

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
        )

    async def resolve_route(
        self,
        model: str,
        ctx: RequestContext | None,
    ) -> ResolvedLLMRoute:
        provider_key = self._model_provider_key(model)
        if ctx is not None and provider_key and self.provider_resolver is not None:
            config = self.provider_resolver(ctx, provider_key)
            if inspect.isawaitable(config):
                config = await config
            if config is not None:
                if config.status != "active":
                    raise ValidationError(
                        f"Workspace provider is {config.status}: {config.slug}"
                    )
                if config.adapter_backend == "native":
                    port = self.providers.get(config.kind)
                    if port is None:
                        raise ValidationError(
                            f"Native LLM provider is not configured: {config.kind}"
                        )
                    return ResolvedLLMRoute(
                        port=port,
                        target=self._runtime_target(
                            model,
                            provider_id=config.provider_id,
                            provider_slug=config.slug,
                            provider_kind=config.kind,
                            adapter_backend=config.adapter_backend,
                        ),
                        timeout_seconds=config.timeout,
                        max_retries=config.max_retries,
                        retry_backoff=config.retry_backoff,
                        retryable_status_codes=config.retryable_status_codes,
                    )
                if config.adapter_backend == "litellm":
                    secret_bindings = dict(config.secret_bindings)
                    if config.credential_ref and "api_key" not in secret_bindings:
                        secret_bindings["api_key"] = config.credential_ref
                    credentials: dict[str, str] = {}
                    if secret_bindings:
                        if self.secrets_resolver is None:
                            raise ValidationError("LiteLLM provider requires a secrets resolver")
                        secrets = self.secrets_resolver(ctx)
                        for parameter, secret_ref in secret_bindings.items():
                            credentials[parameter] = await secrets.get_secret(
                                secret_ref=secret_ref
                            )
                    return ResolvedLLMRoute(
                        port=self.litellm_factory(config, credentials),
                        target=self._runtime_target(
                            model,
                            provider_id=config.provider_id,
                            provider_slug=config.slug,
                            provider_kind=config.kind,
                            adapter_backend=config.adapter_backend,
                        ),
                        timeout_seconds=config.timeout,
                        max_retries=config.max_retries,
                        retry_backoff=config.retry_backoff,
                        retryable_status_codes=config.retryable_status_codes,
                    )
                raise ValidationError(
                    f"Unsupported LLM adapter backend: {config.adapter_backend}"
                )

        static_key = self._static_provider_key(model)
        port = self.providers.get(static_key)
        if port is None:
            raise ValidationError(f"Unsupported LLM provider: {static_key}")
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
        route = await self.resolve_route(model, kwargs.get("ctx"))
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
        route = await self.resolve_route(model, kwargs.get("ctx"))
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
        route = await self.resolve_route(model, kwargs.get("ctx"))
        response = await route.port.embed(
            texts=texts,
            model=model,
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
        route = await self.resolve_route(model, kwargs.get("ctx"))
        response = await route.port.rerank(
            query=query,
            documents=documents,
            model=model,
            top_n=top_n,
            **self._downstream_kwargs(kwargs),
        )
        response.runtime_target = route.target
        return response
