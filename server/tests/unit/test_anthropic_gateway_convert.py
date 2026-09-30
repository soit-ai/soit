"""Anthropic Messages shapes translate to and from the SOIT LLM port."""

from __future__ import annotations

import pytest

from app.api.anthropic.convert import (
    message_body,
    stop_reason,
    to_chat_messages,
    to_tool_choice,
    to_tool_definitions,
)
from app.api.anthropic.schemas import MessageIn, ToolChoiceIn, ToolIn
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import ChatResponse, ToolCall


def _message(role: str, content) -> MessageIn:
    return MessageIn(role=role, content=content)


def test_a_system_prompt_and_plain_turns_become_chat_messages() -> None:
    messages = to_chat_messages(
        "Be brief.", [_message("user", "hi"), _message("assistant", "hello")]
    )

    assert [(m.role, m.content) for m in messages] == [
        ("system", "Be brief."),
        ("user", "hi"),
        ("assistant", "hello"),
    ]


def test_system_blocks_are_joined_and_cache_control_is_ignored() -> None:
    messages = to_chat_messages(
        [
            {"type": "text", "text": "One."},
            {"type": "text", "text": "Two.", "cache_control": {"type": "ephemeral"}},
        ],
        [_message("user", "hi")],
    )

    assert messages[0].role == "system"
    assert messages[0].content == "One.\n\nTwo."


def test_a_system_block_that_is_not_text_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        to_chat_messages([{"type": "image", "source": {}}], [_message("user", "hi")])

    assert caught.value.details == {"param": "system"}


def test_user_blocks_carry_text_and_images() -> None:
    messages = to_chat_messages(
        None,
        [
            _message(
                "user",
                [
                    {"type": "text", "text": "what is this"},
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"},
                    },
                    {"type": "image", "source": {"type": "url", "url": "https://x.test/a.png"}},
                ],
            )
        ],
    )

    assert len(messages) == 1
    assert messages[0].content == "what is this"
    assert [image.url for image in messages[0].images] == [
        "data:image/png;base64,QUJD",
        "https://x.test/a.png",
    ]


def test_an_assistant_tool_use_and_the_users_tool_result_become_call_and_tool_messages() -> None:
    messages = to_chat_messages(
        None,
        [
            _message("user", "find order 42"),
            _message(
                "assistant",
                [
                    {"type": "thinking", "thinking": "hmm", "signature": "s"},
                    {"type": "text", "text": "Looking."},
                    {"type": "tool_use", "id": "toolu_1", "name": "lookup", "input": {"q": "42"}},
                ],
            ),
            _message(
                "user",
                [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "content": [{"type": "text", "text": "shipped"}],
                    },
                    {"type": "text", "text": "thanks"},
                ],
            ),
        ],
    )

    assistant = messages[1]
    assert assistant.content == "Looking."
    assert assistant.tool_calls == [ToolCall(id="toolu_1", name="lookup", arguments={"q": "42"})]
    assert (messages[2].role, messages[2].tool_call_id, messages[2].content) == (
        "tool",
        "toolu_1",
        "shipped",
    )
    assert (messages[3].role, messages[3].content) == ("user", "thanks")


def test_a_tool_result_alone_does_not_add_an_empty_user_turn() -> None:
    messages = to_chat_messages(
        None,
        [_message("user", [{"type": "tool_result", "tool_use_id": "t", "content": "ok"}])],
    )

    assert [m.role for m in messages] == ["tool"]


@pytest.mark.parametrize(
    "block",
    [
        {"type": "document", "source": {}},
        {"type": "server_tool_use", "id": "x", "name": "web_search", "input": {}},
        {"type": "image", "source": {"type": "file", "file_id": "f"}},
        {"type": "tool_result", "tool_use_id": "t", "content": [{"type": "image", "source": {}}]},
    ],
)
def test_a_block_that_cannot_be_carried_is_refused_by_name(block) -> None:
    with pytest.raises(ValidationError):
        to_chat_messages(None, [_message("user", [block])])


def test_tools_map_to_definitions_and_server_tools_are_refused() -> None:
    definitions = to_tool_definitions(
        [ToolIn(name="lookup", description="Find", input_schema={"type": "object"})]
    )
    assert definitions is not None
    assert (definitions[0].name, definitions[0].parameters) == ("lookup", {"type": "object"})

    with pytest.raises(ValidationError):
        to_tool_definitions([ToolIn(name="web_search", type="web_search_20250305")])


def test_tool_choice_maps_to_the_choice_the_ports_take() -> None:
    assert to_tool_choice(None) is None
    assert to_tool_choice(ToolChoiceIn(type="auto")) == "auto"
    assert to_tool_choice(ToolChoiceIn(type="any")) == "required"
    assert to_tool_choice(ToolChoiceIn(type="none")) == "none"
    assert to_tool_choice(ToolChoiceIn(type="tool", name="lookup")) == {
        "type": "function",
        "function": {"name": "lookup"},
    }
    with pytest.raises(ValidationError):
        to_tool_choice(ToolChoiceIn(type="tool"))


@pytest.mark.parametrize(
    ("raw", "has_calls", "expected"),
    [
        (None, False, "end_turn"),
        ("stop", False, "end_turn"),
        ("end_turn", False, "end_turn"),
        ("length", False, "max_tokens"),
        ("max_tokens", False, "max_tokens"),
        ("stop_sequence", False, "stop_sequence"),
        ("content_filter", False, "refusal"),
        ("stop", True, "tool_use"),
        ("tool_calls", False, "tool_use"),
    ],
)
def test_stop_reasons_follow_what_the_provider_reported(raw, has_calls, expected) -> None:
    assert stop_reason(raw, has_tool_calls=has_calls) == expected


def test_a_message_body_lists_text_then_tool_use_blocks() -> None:
    body = message_body(
        message_id="msg_1",
        model="model:test:chat",
        response=ChatResponse(
            text="Looking.",
            tokens_prompt=10,
            tokens_completion=4,
            model="m",
            finish_reason="tool_calls",
            tool_calls=[ToolCall(id="toolu_1", name="lookup", arguments={"q": "42"})],
        ),
    )

    assert body["content"] == [
        {"type": "text", "text": "Looking."},
        {"type": "tool_use", "id": "toolu_1", "name": "lookup", "input": {"q": "42"}},
    ]
    assert body["stop_reason"] == "tool_use"
    assert body["usage"] == {"input_tokens": 10, "output_tokens": 4}
    assert body["type"] == "message" and body["role"] == "assistant"


def test_an_empty_reply_still_has_one_text_block() -> None:
    body = message_body(
        message_id="msg_1",
        model="m",
        response=ChatResponse(text="", tokens_prompt=1, tokens_completion=0, model="m"),
    )

    assert body["content"] == [{"type": "text", "text": ""}]
