"""Translation between OpenAI wire shapes and the SOIT LLM port."""

from __future__ import annotations

import json
from typing import Any

from app.api.openai.schemas import ChatMessageIn, ToolIn
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import (
    ChatImage,
    ChatMessage,
    ChatResponse,
    ToolCall,
    ToolCallDelta,
    ToolDefinition,
)

_FINISH_REASONS = {
    "stop": "stop",
    "end_turn": "stop",
    "stop_sequence": "stop",
    "length": "length",
    "max_tokens": "length",
    "tool_calls": "tool_calls",
    "tool_use": "tool_calls",
    "function_call": "tool_calls",
    "content_filter": "content_filter",
    "refusal": "content_filter",
}


def finish_reason(raw: str | None, *, has_tool_calls: bool) -> str:
    """OpenAI's finish reason for whatever the provider reported."""

    if has_tool_calls:
        return "tool_calls"
    if raw is None:
        return "stop"
    return _FINISH_REASONS.get(raw.lower(), "stop")


def _arguments(raw: str, *, call_id: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise ValidationError(
            "Tool call arguments must be a JSON object",
            {"param": "messages", "tool_call_id": call_id},
        ) from exc
    if not isinstance(parsed, dict):
        raise ValidationError(
            "Tool call arguments must be a JSON object",
            {"param": "messages", "tool_call_id": call_id},
        )
    return parsed


def to_chat_messages(messages: list[ChatMessageIn]) -> list[ChatMessage]:
    """Port messages from OpenAI messages; ``developer`` is a system turn."""

    converted: list[ChatMessage] = []
    for message in messages:
        text: str | None
        images: list[ChatImage] = []
        if isinstance(message.content, list):
            texts: list[str] = []
            for part in message.content:
                if part.type == "text" and part.text is not None:
                    texts.append(part.text)
                elif part.type == "image_url" and part.image_url is not None:
                    images.append(ChatImage(url=part.image_url.url, detail=part.image_url.detail))
                else:
                    raise ValidationError(
                        f"Unsupported content part type: {part.type}", {"param": "messages"}
                    )
            text = "\n".join(texts) if texts else None
        else:
            text = message.content
        tool_calls = (
            [
                ToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=_arguments(call.function.arguments, call_id=call.id),
                )
                for call in message.tool_calls
            ]
            if message.tool_calls
            else None
        )
        converted.append(
            ChatMessage(
                role="system" if message.role == "developer" else message.role,
                content=text,
                tool_call_id=message.tool_call_id,
                tool_calls=tool_calls,
                name=message.name,
                images=images,
            )
        )
    return converted


def to_tool_definitions(tools: list[ToolIn] | None) -> list[ToolDefinition] | None:
    if not tools:
        return None
    return [
        ToolDefinition(
            name=tool.function.name,
            description=tool.function.description or "",
            parameters=tool.function.parameters or {"type": "object", "properties": {}},
        )
        for tool in tools
    ]


def tool_calls_out(tool_calls: list[ToolCall] | None) -> list[dict[str, Any]] | None:
    if not tool_calls:
        return None
    return [
        {
            "id": call.id,
            "type": "function",
            "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
        }
        for call in tool_calls
    ]


def tool_call_deltas_out(deltas: list[ToolCallDelta]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for delta in deltas:
        item: dict[str, Any] = {"index": delta.index}
        function: dict[str, Any] = {"arguments": delta.arguments_delta}
        if delta.id:
            item["id"] = delta.id
            item["type"] = "function"
        if delta.name:
            function["name"] = delta.name
        item["function"] = function
        out.append(item)
    return out


def usage(prompt_tokens: int, completion_tokens: int) -> dict[str, int]:
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def completion_body(
    *, completion_id: str, created: int, model: str, response: ChatResponse
) -> dict[str, Any]:
    tool_calls = tool_calls_out(response.tool_calls)
    message: dict[str, Any] = {"role": "assistant", "content": response.text}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason(
                    response.finish_reason, has_tool_calls=bool(tool_calls)
                ),
            }
        ],
        "usage": usage(response.tokens_prompt, response.tokens_completion),
        "system_fingerprint": None,
    }


def chunk_body(
    *,
    completion_id: str,
    created: int,
    model: str,
    delta: dict[str, Any] | None,
    finish: str | None = None,
    usage_block: dict[str, int] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "system_fingerprint": None,
        "choices": (
            []
            if delta is None
            else [{"index": 0, "delta": delta, "finish_reason": finish}]
        ),
    }
    if usage_block is not None:
        body["usage"] = usage_block
    return body
