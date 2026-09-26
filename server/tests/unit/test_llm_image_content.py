"""Images travel beside message text to every adapter that can send them."""

from __future__ import annotations

import pytest

from app.adapters.llm.anthropic import AnthropicLLMPort
from app.adapters.llm.content_parts import (
    anthropic_image_block,
    openai_chat_content,
    openai_responses_content,
)
from app.adapters.llm.litellm import LiteLLMPort
from app.adapters.llm.openai import OpenAILLMPort
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import ChatImage, ChatMessage
from app.kernel.ports.llm.policy import LLMPolicyGateway
from app.kernel.safety.rules import RuleContentSafetyPort

PNG = "data:image/png;base64,iVBORw0KGgo="
PHOTO = "https://example.com/receipt.jpg"


def _message() -> ChatMessage:
    return ChatMessage(
        role="user",
        content="What is on this receipt?",
        images=[ChatImage(url=PHOTO, detail="high"), ChatImage(url=PNG)],
    )


def test_chat_completions_content_carries_text_then_images() -> None:
    assert openai_chat_content(_message()) == [
        {"type": "text", "text": "What is on this receipt?"},
        {"type": "image_url", "image_url": {"url": PHOTO, "detail": "high"}},
        {"type": "image_url", "image_url": {"url": PNG}},
    ]
    assert openai_chat_content(ChatMessage(role="user", content="plain")) == "plain"


def test_responses_content_uses_input_parts() -> None:
    assert openai_responses_content(_message()) == [
        {"type": "input_text", "text": "What is on this receipt?"},
        {"type": "input_image", "image_url": PHOTO, "detail": "high"},
        {"type": "input_image", "image_url": PNG, "detail": "auto"},
    ]


def test_openai_and_litellm_messages_include_the_images() -> None:
    converted = OpenAILLMPort._convert_messages([_message()])
    assert converted[0]["content"][1]["type"] == "image_url"
    litellm = LiteLLMPort._messages([_message()])
    assert litellm[0]["content"][2] == {"type": "image_url", "image_url": {"url": PNG}}


def test_anthropic_blocks_from_urls_and_data_urls() -> None:
    assert anthropic_image_block(ChatImage(url=PHOTO)) == {
        "type": "image",
        "source": {"type": "url", "url": PHOTO},
    }
    assert anthropic_image_block(ChatImage(url=PNG)) == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": "iVBORw0KGgo="},
    }
    with pytest.raises(ValidationError):
        anthropic_image_block(ChatImage(url="data:image/png,not-base64"))


def test_anthropic_payload_places_images_after_the_text() -> None:
    payload = AnthropicLLMPort(api_key="k")._build_messages_payload(
        messages=[_message()],
        model="claude-sonnet-4-6",
        temperature=None,
        max_tokens=None,
        stream=False,
    )

    content = payload["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "What is on this receipt?"}
    assert [block["type"] for block in content[1:]] == ["image", "image"]


@pytest.mark.asyncio
async def test_content_safety_keeps_the_images_when_it_rewrites_the_text(ctx) -> None:
    gateway = LLMPolicyGateway(
        gateway=object(), ctx=ctx, content_safety=RuleContentSafetyPort()
    )
    message = ChatMessage(
        role="user",
        content="my token is ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        images=[ChatImage(url=PHOTO)],
    )

    inspected = await gateway._inspect_messages([message], [])

    assert "ghp_" not in (inspected[0].content or "")
    assert inspected[0].images == [ChatImage(url=PHOTO)]
