"""OpenAI request shapes become port messages in the SOIT vocabulary."""

from __future__ import annotations

import pytest

from app.api.openai.convert import finish_reason, to_chat_messages
from app.api.openai.schemas import ChatMessageIn
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import ChatImage


def test_messages_map_developer_to_system_and_keep_images() -> None:
    messages = to_chat_messages(
        [
            ChatMessageIn(role="developer", content="Answer in French."),
            ChatMessageIn(
                role="user",
                content=[
                    {"type": "text", "text": "What is this?"},
                    {"type": "image_url", "image_url": {"url": "https://x.test/a.png", "detail": "low"}},
                    {"type": "text", "text": "Be brief."},
                ],
            ),
        ]
    )

    assert messages[0].role == "system"
    assert messages[1].content == "What is this?\nBe brief."
    assert messages[1].images == [ChatImage(url="https://x.test/a.png", detail="low")]


def test_unsupported_content_parts_are_refused() -> None:
    with pytest.raises(ValidationError):
        to_chat_messages(
            [ChatMessageIn(role="user", content=[{"type": "input_audio", "text": None}])]
        )


def test_finish_reasons_use_the_openai_vocabulary() -> None:
    assert finish_reason("end_turn", has_tool_calls=False) == "stop"
    assert finish_reason("max_tokens", has_tool_calls=False) == "length"
    assert finish_reason("refusal", has_tool_calls=False) == "content_filter"
    assert finish_reason("stop", has_tool_calls=True) == "tool_calls"
    assert finish_reason(None, has_tool_calls=False) == "stop"
