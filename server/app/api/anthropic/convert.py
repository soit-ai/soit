"""Translation between Anthropic Messages wire shapes and the SOIT LLM port."""

from __future__ import annotations

from typing import Any, cast

from app.api.anthropic.schemas import MessageIn, ToolChoiceIn, ToolIn
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import (
    ChatImage,
    ChatMessage,
    ChatResponse,
    ToolCall,
    ToolDefinition,
)

# Blocks that carry no input the model acts on: the model's earlier reasoning
# is regenerated, not replayed.
_DROPPED_BLOCKS = frozenset({"thinking", "redacted_thinking"})

_STOP_REASONS = {
    "tool_calls": "tool_use",
    "tool_use": "tool_use",
    "function_call": "tool_use",
    "length": "max_tokens",
    "max_tokens": "max_tokens",
    "stop_sequence": "stop_sequence",
    "content_filter": "refusal",
    "refusal": "refusal",
}


def stop_reason(raw: str | None, *, has_tool_calls: bool) -> str:
    """Anthropic's stop reason for whatever the provider reported.

    A provider that reports a bare ``stop`` does not say whether a stop
    sequence ended the turn, so that case is ``end_turn``.
    """

    if has_tool_calls:
        return "tool_use"
    if raw is None:
        return "end_turn"
    return _STOP_REASONS.get(raw.lower(), "end_turn")


def _refuse(message: str, param: str = "messages") -> ValidationError:
    return ValidationError(message, {"param": param})


def _mapping(value: object) -> dict[str, Any] | None:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else None


def _text_of(block: dict[str, Any]) -> str:
    text = block.get("text")
    if not isinstance(text, str):
        raise _refuse("A text block needs a string text")
    return text


def _image_of(block: dict[str, Any]) -> ChatImage:
    source = _mapping(block.get("source"))
    if source is None:
        raise _refuse("An image block needs a source")
    kind = source.get("type")
    if kind == "base64":
        media_type = source.get("media_type")
        data = source.get("data")
        if not isinstance(media_type, str) or not isinstance(data, str) or not data:
            raise _refuse("A base64 image source needs media_type and data")
        return ChatImage(url=f"data:{media_type};base64,{data}")
    if kind == "url":
        url = source.get("url")
        if not isinstance(url, str) or not url:
            raise _refuse("A url image source needs a url")
        return ChatImage(url=url)
    raise _refuse(f"Unsupported image source type: {kind}")


def _tool_result_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise _refuse("A tool_result content must be a string or a list of blocks")
    texts: list[str] = []
    for raw in cast("list[object]", content):
        part = _mapping(raw)
        if part is not None and part.get("type") == "text":
            texts.append(_text_of(part))
        else:
            kind = part.get("type") if part is not None else type(raw).__name__
            raise _refuse(f"Unsupported content block in a tool_result: {kind}")
    return "\n".join(texts)


def _tool_input(block: dict[str, Any]) -> dict[str, Any]:
    raw = block.get("input")
    if raw is None:
        return {}
    arguments = _mapping(raw)
    if arguments is None:
        raise _refuse("A tool_use input must be an object")
    return arguments


def _blocks_to_messages(message: MessageIn, blocks: list[dict[str, Any]]) -> list[ChatMessage]:
    texts: list[str] = []
    images: list[ChatImage] = []
    calls: list[ToolCall] = []
    results: list[ChatMessage] = []
    for block in blocks:
        kind = block.get("type")
        if kind == "text":
            texts.append(_text_of(block))
        elif kind == "image" and message.role == "user":
            images.append(_image_of(block))
        elif kind == "tool_use" and message.role == "assistant":
            call_id, name = block.get("id"), block.get("name")
            if not isinstance(call_id, str) or not isinstance(name, str):
                raise _refuse("A tool_use block needs an id and a name")
            calls.append(ToolCall(id=call_id, name=name, arguments=_tool_input(block)))
        elif kind == "tool_result" and message.role == "user":
            call_id = block.get("tool_use_id")
            if not isinstance(call_id, str):
                raise _refuse("A tool_result block needs a tool_use_id")
            results.append(
                ChatMessage(role="tool", content=_tool_result_text(block), tool_call_id=call_id)
            )
        elif kind in _DROPPED_BLOCKS:
            continue
        else:
            raise _refuse(f"Unsupported {message.role} content block type: {kind}")
    # A tool's result answers the turn before the user's words.
    converted = list(results)
    if texts or images or calls or not results:
        converted.append(
            ChatMessage(
                role=message.role,
                content="\n".join(texts) if texts else None,
                tool_calls=calls or None,
                images=images,
            )
        )
    return converted


def to_chat_messages(
    system: str | list[dict[str, Any]] | None, messages: list[MessageIn]
) -> list[ChatMessage]:
    """Port messages from an Anthropic system prompt and messages."""

    converted: list[ChatMessage] = []
    if isinstance(system, str):
        system_text = system
    elif system:
        parts: list[str] = []
        for block in system:
            if block.get("type") != "text":
                raise _refuse(f"Unsupported system block type: {block.get('type')}", "system")
            parts.append(_text_of(block))
        system_text = "\n\n".join(parts)
    else:
        system_text = ""
    if system_text:
        converted.append(ChatMessage(role="system", content=system_text))
    for message in messages:
        if isinstance(message.content, str):
            converted.append(ChatMessage(role=message.role, content=message.content))
        else:
            converted.extend(_blocks_to_messages(message, message.content))
    return converted


def to_tool_definitions(tools: list[ToolIn] | None) -> list[ToolDefinition] | None:
    if not tools:
        return None
    definitions: list[ToolDefinition] = []
    for tool in tools:
        if tool.type not in (None, "custom"):
            # Silently dropping a tool Anthropic would run for the model would
            # change what the model can do without saying so.
            raise _refuse(
                f"Unsupported tool type: {tool.type}. Only client-defined tools are served",
                "tools",
            )
        definitions.append(
            ToolDefinition(
                name=tool.name,
                description=tool.description or "",
                parameters=tool.input_schema or {"type": "object", "properties": {}},
            )
        )
    return definitions


def to_tool_choice(choice: ToolChoiceIn | None) -> str | dict[str, Any] | None:
    """The OpenAI-style choice the model ports take."""

    if choice is None:
        return None
    if choice.type == "tool":
        if not choice.name:
            raise _refuse("A tool_choice of type tool needs a name", "tool_choice")
        return {"type": "function", "function": {"name": choice.name}}
    return {"auto": "auto", "any": "required", "none": "none"}[choice.type]


def tool_use_blocks(tool_calls: list[ToolCall] | None) -> list[dict[str, Any]]:
    return [
        {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
        for call in tool_calls or []
    ]


def usage(input_tokens: int, output_tokens: int) -> dict[str, int]:
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


def message_body(*, message_id: str, model: str, response: ChatResponse) -> dict[str, Any]:
    blocks = tool_use_blocks(response.tool_calls)
    content: list[dict[str, Any]] = []
    if response.text or not blocks:
        content.append({"type": "text", "text": response.text or ""})
    content.extend(blocks)
    return {
        "id": message_id,
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason(response.finish_reason, has_tool_calls=bool(blocks)),
        "stop_sequence": None,
        "usage": usage(response.tokens_prompt, response.tokens_completion),
    }
