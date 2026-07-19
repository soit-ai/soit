"""Anthropic LLM port adapter implementation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
    ToolDefinition,
)

ANTHROPIC_API_VERSION = "2023-06-01"
ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com"


class AnthropicLLMPort(LLMPort):
    """Anthropic Messages API adapter."""

    def __init__(self, api_key: str, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = (base_url or ANTHROPIC_DEFAULT_BASE_URL).rstrip("/")

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        if tools or tool_choice:
            raise ValidationError("Anthropic tool calling is not supported by this adapter")
        payload = self._build_messages_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            **kwargs,
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        usage = body.get("usage") or {}
        return ChatResponse(
            text=self._extract_text(body),
            reasoning=self._extract_reasoning(body),
            tokens_prompt=int(usage.get("input_tokens") or 0),
            tokens_completion=int(usage.get("output_tokens") or 0),
            model=body.get("model") or self._resolve_model_name(model),
            finish_reason=body.get("stop_reason"),
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatStreamChunk]:
        payload = self._build_messages_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )
        finish_reason: str | None = None
        tokens_completion = 0
        model_name = self._resolve_model_name(model)
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if not data or data == "[DONE]":
                        continue
                    event = json.loads(data)
                    event_type = event.get("type")
                    if event_type == "message_start":
                        message = event.get("message") or {}
                        model_name = message.get("model") or model_name
                        usage = message.get("usage") or {}
                        tokens_completion = int(usage.get("output_tokens") or tokens_completion)
                    elif event_type == "content_block_delta":
                        delta = event.get("delta") or {}
                        reasoning = delta.get("thinking") or ""
                        if delta.get("type") == "thinking_delta" and reasoning:
                            yield ChatStreamChunk(
                                reasoning_delta=str(reasoning),
                                model=model_name,
                            )
                        text = delta.get("text") or ""
                        if text:
                            yield ChatStreamChunk(delta=text, model=model_name)
                    elif event_type == "message_delta":
                        delta = event.get("delta") or {}
                        finish_reason = delta.get("stop_reason") or finish_reason
                        usage = event.get("usage") or {}
                        tokens_completion = int(usage.get("output_tokens") or tokens_completion)
                    elif event_type == "message_stop":
                        yield ChatStreamChunk(
                            delta="",
                            done=True,
                            tokens_completion=tokens_completion,
                            model=model_name,
                            finish_reason=finish_reason,
                        )

    async def embed(
        self,
        texts: list[str],
        model: str,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        raise ValidationError("Embeddings are not supported for Anthropic providers")

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        raise ValidationError("Rerank is not supported for Anthropic providers")

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }

    def _build_messages_payload(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
        **kwargs: Any,
    ) -> dict[str, Any]:
        system_messages: list[str] = []
        anthropic_messages: list[dict[str, str]] = []
        for message in messages:
            if message.role == "system":
                if message.content:
                    system_messages.append(message.content)
                continue
            if message.role not in {"user", "assistant"}:
                raise ValidationError(f"Anthropic chat does not support message role: {message.role}")
            if message.tool_calls:
                raise ValidationError("Anthropic tool calling is not supported by this adapter")
            anthropic_messages.append({"role": message.role, "content": message.content or ""})

        payload: dict[str, Any] = {
            "model": self._resolve_model_name(model),
            "messages": anthropic_messages,
            "max_tokens": max_tokens or 1024,
        }
        if system_messages:
            payload["system"] = "\n\n".join(system_messages)
        if temperature is not None:
            payload["temperature"] = temperature
        if stream:
            payload["stream"] = True
        top_p = kwargs.get("top_p")
        if top_p is not None:
            payload["top_p"] = top_p
        return payload

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        parts: list[str] = []
        for item in payload.get("content", []) or []:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_reasoning(payload: dict[str, Any]) -> str | None:
        parts: list[str] = []
        for item in payload.get("content", []) or []:
            if (
                isinstance(item, dict)
                and item.get("type") == "thinking"
                and item.get("thinking")
            ):
                parts.append(str(item["thinking"]))
        reasoning = "\n".join(parts).strip()
        return reasoning or None

    @staticmethod
    def _resolve_model_name(model: str) -> str:
        if model.startswith("model:"):
            parts = model.split(":")
            if len(parts) >= 3:
                return ":".join(parts[2:])
        if model.startswith("anthropic:"):
            return model.split(":", 1)[1]
        return model
