""" memory

In-memory LLM adapter for tests and local runs.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, AsyncIterator

from app.kernel.ports.llm.interface import (
    LLMPort,
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    RerankResponse,
)


class InMemoryLLMPort(LLMPort):
    """In-memory LLM implementation with deterministic responses."""

    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        last_user = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_user = msg.content or ""
                break

        text = last_user or "ok"
        prompt_tokens = len(" ".join([m.content for m in messages]).split())
        completion_tokens = len(text.split()) if text else 0
        model_name = model.split(":")[-1] if ":" in model else model
        return ChatResponse(
            text=text,
            tokens_prompt=prompt_tokens,
            tokens_completion=completion_tokens,
            model=model_name,
            finish_reason="stop",
        )

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatStreamChunk]:
        response = await self.chat(messages, model, temperature, max_tokens, **kwargs)
        yield ChatStreamChunk(
            delta=response.text,
            done=True,
            tokens_prompt=response.tokens_prompt,
            tokens_completion=response.tokens_completion,
            model=response.model,
            finish_reason=response.finish_reason,
        )

    async def embed(
        self,
        texts: List[str],
        model: str,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        embeddings = [[0.0, 0.0, 0.0] for _ in texts]
        tokens_used = len(" ".join(texts).split())
        model_name = model.split(":")[-1] if ":" in model else model
        return EmbeddingResponse(
            embeddings=embeddings,
            tokens_used=tokens_used,
            model=model_name,
        )

    async def rerank(
        self,
        query: str,
        documents: List[str],
        model: str,
        top_n: Optional[int] = None,
        **kwargs: Any,
    ) -> RerankResponse:
        results = []
        for idx, doc in enumerate(documents):
            results.append({"index": idx, "document": doc, "score": 1.0})

        if top_n is not None and top_n > 0:
            results = results[:top_n]

        model_name = model.split(":")[-1] if ":" in model else model
        tokens_used = len(query.split()) + len(" ".join(documents).split())
        return RerankResponse(results=results, tokens_used=tokens_used, model=model_name)
