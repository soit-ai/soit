"""Tests for InMemoryLLMPort function calling."""

import pytest

from app.adapters.llm.memory import InMemoryLLMPort
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ToolCall,
    ToolDefinition,
)


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
async def test_inmemory_chat_with_tools_populates_required_string_arguments():
    port = InMemoryLLMPort()
    tools = [
        ToolDefinition(
            name="wf:ticket_triage",
            description="Execute ticket workflow",
            parameters={
                "type": "object",
                "required": ["customer_message", "customer_id", "priority"],
                "properties": {
                    "customer_message": {"type": "string"},
                    "customer_id": {"type": "string"},
                    "priority": {"type": "string"},
                },
            },
        )
    ]
    messages = [ChatMessage(role="user", content="Refund escalation for customer C-42")]

    resp = await port.chat(messages, model="test-model", tools=tools)

    assert resp.tool_calls is not None
    assert resp.tool_calls[0].arguments == {
        "customer_message": "Refund escalation for customer C-42",
        "customer_id": "demo-customer",
        "priority": "normal",
    }


@pytest.mark.asyncio
async def test_inmemory_chat_with_tools_returns_final_text_after_tool_result():
    port = InMemoryLLMPort()
    tools = [
        ToolDefinition(
            name="wf:ticket_triage",
            description="Execute ticket workflow",
            parameters={"type": "object", "additionalProperties": True},
        )
    ]
    messages = [
        ChatMessage(role="user", content="Create a review ticket"),
        ChatMessage(role="assistant", content=None, tool_calls=[ToolCall(id="call_1", name="wf:ticket_triage", arguments={})]),
        ChatMessage(role="tool", content="{'ticket_id': 'TICKET-1', 'status': 'created'}", tool_call_id="call_1"),
    ]

    resp = await port.chat(messages, model="test-model", tools=tools)

    assert resp.tool_calls is None
    assert "TICKET-1" in (resp.text or "")


@pytest.mark.asyncio
async def test_inmemory_chat_with_empty_tools_no_tool_call():
    """Empty tools list behaves like no tools."""
    port = InMemoryLLMPort()
    messages = [ChatMessage(role="user", content="hello")]
    resp = await port.chat(messages, model="test-model", tools=[])
    assert resp.tool_calls is None
    assert resp.text == "hello"
