"""The OpenAI adapter keeps the output controls a caller asked for."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.llm.openai import OpenAILLMPort
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import ChatMessage, ToolDefinition

TOOLS = [
    ToolDefinition(
        name="search.docs",
        description="Search the docs",
        parameters={"type": "object", "properties": {}},
    )
]

def _chat_completions_port() -> OpenAILLMPort:
    port = OpenAILLMPort(api_key="k", base_url="https://compatible.example/v1")
    port.client = MagicMock()
    message = SimpleNamespace(content="{}", tool_calls=None, reasoning_content=None)
    port.client.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=1),
            model="m",
        )
    )
    return port


@pytest.mark.asyncio
async def test_chat_completions_receive_the_output_controls() -> None:
    port = _chat_completions_port()

    await port.chat(
        [ChatMessage(role="user", content="json please")],
        model="gpt-4.1",
        tools=TOOLS,
        tool_choice={"type": "function", "function": {"name": "search.docs"}},
        response_format={"type": "json_object"},
        stop=["END"],
        seed=11,
    )

    params = port.client.chat.completions.create.call_args.kwargs
    assert params["response_format"] == {"type": "json_object"}
    assert params["stop"] == ["END"]
    assert params["seed"] == 11
    offered = params["tools"][0]["function"]["name"]
    assert params["tool_choice"] == {"type": "function", "function": {"name": offered}}


def _responses_port() -> OpenAILLMPort:
    port = OpenAILLMPort(api_key="k")
    port.client = MagicMock()
    port.client.responses.create = AsyncMock(
        return_value=SimpleNamespace(
            output=[],
            output_text="{}",
            status="completed",
            model="gpt-5.5",
            incomplete_details=None,
            usage=SimpleNamespace(input_tokens=3, output_tokens=1),
        )
    )
    return port


@pytest.mark.asyncio
async def test_responses_carry_structured_output_and_a_named_tool_choice() -> None:
    port = _responses_port()

    await port.chat(
        [ChatMessage(role="user", content="json please")],
        model="gpt-5.5",
        tools=TOOLS,
        tool_choice={"type": "function", "function": {"name": "search.docs"}},
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "answer", "schema": {"type": "object"}, "strict": True},
        },
        seed=11,
    )

    params = port.client.responses.create.call_args.kwargs
    assert params["text"] == {
        "format": {"type": "json_schema", "name": "answer", "schema": {"type": "object"}, "strict": True}
    }
    assert params["tool_choice"] == {"type": "function", "name": params["tools"][0]["name"]}
    assert "seed" not in params


@pytest.mark.asyncio
async def test_responses_refuse_stop_sequences_they_cannot_honour() -> None:
    port = _responses_port()

    with pytest.raises(ValidationError) as refused:
        await port.chat([ChatMessage(role="user", content="x")], model="gpt-5.5", stop="END")

    assert refused.value.details == {"param": "stop"}
    port.client.responses.create.assert_not_awaited()
