"""Tests for InMemoryLLMPort function calling."""

import pytest

from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ToolDefinition,
    ToolCall,
)
from app.adapters.llm.memory import InMemoryLLMPort


@pytest.mark.asyncio
async def test_inmemory_chat_without_tools():
    """Without tools, behaves as before — returns last user message."""
    port = InMemoryLLMPort()
    messages = [ChatMessage(role="user", content="hello")]
    resp = await port.chat(messages, model="test-model")
    assert resp.text == "hello"
    assert resp.tool_calls is None


@pytest.mark.asyncio
async def test_inmemory_chat_with_tools_returns_tool_call():
    """With tools, returns a mock tool call for the first tool."""
    port = InMemoryLLMPort()
    tools = [
        ToolDefinition(
            name="get_weather",
            description="Get weather",
            parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        )
    ]
    messages = [ChatMessage(role="user", content="hello")]
    resp = await port.chat(messages, model="test-model", tools=tools)
    assert resp.tool_calls is not None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "get_weather"
    assert resp.tool_calls[0].id == "call_get_weather"
    assert resp.tool_calls[0].arguments == {}
    assert resp.text is None


@pytest.mark.asyncio
async def test_inmemory_chat_with_empty_tools_no_tool_call():
    """Empty tools list behaves like no tools."""
    port = InMemoryLLMPort()
    messages = [ChatMessage(role="user", content="hello")]
    resp = await port.chat(messages, model="test-model", tools=[])
    assert resp.tool_calls is None
    assert resp.text == "hello"
