"""Anthropic LLM port adapter implementation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.adapters.llm.content_parts import anthropic_image_block
from app.adapters.llm.tool_names import tool_name_alias, tool_name_maps
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
    ToolCall,
    ToolCallDelta,
    ToolDefinition,
)

ANTHROPIC_API_VERSION = "2023-06-01"
ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com"


def _prompt_tokens(usage: dict[str, Any]) -> int:
    """Every input token the call consumed.

    Anthropic reports prompt-cache writes and reads apart from
    ``input_tokens``; all three are input the call was charged for.
    """
    return sum(
        int(usage.get(key) or 0)
        for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )


def _tool_choice(tool_choice: Any, name_map: dict[str, str]) -> dict[str, Any] | None:
    """Translate an OpenAI-style ``tool_choice`` into Anthropic's shape."""

    if tool_choice is None:
        return None
    if isinstance(tool_choice, str):
        choice = tool_choice.strip().lower()
        if choice == "auto":
            return {"type": "auto"}
        if choice in {"required", "any"}:
            return {"type": "any"}
        if choice == "none":
            return {"type": "none"}
        # A bare tool name selects that tool.
        return {"type": "tool", "name": name_map.get(tool_choice, tool_name_alias(tool_choice))}
    if isinstance(tool_choice, dict):
        function = tool_choice.get("function") if isinstance(tool_choice.get("function"), dict) else {}
        name = function.get("name") or tool_choice.get("name")
        if name:
            return {"type": "tool", "name": name_map.get(str(name), tool_name_alias(str(name)))}
    raise ValidationError("Unsupported tool_choice for Anthropic")


def _text_blocks(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, list):
        return [dict(block) for block in content]
    if content:
        return [{"type": "text", "text": str(content)}]
    return []


class AnthropicLLMPort(LLMPort):
    """Anthropic Messages API adapter."""

    def __init__(self, api_key: str, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = (base_url or ANTHROPIC_DEFAULT_BASE_URL).rstrip("/")
        self.egress_base_url = self.base_url

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> ChatResponse:
        name_map, reverse_map = tool_name_maps(tools)
        payload = self._build_messages_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            tools=tools,
            tool_choice=tool_choice,
            name_map=name_map,
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
        tool_calls = self._extract_tool_calls(body, reverse_map)
        return ChatResponse(
            text=self._extract_text(body),
            reasoning=self._extract_reasoning(body),
            tokens_prompt=_prompt_tokens(usage),
            tokens_completion=int(usage.get("output_tokens") or 0),
            model=body.get("model") or self._resolve_model_name(model),
            finish_reason=body.get("stop_reason"),
            tool_calls=tool_calls or None,
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatStreamChunk]:
        name_map, reverse_map = tool_name_maps(tools)
        payload = self._build_messages_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            tools=tools,
            tool_choice=tool_choice,
            name_map=name_map,
            **kwargs,
        )
        finish_reason: str | None = None
        tokens_prompt = 0
        tokens_completion = 0
        model_name = self._resolve_model_name(model)
        # Content blocks are indexed across text and tool_use blocks; tool
        # calls are numbered in the order they start, as OpenAI numbers them.
        tool_positions: dict[int, int] = {}
        assembled: dict[int, dict[str, str]] = {}
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
                        tokens_prompt = _prompt_tokens(usage) or tokens_prompt
                        tokens_completion = int(usage.get("output_tokens") or tokens_completion)
                    elif event_type == "content_block_start":
                        block = event.get("content_block") or {}
                        if block.get("type") == "tool_use":
                            position = len(tool_positions)
                            tool_positions[int(event.get("index") or 0)] = position
                            alias = str(block.get("name") or "")
                            assembled[position] = {
                                "id": str(block.get("id") or ""),
                                "name": reverse_map.get(alias, alias),
                                "arguments": "",
                            }
                            yield ChatStreamChunk(
                                model=model_name,
                                tool_call_deltas=[
                                    ToolCallDelta(
                                        index=position,
                                        id=assembled[position]["id"],
                                        name=assembled[position]["name"],
                                        arguments_delta="",
                                    )
                                ],
                            )
                    elif event_type == "content_block_delta":
                        delta = event.get("delta") or {}
                        delta_type = delta.get("type")
                        if delta_type == "input_json_delta":
                            position = tool_positions.get(int(event.get("index") or 0))
                            fragment = str(delta.get("partial_json") or "")
                            if position is not None and fragment:
                                assembled[position]["arguments"] += fragment
                                yield ChatStreamChunk(
                                    model=model_name,
                                    tool_call_deltas=[
                                        ToolCallDelta(index=position, arguments_delta=fragment)
                                    ],
                                )
                            continue
                        reasoning = delta.get("thinking") or ""
                        if delta_type == "thinking_delta" and reasoning:
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
                        tokens_prompt = _prompt_tokens(usage) or tokens_prompt
                        tokens_completion = int(usage.get("output_tokens") or tokens_completion)
                    elif event_type == "message_stop":
                        yield ChatStreamChunk(
                            delta="",
                            done=True,
                            tokens_prompt=tokens_prompt,
                            tokens_completion=tokens_completion,
                            model=model_name,
                            finish_reason=finish_reason,
                            tool_calls=self._completed_calls(assembled) or None,
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
        tools: list[ToolDefinition] | None = None,
        tool_choice: Any = None,
        name_map: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        name_map = name_map or {}
        system_messages: list[str] = []
        anthropic_messages: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                if message.content:
                    system_messages.append(str(message.content))
                continue
            if message.role == "tool":
                # A tool result answers the assistant's tool_use and travels
                # on the user side of the conversation.
                block = {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id or "",
                    "content": str(message.content or ""),
                }
                self._append(anthropic_messages, "user", [block])
                continue
            if message.role not in {"user", "assistant"}:
                raise ValidationError(f"Anthropic chat does not support message role: {message.role}")
            blocks = _text_blocks(message.content)
            blocks.extend(anthropic_image_block(image) for image in message.images)
            if message.role == "assistant" and message.tool_calls:
                blocks.extend(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": name_map.get(call.name, tool_name_alias(call.name)),
                        "input": call.arguments or {},
                    }
                    for call in message.tool_calls
                )
            if not blocks:
                blocks = [{"type": "text", "text": ""}]
            self._append(anthropic_messages, message.role, blocks)

        payload: dict[str, Any] = {
            "model": self._resolve_model_name(model),
            "messages": [self._collapse(message) for message in anthropic_messages],
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
        stop = kwargs.get("stop")
        if stop:
            payload["stop_sequences"] = [stop] if isinstance(stop, str) else list(stop)
        if tools:
            payload["tools"] = [
                {
                    "name": name_map.get(tool.name, tool_name_alias(tool.name)),
                    "description": tool.description or "",
                    "input_schema": tool.parameters or {"type": "object", "properties": {}},
                }
                for tool in tools
            ]
        choice = _tool_choice(tool_choice, name_map) if tools else None
        if choice is not None:
            payload["tool_choice"] = choice
        return payload

    @staticmethod
    def _append(messages: list[dict[str, Any]], role: str, blocks: list[dict[str, Any]]) -> None:
        # The Messages API alternates roles, so consecutive turns of one role
        # (several tool results, a result followed by a user note) merge.
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].extend(blocks)
            return
        messages.append({"role": role, "content": list(blocks)})

    @staticmethod
    def _collapse(message: dict[str, Any]) -> dict[str, Any]:
        blocks = message["content"]
        if len(blocks) == 1 and blocks[0].get("type") == "text":
            return {"role": message["role"], "content": blocks[0].get("text", "")}
        return message

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
    def _extract_tool_calls(
        payload: dict[str, Any], reverse_map: dict[str, str]
    ) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for item in payload.get("content", []) or []:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                alias = str(item.get("name") or "")
                arguments = item.get("input")
                calls.append(
                    ToolCall(
                        id=str(item.get("id") or ""),
                        name=reverse_map.get(alias, alias),
                        arguments=arguments if isinstance(arguments, dict) else {},
                    )
                )
        return calls

    @staticmethod
    def _completed_calls(assembled: dict[int, dict[str, str]]) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for position in sorted(assembled):
            state = assembled[position]
            try:
                arguments = json.loads(state["arguments"]) if state["arguments"] else {}
            except ValueError:
                arguments = {}
            calls.append(
                ToolCall(
                    id=state["id"],
                    name=state["name"],
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )
        return calls

    @staticmethod
    def _resolve_model_name(model: str) -> str:
        if model.startswith("model:"):
            parts = model.split(":")
            if len(parts) >= 3:
                return ":".join(parts[2:])
        if model.startswith("anthropic:"):
            return model.split(":", 1)[1]
        return model
