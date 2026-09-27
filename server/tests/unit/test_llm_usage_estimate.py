"""Token estimates for calls whose provider never reported usage."""

from __future__ import annotations

from app.kernel.ports.llm.interface import (
    ChatImage,
    ChatMessage,
    ToolCall,
    ToolCallDelta,
    ToolDefinition,
)
from app.kernel.ports.llm.usage_estimate import (
    IMAGE_TOKENS,
    MESSAGE_OVERHEAD_TOKENS,
    GeneratedText,
    estimate_prompt_tokens,
    estimate_text_tokens,
)


def test_text_counts_four_ascii_characters_per_token_and_one_per_other_character() -> None:
    assert estimate_text_tokens(None) == 0
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens("abcd") == 1
    assert estimate_text_tokens("abcde") == 2
    assert estimate_text_tokens("café") == 2
    assert estimate_text_tokens("ñññ") == 3


def test_a_prompt_counts_its_messages_images_tool_calls_and_tools() -> None:
    messages = [
        ChatMessage(role="system", content="Be brief."),
        ChatMessage(
            role="user",
            content="What is in this picture?",
            images=[ChatImage(url="https://example.com/a.png")],
        ),
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id="call_1", name="lookup", arguments={"q": "x"})],
        ),
    ]
    tool = ToolDefinition(name="lookup", description="Find things", parameters={"type": "object"})

    bare = estimate_prompt_tokens(messages)
    with_tools = estimate_prompt_tokens(messages, [tool])

    text = estimate_text_tokens("Be brief.") + estimate_text_tokens("What is in this picture?")
    call = estimate_text_tokens("lookup") + estimate_text_tokens('{"q": "x"}')
    assert bare == 3 * MESSAGE_OVERHEAD_TOKENS + text + IMAGE_TOKENS + call
    assert with_tools > bare


def test_generated_text_counts_text_reasoning_and_calls_once() -> None:
    generated = GeneratedText()
    generated.add(delta="abcd", reasoning_delta="efgh")
    generated.add(tool_call_deltas=[ToolCallDelta(index=0, name="lookup", arguments_delta='{"q"')])
    generated.add(tool_call_deltas=[ToolCallDelta(index=0, arguments_delta=': "x"}')])
    # The same call, reported whole at the end, is not counted again.
    generated.add(tool_calls=[ToolCall(id="call_1", name="lookup", arguments={"q": "x"})])

    assert generated.tokens() == estimate_text_tokens('abcdefghlookup{"q": "x"}')


def test_generated_text_counts_calls_a_provider_reports_only_whole() -> None:
    generated = GeneratedText()
    generated.add(tool_calls=[ToolCall(id="call_1", name="lookup", arguments={"q": "x"})])

    assert generated.tokens() == estimate_text_tokens('lookup{"q": "x"}')


def test_a_call_name_repeated_on_every_argument_piece_counts_once() -> None:
    generated = GeneratedText()
    for piece in ('{"q"', ': "x"}'):
        generated.add(tool_call_deltas=[ToolCallDelta(index=0, name="lookup", arguments_delta=piece)])

    assert generated.tokens() == estimate_text_tokens('lookup{"q": "x"}')
