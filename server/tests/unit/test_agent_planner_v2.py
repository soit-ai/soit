"""Tests for AgentPlanner with native function calling."""

import pytest

from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ToolDefinition,
    ToolCall,
)
from app.adapters.llm.memory import InMemoryLLMPort
from app.modules.agent.runtime.planner import AgentPlanner, PlanResult


class MockFCLLMPort(InMemoryLLMPort):
    """LLM port that returns pre-configured responses."""

    def __init__(self, response: ChatResponse):
        self._response = response

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        return self._response


@pytest.mark.asyncio
async def test_planner_returns_tool_action_when_llm_returns_tool_calls():
    tc = ToolCall(id="call_1", name="get_weather", arguments={"city": "Beijing"})
    llm = MockFCLLMPort(ChatResponse(
        text=None, tokens_prompt=10, tokens_completion=5,
        finish_reason="tool_calls", tool_calls=[tc],
    ))
    planner = AgentPlanner(llm)
    tool_defs = [ToolDefinition(name="get_weather", description="Get weather", parameters={"type": "object"})]

    result = await planner.plan(
        messages=[ChatMessage(role="user", content="weather?")],
        tool_definitions=tool_defs,
        model="test-model",
        temperature=None,
        run_id="run_1",
    )

    assert result.action == "tool"
    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "get_weather"
    assert result.tool_calls[0].arguments == {"city": "Beijing"}
    assert result.response is None


@pytest.mark.asyncio
async def test_planner_returns_respond_action_when_llm_returns_text():
    llm = MockFCLLMPort(ChatResponse(
        text="The weather is sunny.", tokens_prompt=10, tokens_completion=5,
        finish_reason="stop",
    ))
    planner = AgentPlanner(llm)

    result = await planner.plan(
        messages=[ChatMessage(role="user", content="weather?")],
        tool_definitions=None,
        model="test-model",
        temperature=None,
        run_id="run_1",
    )

    assert result.action == "respond"
    assert result.response == "The weather is sunny."
    assert result.tool_calls is None


@pytest.mark.asyncio
async def test_planner_injects_memory_context():
    """Memory context is prepended as system message."""

    class RecordingLLM(InMemoryLLMPort):
        def __init__(self):
            self.captured_messages = None

        async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
            self.captured_messages = messages
            return ChatResponse(text="ok", tokens_prompt=1, tokens_completion=1, finish_reason="stop")

    llm = RecordingLLM()
    planner = AgentPlanner(llm)

    await planner.plan(
        messages=[ChatMessage(role="user", content="hello")],
        tool_definitions=None,
        memory_context="User prefers dark mode",
        model="test-model",
        temperature=None,
        run_id="run_1",
    )

    assert llm.captured_messages[0].role == "system"
    assert "User prefers dark mode" in llm.captured_messages[0].content


@pytest.mark.asyncio
async def test_planner_without_tools_does_not_pass_tools_to_llm():
    """When no tool_definitions, tools param is not passed."""

    class RecordingLLM(InMemoryLLMPort):
        def __init__(self):
            self.passed_tools = "NOT_SET"
            self.passed_tool_choice = "NOT_SET"

        async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
            self.passed_tools = tools
            self.passed_tool_choice = tool_choice
            return ChatResponse(text="ok", tokens_prompt=1, tokens_completion=1, finish_reason="stop")

    llm = RecordingLLM()
    planner = AgentPlanner(llm)

    await planner.plan(
        messages=[ChatMessage(role="user", content="hello")],
        tool_definitions=None,
        model="test-model",
        temperature=None,
        run_id="run_1",
    )

    assert llm.passed_tools is None
    assert llm.passed_tool_choice is None
