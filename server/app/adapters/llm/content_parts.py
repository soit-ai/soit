"""Provider shapes for a message that shows images beside its text."""

from __future__ import annotations

from typing import Any

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import ChatImage, ChatMessage


def openai_chat_content(message: ChatMessage) -> str | list[dict[str, Any]] | None:
    """Chat Completions ``content``: a string, or text and image parts."""

    if not message.images:
        return message.content
    parts: list[dict[str, Any]] = []
    if message.content:
        parts.append({"type": "text", "text": message.content})
    for image in message.images:
        image_url: dict[str, Any] = {"url": image.url}
        if image.detail:
            image_url["detail"] = image.detail
        parts.append({"type": "image_url", "image_url": image_url})
    return parts


def openai_responses_content(message: ChatMessage) -> str | list[dict[str, Any]] | None:
    """Responses API ``content``: a string, or input text and input images."""

    if not message.images:
        return message.content
    parts: list[dict[str, Any]] = []
    if message.content:
        parts.append({"type": "input_text", "text": message.content})
    parts.extend(
        {"type": "input_image", "image_url": image.url, "detail": image.detail or "auto"}
        for image in message.images
    )
    return parts


def anthropic_image_block(image: ChatImage) -> dict[str, Any]:
    """Messages API image block from a URL or a ``data:`` URL."""

    if not image.is_data_url:
        return {"type": "image", "source": {"type": "url", "url": image.url}}
    header, _, data = image.url.partition(",")
    media_type = header.removeprefix("data:").split(";")[0]
    if ";base64" not in header or not media_type or not data:
        raise ValidationError("Image data URLs must be base64 encoded with a media type")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}
