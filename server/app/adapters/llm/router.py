"""router

LLM provider router adapter.
"""

from collections.abc import AsyncIterator
from typing import Any

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
)
from app.settings.settings import settings


class LLMRouterPort(LLMPort):
    """Route LLM calls to provider-specific ports."""

    def __init__(self, providers: dict[str, LLMPort]):
        """Initialize router with provider mapping."""
        self.providers = providers

    def _resolve_provider(self, model: str) -> str:
        """Resolve provider name from model reference."""
        if model.startswith("model:"):
            parts = model.split(":")
            if len(parts) >= 3 and parts[1]:
                return parts[1]
        elif ":" in model:
            prefix = model.split(":", 1)[0]
            if prefix in self.providers:
                return prefix
        return settings.default_llm_provider

    def _get_provider_port(self, model: str) -> LLMPort:
        """Get provider port for a model reference."""
        provider = self._resolve_provider(model)
        port = self.providers.get(provider)
        if not port:
            raise ValidationError(f"Unsupported LLM provider: {provider}")
        return port

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Route chat completion."""
        port = self._get_provider_port(model)
        return await port.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatStreamChunk]:
        """Route streaming chat completion."""
        import inspect
        port = self._get_provider_port(model)
        if not hasattr(port, "stream_chat"):
            raise ValidationError(f"Streaming not supported for provider: {self._resolve_provider(model)}")
        stream = port.stream_chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        if inspect.isawaitable(stream):
            stream = await stream
        async for chunk in stream:
            yield chunk

    async def embed(
        self,
        texts: list[str],
        model: str,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Route embedding request."""
        port = self._get_provider_port(model)
        return await port.embed(texts=texts, model=model, **kwargs)

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        """Route rerank request."""
        port = self._get_provider_port(model)
        return await port.rerank(
            query=query,
            documents=documents,
            model=model,
            top_n=top_n,
            **kwargs,
        )
