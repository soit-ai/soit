# server/tests/unit/test_llm_port_tool_calling.py
"""Tests for LLM port function calling types."""

from app.kernel.ports.llm.interface import (
    ToolDefinition,
    ToolCall,
    ChatMessage,
    ChatResponse,
)


def test_tool_definition_construction():
    td = ToolDefinition(
        name="get_weather",
        description="Get weather for a city",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )
    assert td.name == "get_weather"
    assert td.description == "Get weather for a city"
    assert td.parameters["required"] == ["city"]


def test_tool_call_construction():
    tc = ToolCall(id="call_123", name="get_weather", arguments={"city": "Beijing"})
    assert tc.id == "call_123"
    assert tc.name == "get_weather"
    assert tc.arguments == {"city": "Beijing"}


def test_chat_response_tool_calls_default_none():
    resp = ChatResponse(text="hello", tokens_prompt=1, tokens_completion=1)
    assert resp.tool_calls is None


def test_chat_response_with_tool_calls():
    tc = ToolCall(id="call_1", name="get_weather", arguments={"city": "Beijing"})
    resp = ChatResponse(text=None, tokens_prompt=1, tokens_completion=1, tool_calls=[tc])
    assert resp.tool_calls is not None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "get_weather"


def test_chat_message_tool_call_id_default_none():
    msg = ChatMessage(role="user", content="hello")
    assert msg.tool_call_id is None
    assert msg.tool_calls is None
    assert msg.name is None


def test_chat_message_tool_result():
    msg = ChatMessage(role="tool", content="sunny, 25C", tool_call_id="call_1", name="get_weather")
    assert msg.role == "tool"
    assert msg.tool_call_id == "call_1"
    assert msg.name == "get_weather"


def test_chat_message_assistant_with_tool_calls():
    tc = ToolCall(id="call_1", name="get_weather", arguments={"city": "Beijing"})
    msg = ChatMessage(role="assistant", content=None, tool_calls=[tc])
    assert msg.tool_calls is not None
    assert msg.tool_calls[0].id == "call_1"
