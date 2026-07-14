""" memory

In-memory LLM adapter for tests and local runs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

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


class InMemoryLLMPort(LLMPort):
    """In-memory LLM implementation with deterministic responses."""

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
        model_name = model.split(":")[-1] if ":" in model else model
        prompt_tokens = sum(len((m.content or "").split()) for m in messages)
        last_user = ""
        last_tool = ""
        for msg in reversed(messages):
            if not last_tool and msg.role == "tool":
                last_tool = msg.content or ""
            if msg.role == "user":
                last_user = msg.content or ""
                break

        if last_tool:
            completion_tokens = len(last_tool.split())
            return ChatResponse(
                text=last_tool,
                tokens_prompt=prompt_tokens,
                tokens_completion=completion_tokens,
                model=model_name,
                finish_reason="stop",
            )

        # When tools are provided, mock a tool call for the first tool
        if tools:
            tool = tools[0]
            return ChatResponse(
                text=None,
                tool_calls=[
                    ToolCall(
                        id=f"call_{tool.name}",
                        name=tool.name,
                        arguments=self._mock_tool_arguments(tool.parameters, last_user),
                    )
                ],
                tokens_prompt=prompt_tokens,
                tokens_completion=1,
                model=model_name,
                finish_reason="tool_calls",
            )

        text = last_user or "ok"
        completion_tokens = len(text.split()) if text else 0
        return ChatResponse(
            text=text,
            tokens_prompt=prompt_tokens,
            tokens_completion=completion_tokens,
            model=model_name,
            finish_reason="stop",
        )

    def _mock_tool_arguments(self, parameters: dict[str, Any], last_user: str) -> dict[str, Any]:
        required = parameters.get("required") or []
        properties = parameters.get("properties") or {}
        arguments: dict[str, Any] = {}
        for name in required:
            schema = properties.get(name) or {}
            arguments[name] = self._mock_argument_value(name, schema, last_user)
        return arguments

    def _mock_argument_value(self, name: str, schema: dict[str, Any], last_user: str) -> Any:
        value_type = schema.get("type")
        lowered = name.lower()
        if value_type == "string":
            if any(token in lowered for token in ("message", "query", "prompt", "text", "description")):
                return last_user or "demo request"
            if "priority" in lowered:
                return "normal"
            if lowered.endswith("_id") or lowered == "id" or "customer" in lowered:
                return "demo-customer"
            return f"demo-{lowered.replace('_', '-')}"
        if value_type in ("integer", "number"):
            return 1
        if value_type == "boolean":
            return True
        if value_type == "array":
            return []
        if value_type == "object":
            return {}
        return last_user or "demo"

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatStreamChunk]:
        # Strip tools/tool_choice from kwargs before passing to chat
        tools = kwargs.pop("tools", None)
        tool_choice = kwargs.pop("tool_choice", None)
        response = await self.chat(
            messages, model, temperature, max_tokens,
            tools=tools, tool_choice=tool_choice, **kwargs,
        )
        yield ChatStreamChunk(
            delta=response.text or "",
            done=True,
            tokens_prompt=response.tokens_prompt,
            tokens_completion=response.tokens_completion,
            model=response.model,
            finish_reason=response.finish_reason,
        )

    async def embed(
        self,
        texts: list[str],
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
        documents: list[str],
        model: str,
        top_n: int | None = None,
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
