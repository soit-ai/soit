"""Native Anthropic tool calling: tool_use out, tool_result back, streamed input."""

from __future__ import annotations

from typing import Any

import pytest

from app.adapters.llm.anthropic import AnthropicLLMPort
from app.adapters.llm.tool_names import tool_name_alias
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import ChatMessage, ToolCall, ToolDefinition

SEARCH = ToolDefinition(
    name="tool:plugin:search",
    description="Search the knowledge base",
    parameters={"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
)


def _fake_client(monkeypatch, *, body: dict[str, Any] | None = None, lines: list[str] | None = None):
    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return body

        async def aiter_lines(self):
            for line in lines or []:
                yield line

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["json"] = json
            return FakeResponse()

        def stream(self, method, url, headers=None, json=None):
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.adapters.llm.anthropic.httpx.AsyncClient", FakeClient)
    return captured


@pytest.mark.asyncio
async def test_tools_are_offered_under_provider_safe_names(monkeypatch) -> None:
    alias = tool_name_alias(SEARCH.name)
    captured = _fake_client(
        monkeypatch,
        body={
            "model": "claude-sonnet-4-6",
            "stop_reason": "tool_use",
            "content": [
                {"type": "text", "text": "Let me look."},
                {"type": "tool_use", "id": "toolu_1", "name": alias, "input": {"q": "refund policy"}},
            ],
            "usage": {"input_tokens": 30, "output_tokens": 12},
        },
    )

    response = await AnthropicLLMPort(api_key="k").chat(
        [ChatMessage(role="user", content="What is the refund policy?")],
        model="model:anthropic:claude-sonnet-4-6",
        tools=[SEARCH],
        tool_choice="auto",
    )

    sent = captured["json"]
    assert sent["tools"] == [
        {"name": alias, "description": "Search the knowledge base", "input_schema": SEARCH.parameters}
    ]
    assert sent["tool_choice"] == {"type": "auto"}
    assert alias != SEARCH.name and ":" not in alias
    assert response.text == "Let me look."
    assert response.finish_reason == "tool_use"
    assert response.tool_calls == [ToolCall(id="toolu_1", name=SEARCH.name, arguments={"q": "refund policy"})]


@pytest.mark.asyncio
async def test_a_tool_round_trip_becomes_tool_use_and_tool_result_blocks(monkeypatch) -> None:
    alias = tool_name_alias(SEARCH.name)
    captured = _fake_client(
        monkeypatch,
        body={"content": [{"type": "text", "text": "Refunds within 30 days."}], "usage": {}},
    )

    await AnthropicLLMPort(api_key="k").chat(
        [
            ChatMessage(role="system", content="Be brief."),
            ChatMessage(role="user", content="Refund policy and shipping policy?"),
            ChatMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(id="toolu_1", name=SEARCH.name, arguments={"q": "refund"}),
                    ToolCall(id="toolu_2", name=SEARCH.name, arguments={"q": "shipping"}),
                ],
            ),
            ChatMessage(role="tool", content="30 days", tool_call_id="toolu_1"),
            ChatMessage(role="tool", content="5 days", tool_call_id="toolu_2"),
        ],
        model="claude-sonnet-4-6",
        tools=[SEARCH],
    )

    sent = captured["json"]
    assert sent["system"] == "Be brief."
    messages = sent["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant", "user"]
    assert messages[1]["content"] == [
        {"type": "tool_use", "id": "toolu_1", "name": alias, "input": {"q": "refund"}},
        {"type": "tool_use", "id": "toolu_2", "name": alias, "input": {"q": "shipping"}},
    ]
    # Both results travel in one user turn: the API alternates roles.
    assert messages[2]["content"] == [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "30 days"},
        {"type": "tool_result", "tool_use_id": "toolu_2", "content": "5 days"},
    ]


@pytest.mark.asyncio
async def test_streamed_tool_input_is_emitted_and_assembled(monkeypatch) -> None:
    alias = tool_name_alias(SEARCH.name)
    _fake_client(
        monkeypatch,
        lines=[
            'data: {"type":"message_start","message":{"usage":{"input_tokens":9,"output_tokens":1}}}',
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}',
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Searching."}}',
            f'data: {{"type":"content_block_start","index":1,"content_block":{{"type":"tool_use","id":"toolu_9","name":"{alias}","input":{{}}}}}}',
            'data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\\"q\\": \\"ref"}}',
            'data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"und\\"}"}}',
            'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":20}}',
            'data: {"type":"message_stop"}',
        ],
    )

    chunks = [
        chunk
        async for chunk in AnthropicLLMPort(api_key="k").stream_chat(
            [ChatMessage(role="user", content="refund?")], model="claude-sonnet-4-6", tools=[SEARCH]
        )
    ]

    deltas = [delta for chunk in chunks for delta in (chunk.tool_call_deltas or [])]
    assert deltas[0].index == 0 and deltas[0].id == "toolu_9" and deltas[0].name == SEARCH.name
    assert "".join(delta.arguments_delta for delta in deltas) == '{"q": "refund"}'
    assert "".join(chunk.delta for chunk in chunks) == "Searching."
    final = chunks[-1]
    assert final.done and final.finish_reason == "tool_use"
    assert final.tool_calls == [ToolCall(id="toolu_9", name=SEARCH.name, arguments={"q": "refund"})]
    assert final.tokens_prompt == 9 and final.tokens_completion == 20


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_choice", "expected"),
    [
        ("required", {"type": "any"}),
        ("none", {"type": "none"}),
        ({"type": "function", "function": {"name": SEARCH.name}}, {"type": "tool", "name": tool_name_alias(SEARCH.name)}),
    ],
)
async def test_tool_choice_translates(monkeypatch, tool_choice, expected) -> None:
    captured = _fake_client(monkeypatch, body={"content": [], "usage": {}})

    await AnthropicLLMPort(api_key="k").chat(
        [ChatMessage(role="user", content="go")],
        model="claude-sonnet-4-6",
        tools=[SEARCH],
        tool_choice=tool_choice,
    )

    assert captured["json"]["tool_choice"] == expected


@pytest.mark.asyncio
async def test_an_unknown_tool_choice_shape_is_refused(monkeypatch) -> None:
    _fake_client(monkeypatch, body={"content": [], "usage": {}})

    with pytest.raises(ValidationError):
        await AnthropicLLMPort(api_key="k").chat(
            [ChatMessage(role="user", content="go")],
            model="claude-sonnet-4-6",
            tools=[SEARCH],
            tool_choice={"type": "mystery"},
        )
