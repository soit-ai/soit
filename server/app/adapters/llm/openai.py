""" openai_llm

OpenAI LLM port adapter implementation.
"""

import json as _json
from typing import Any

import numpy as np
from openai import AsyncOpenAI

from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
    ToolCall,
    ToolDefinition,
)


class OpenAILLMPort(LLMPort):
    """OpenAI LLM port adapter."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """Initialize OpenAI gateway.

        Args:
            api_key: OpenAI API key (if None, uses settings or env var).
            base_url: Optional OpenAI-compatible API base URL.
        """
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @staticmethod
    def _convert_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        """Convert ChatMessage list to OpenAI message format."""
        openai_messages = []
        for msg in messages:
            m: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.role == "assistant" and msg.tool_calls:
                m["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": _json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            if msg.role == "tool" and msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.name:
                m["name"] = msg.name
            openai_messages.append(m)
        return openai_messages

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> ChatResponse:
        """Chat completion via OpenAI."""
        model_name = self._resolve_model_name(model)
        openai_messages = self._convert_messages(messages)

        params: dict[str, Any] = {
            "model": model_name,
            "messages": openai_messages,
        }
        resolved_temperature = self._resolve_temperature_param(model_name, temperature)
        if resolved_temperature is not None:
            params["temperature"] = resolved_temperature
        if max_tokens is not None:
            params[self._token_limit_param(model_name)] = max_tokens

        # Function calling parameters
        if tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": td.name,
                        "description": td.description,
                        "parameters": td.parameters,
                    },
                }
                for td in tools
            ]
        if tool_choice is not None:
            params["tool_choice"] = tool_choice

        reasoning_effort = kwargs.get("reasoning_effort")
        if reasoning_effort and self._supports_reasoning_effort(model_name):
            params["reasoning_effort"] = reasoning_effort
        top_p = kwargs.get("top_p")
        if top_p is not None:
            params["top_p"] = top_p

        response = await self.client.chat.completions.create(**params)

        choice = response.choices[0]

        # Parse tool_calls from response
        parsed_tool_calls = None
        if choice.message.tool_calls:
            parsed_tool_calls = []
            for tc in choice.message.tool_calls:
                try:
                    arguments = _json.loads(tc.function.arguments)
                except (ValueError, TypeError):
                    arguments = {}
                parsed_tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, arguments=arguments)
                )

        return ChatResponse(
            text=choice.message.content if not parsed_tool_calls else None,
            tokens_prompt=response.usage.prompt_tokens if response.usage else 0,
            tokens_completion=response.usage.completion_tokens if response.usage else 0,
            model=model_name,
            finish_reason=choice.finish_reason,
            tool_calls=parsed_tool_calls,
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ):
        """Stream chat completion via OpenAI."""
        model_name = self._resolve_model_name(model)
        openai_messages = self._convert_messages(messages)

        params: dict[str, Any] = {
            "model": model_name,
            "messages": openai_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        resolved_temperature = self._resolve_temperature_param(model_name, temperature)
        if resolved_temperature is not None:
            params["temperature"] = resolved_temperature
        if max_tokens is not None:
            params[self._token_limit_param(model_name)] = max_tokens
        reasoning_effort = kwargs.get("reasoning_effort")
        if reasoning_effort and self._supports_reasoning_effort(model_name):
            params["reasoning_effort"] = reasoning_effort
        top_p = kwargs.get("top_p")
        if top_p is not None:
            params["top_p"] = top_p

        # Compat: older OpenAI SDK (e.g. 1.6.x) does not accept stream_options.
        try:
            stream = await self.client.chat.completions.create(**params)
        except TypeError as exc:
            if "stream_options" not in str(exc):
                raise
            params.pop("stream_options", None)
            stream = await self.client.chat.completions.create(**params)
        async for event in stream:
            if not event.choices:
                usage = getattr(event, "usage", None)
                if usage:
                    yield ChatStreamChunk(
                        delta="",
                        done=True,
                        tokens_prompt=usage.prompt_tokens or 0,
                        tokens_completion=usage.completion_tokens or 0,
                        model=model_name,
                        finish_reason=None,
                    )
                continue

            choice = event.choices[0]
            delta = ""
            if choice.delta and choice.delta.content:
                delta = choice.delta.content

            done = choice.finish_reason is not None
            usage = getattr(event, "usage", None)
            tokens_prompt = usage.prompt_tokens if usage else 0
            tokens_completion = usage.completion_tokens if usage else 0

            yield ChatStreamChunk(
                delta=delta,
                done=done,
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
                model=model_name,
                finish_reason=choice.finish_reason,
            )

    async def embed(
        self,
        texts: list[str],
        model: str,
        **kwargs,
    ) -> EmbeddingResponse:
        """Generate embeddings via OpenAI."""
        model_name = self._resolve_model_name(model)

        # Call OpenAI API
        response = await self.client.embeddings.create(
            model=model_name,
            input=texts,
        )

        embeddings = [item.embedding for item in response.data]
        tokens_used = response.usage.total_tokens if response.usage else 0

        return EmbeddingResponse(
            embeddings=embeddings,
            tokens_used=tokens_used,
            model=model_name,
        )

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
        **kwargs,
    ) -> RerankResponse:
        """Rerank documents via OpenAI using embeddings + cosine similarity.

        Args:
            query: Query text.
            documents: List of document texts to rerank.
            model: Model reference (embedding model).
            top_n: Number of top results to return.
            **kwargs: Additional parameters.

        Returns:
            RerankResponse with reranked results.
        """
        if not documents:
            return RerankResponse(
                results=[],
                tokens_used=0,
                model=model,
            )

        model_name = self._resolve_model_name(model)

        # Use embedding model (default to text-embedding-ada-002 if not specified)
        embedding_model = self._resolve_model_name(kwargs.get("embedding_model", "text-embedding-ada-002"))

        # Generate embeddings for query and documents
        all_texts = [query] + documents
        response = await self.client.embeddings.create(
            model=embedding_model,
            input=all_texts,
        )

        embeddings = [item.embedding for item in response.data]
        tokens_used = response.usage.total_tokens if response.usage else 0

        # Extract query embedding and document embeddings
        query_embedding = np.array(embeddings[0])
        doc_embeddings = np.array(embeddings[1:])

        # Calculate cosine similarity
        # Cosine similarity = dot product / (norm(query) * norm(doc))
        query_norm = np.linalg.norm(query_embedding)
        doc_norms = np.linalg.norm(doc_embeddings, axis=1)

        # Avoid division by zero
        query_norm = max(query_norm, 1e-8)
        doc_norms = np.maximum(doc_norms, 1e-8)

        # Calculate cosine similarities
        similarities = np.dot(doc_embeddings, query_embedding) / (query_norm * doc_norms)

        # Create results with scores
        results = []
        for i, (doc, score) in enumerate(zip(documents, similarities, strict=False)):
            results.append({
                "index": i,
                "document": doc,
                "score": float(score),
            })

        # Sort by score (descending)
        results.sort(key=lambda x: x["score"], reverse=True)

        # Apply top_n if specified
        if top_n is not None and top_n > 0:
            results = results[:top_n]

        return RerankResponse(
            results=results,
            tokens_used=tokens_used,
            model=model_name,
        )

    @staticmethod
    def _token_limit_param(model_name: str) -> str:
        """Map token-limit param based on model family."""
        normalized = model_name.lower()
        if normalized.startswith(("gpt-5", "o1", "o3", "o4")):
            return "max_completion_tokens"
        return "max_tokens"

    @staticmethod
    def _resolve_model_name(model: str) -> str:
        """Resolve provider-qualified model refs to provider-native model ids."""
        if model.startswith("model:"):
            parts = model.split(":")
            if len(parts) >= 3:
                return ":".join(parts[2:])
        if model.startswith("openai:"):
            return model.split(":", 1)[1]
        return model

    @staticmethod
    def _supports_reasoning_effort(model_name: str) -> bool:
        """Whether model supports reasoning_effort param."""
        normalized = model_name.lower()
        return normalized.startswith(("gpt-5", "o1", "o3", "o4"))

    @staticmethod
    def _resolve_temperature_param(
        model_name: str,
        temperature: float | None,
    ) -> float | None:
        """Normalize temperature by model capabilities."""
        if temperature is None:
            return None
        normalized = model_name.lower()
        # Some reasoning-focused models only accept the default temperature.
        if normalized.startswith(("gpt-5", "o1", "o3", "o4")):
            return 1.0 if abs(temperature - 1.0) < 1e-9 else None
        return temperature
