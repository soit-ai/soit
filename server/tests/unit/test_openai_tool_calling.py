"""Tests for OpenAI adapter function calling format conversion."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.llm.openai import OpenAILLMPort
from app.kernel.ports.llm.interface import ChatMessage, ToolCall, ToolDefinition


def _make_openai_response(*, tool_calls=None, content=None, finish_reason="stop"):
    """Build a mock OpenAI ChatCompletion response."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = finish_reason
    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_openai_tool_call(*, call_id, name, arguments_json):
    """Build a mock OpenAI tool_call object."""
    tc = MagicMock()
    tc.id = call_id
    tc.type = "function"
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments_json  # JSON string
    return tc


@pytest.mark.asyncio
async def test_openai_chat_passes_tools_to_api():
    """When tools are provided, they are passed in OpenAI format."""
    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.chat = MagicMock()
    port.client.chat.completions = MagicMock()
    port.client.chat.completions.create = AsyncMock(
        return_value=_make_openai_response(content="hello")
    )

    tools = [
        ToolDefinition(
            name="get_weather",
            description="Get weather for a city",
            parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        )
    ]
    messages = [ChatMessage(role="user", content="hello")]
    await port.chat(messages, model="gpt-4", tools=tools, tool_choice="auto")

    call_kwargs = port.client.chat.completions.create.call_args
    assert "tools" in call_kwargs.kwargs
    assert call_kwargs.kwargs["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a city",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
        }
    ]
    assert call_kwargs.kwargs["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_openai_chat_parses_tool_calls():
    """When OpenAI returns tool_calls, they are parsed into ToolCall objects."""
    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.chat = MagicMock()
    port.client.chat.completions = MagicMock()

    openai_tool_call = _make_openai_tool_call(
        call_id="call_abc",
        name="get_weather",
        arguments_json='{"city": "Beijing"}',
    )
    port.client.chat.completions.create = AsyncMock(
        return_value=_make_openai_response(
            tool_calls=[openai_tool_call],
            content=None,
            finish_reason="tool_calls",
        )
    )

    messages = [ChatMessage(role="user", content="weather?")]
    resp = await port.chat(messages, model="gpt-4")

    assert resp.tool_calls is not None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].id == "call_abc"
    assert resp.tool_calls[0].name == "get_weather"
    assert resp.tool_calls[0].arguments == {"city": "Beijing"}
    assert resp.text is None


@pytest.mark.asyncio
async def test_openai_chat_no_tools_no_tool_calls():
    """Without tools, no tool_calls in response."""
    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.chat = MagicMock()
    port.client.chat.completions = MagicMock()
    port.client.chat.completions.create = AsyncMock(
        return_value=_make_openai_response(content="hi")
    )

    messages = [ChatMessage(role="user", content="hello")]
    resp = await port.chat(messages, model="gpt-4")

    assert resp.tool_calls is None
    assert resp.text == "hi"


@pytest.mark.asyncio
async def test_openai_chat_converts_tool_messages():
    """Tool result messages are converted correctly for OpenAI API."""
    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.chat = MagicMock()
    port.client.chat.completions = MagicMock()
    port.client.chat.completions.create = AsyncMock(
        return_value=_make_openai_response(content="The weather is sunny.")
    )

    tc = ToolCall(id="call_1", name="get_weather", arguments={"city": "Beijing"})
    messages = [
        ChatMessage(role="user", content="weather?"),
        ChatMessage(role="assistant", content=None, tool_calls=[tc]),
        ChatMessage(role="tool", content="sunny, 25C", tool_call_id="call_1", name="get_weather"),
    ]
    await port.chat(messages, model="gpt-4")

    call_kwargs = port.client.chat.completions.create.call_args
    openai_msgs = call_kwargs.kwargs["messages"]
    # assistant message should include tool_calls
    assert openai_msgs[1]["role"] == "assistant"
    assert openai_msgs[1].get("tool_calls") is not None
    assert openai_msgs[1]["tool_calls"][0]["id"] == "call_1"
    # tool message should include tool_call_id
    assert openai_msgs[2]["role"] == "tool"
    assert openai_msgs[2]["tool_call_id"] == "call_1"
    assert openai_msgs[2].get("name") == "get_weather"
