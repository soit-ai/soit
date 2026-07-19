"""Tests for OpenAI adapter function calling format conversion."""

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.llm.openai import OpenAILLMPort
from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.ports.llm.interface import ChatMessage, ToolCall, ToolDefinition


def _make_openai_response(
    *,
    tool_calls=None,
    content=None,
    reasoning_content=None,
    finish_reason="stop",
):
    """Build a mock OpenAI ChatCompletion response."""
    message = MagicMock()
    message.content = content
    message.reasoning_content = reasoning_content
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


def _make_responses_api_response(
    *,
    output=None,
    output_text="",
    status="completed",
    model="gpt-5.5",
):
    """Build a mock OpenAI Responses API response."""

    return SimpleNamespace(
        output=output or [],
        output_text=output_text,
        status=status,
        model=model,
        incomplete_details=None,
        usage=SimpleNamespace(input_tokens=12, output_tokens=7),
    )


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
async def test_openai_compatible_stream_forwards_and_parses_tool_calls():
    """Compatible streaming must preserve tool definitions, deltas, and names."""

    port = OpenAILLMPort(
        api_key="test-key",
        base_url="https://compatible.example/v1",
    )
    port.client = MagicMock()
    port.client.chat = MagicMock()
    port.client.chat.completions = MagicMock()
    tool = ToolDefinition(
        name="tool:function:weather",
        description="Get weather for a city",
        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
    )
    safe_name = port._tool_name_alias(tool.name)

    async def events():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        reasoning_content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id="call_compat",
                                function=SimpleNamespace(
                                    name=safe_name,
                                    arguments='{"city":',
                                ),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        reasoning_content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id=None,
                                function=SimpleNamespace(
                                    name=None,
                                    arguments='"Shanghai"}',
                                ),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        reasoning_content=None,
                        tool_calls=[],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=None,
        )

    port.client.chat.completions.create = AsyncMock(return_value=events())

    chunks = [
        chunk
        async for chunk in port.stream_chat(
            [ChatMessage(role="user", content="Weather in Shanghai?")],
            model="gpt-4",
            tools=[tool],
            tool_choice="auto",
        )
    ]

    params = port.client.chat.completions.create.call_args.kwargs
    assert params["tools"] == [
        {
            "type": "function",
            "function": {
                "name": safe_name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
    ]
    assert params["tool_choice"] == "auto"
    assert chunks[0].tool_call_deltas is not None
    assert chunks[0].tool_call_deltas[0].name == tool.name
    assert chunks[1].tool_call_deltas[0].arguments_delta == '"Shanghai"}'
    assert chunks[-1].done is True
    assert chunks[-1].tool_calls is not None
    assert chunks[-1].tool_calls[0].id == "call_compat"
    assert chunks[-1].tool_calls[0].name == tool.name
    assert chunks[-1].tool_calls[0].arguments == {"city": "Shanghai"}


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
async def test_openai_chat_exposes_provider_reasoning_content():
    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.chat = MagicMock()
    port.client.chat.completions = MagicMock()
    port.client.chat.completions.create = AsyncMock(
        return_value=_make_openai_response(
            content="The answer is 4.",
            reasoning_content="I evaluated the arithmetic.",
        )
    )

    response = await port.chat(
        [ChatMessage(role="user", content="What is 2 + 2?")],
        model="gpt-5.1",
    )

    assert response.reasoning == "I evaluated the arithmetic."


@pytest.mark.asyncio
async def test_openai_stream_exposes_provider_reasoning_delta():
    async def events():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=None, reasoning_content="Checking."),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="Done.", reasoning_content=None),
                    finish_reason="stop",
                )
            ],
            usage=None,
        )

    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.chat = MagicMock()
    port.client.chat.completions = MagicMock()
    port.client.chat.completions.create = AsyncMock(return_value=events())

    chunks = [
        chunk
        async for chunk in port.stream_chat(
            [ChatMessage(role="user", content="Check this")],
            model="gpt-5.1",
        )
    ]

    assert chunks[0].reasoning_delta == "Checking."
    assert chunks[1].delta == "Done."


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


@pytest.mark.asyncio
async def test_openai_chat_roundtrips_canonical_tool_refs_through_safe_aliases():
    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.chat = MagicMock()
    port.client.chat.completions = MagicMock()

    async def create_completion(**kwargs):
        sent_name = kwargs["tools"][0]["function"]["name"]
        assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", sent_name)
        assert sent_name != "tool:function:time_now"
        assert kwargs["messages"][1]["tool_calls"][0]["function"]["name"] == sent_name
        return _make_openai_response(
            tool_calls=[
                _make_openai_tool_call(
                    call_id="call_time",
                    name=sent_name,
                    arguments_json="{}",
                )
            ],
            content=None,
            finish_reason="tool_calls",
        )

    port.client.chat.completions.create = AsyncMock(side_effect=create_completion)
    tool = ToolDefinition(
        name="tool:function:time_now",
        description="Return the current time",
        parameters={"type": "object"},
    )
    messages = [
        ChatMessage(role="user", content="What time is it?"),
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id="previous", name=tool.name, arguments={})],
        ),
        ChatMessage(role="tool", content="{}", tool_call_id="previous", name=tool.name),
    ]

    response = await port.chat(messages, model="gpt-5.1", tools=[tool])

    assert response.tool_calls is not None
    assert response.tool_calls[0].name == "tool:function:time_now"


@pytest.mark.asyncio
async def test_gpt_55_reasoning_with_tools_uses_responses_api():
    """Official GPT-5.5 tool planning must use the Responses API."""

    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.responses = MagicMock()

    tool = ToolDefinition(
        name="tool:function:time_now",
        description="Return the current time",
        parameters={"type": "object", "properties": {}},
    )
    safe_name = port._tool_name_alias(tool.name)
    port.client.responses.create = AsyncMock(
        return_value=_make_responses_api_response(
            output=[
                SimpleNamespace(
                    type="reasoning",
                    summary=[SimpleNamespace(text="I should call the time tool.")],
                ),
                SimpleNamespace(
                    type="function_call",
                    id="fc_1",
                    call_id="call_time",
                    name=safe_name,
                    arguments="{}",
                ),
            ]
        )
    )

    response = await port.chat(
        [ChatMessage(role="user", content="What time is it?")],
        model="gpt-5.5",
        tools=[tool],
        tool_choice="auto",
        reasoning_effort="high",
    )

    port.client.responses.create.assert_awaited_once()
    params = port.client.responses.create.call_args.kwargs
    assert params["model"] == "gpt-5.5"
    assert params["reasoning"] == {"effort": "high", "summary": "auto"}
    assert params["tools"] == [
        {
            "type": "function",
            "name": safe_name,
            "description": "Return the current time",
            "parameters": {"type": "object", "properties": {}},
        }
    ]
    assert params["tool_choice"] == "auto"
    assert params["input"] == [{"role": "user", "content": "What time is it?"}]
    assert response.tool_calls is not None
    assert response.tool_calls[0].id == "call_time"
    assert response.tool_calls[0].name == tool.name
    assert response.reasoning == "I should call the time tool."
    assert response.tokens_prompt == 12
    assert response.tokens_completion == 7


@pytest.mark.asyncio
async def test_gpt_55_maps_hosted_tools_citations_and_generated_files():
    binary = SimpleNamespace(aread=AsyncMock(return_value=b"name,value\nSOIT,1\n"))
    url_annotation = SimpleNamespace(
        type="url_citation",
        url="https://example.com/source",
        title="Primary source",
        start_index=0,
        end_index=14,
    )
    file_annotation = SimpleNamespace(
        type="container_file_citation",
        container_id="container_1",
        file_id="file_1",
        filename="report.csv",
        start_index=15,
        end_index=25,
    )
    response_object = _make_responses_api_response(
        output_text="Sourced answer with report.csv",
        output=[
            SimpleNamespace(
                type="web_search_call",
                id="ws_1",
                status="completed",
                action=SimpleNamespace(
                    type="search",
                    query="SOIT",
                    sources=[SimpleNamespace(type="url", url="https://example.com/source")],
                ),
            ),
            SimpleNamespace(
                type="code_interpreter_call",
                id="ci_1",
                status="completed",
                container_id="container_1",
                code="print('SOIT')",
                outputs=[SimpleNamespace(type="logs", logs="SOIT")],
            ),
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text="Sourced answer with report.csv",
                        annotations=[url_annotation, file_annotation],
                    )
                ],
            ),
        ],
    )
    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.responses = MagicMock()
    port.client.responses.create = AsyncMock(return_value=response_object)
    port.client.containers.files.content.retrieve = AsyncMock(return_value=binary)

    result = await port.chat(
        [ChatMessage(role="user", content="Research SOIT and make a CSV")],
        model="gpt-5.5",
        hosted_tools=[
            {"type": "web_search"},
            {
                "type": "code_interpreter",
                "container": {"type": "auto", "memory_limit": "4g"},
            },
        ],
    )

    params = port.client.responses.create.call_args.kwargs
    assert params["tools"] == [
        {"type": "web_search"},
        {
            "type": "code_interpreter",
            "container": {"type": "auto", "memory_limit": "4g"},
        },
    ]
    assert params["include"] == ["web_search_call.action.sources"]
    assert [call.name for call in result.hosted_tool_calls] == [
        "openai.web_search",
        "openai.code_interpreter",
    ]
    assert result.citations[0]["title"] == "Primary source"
    assert result.citations[0]["source_uri"] == "https://example.com/source"
    assert result.hosted_artifacts[0].filename == "report.csv"
    assert result.hosted_artifacts[0].content == b"name,value\nSOIT,1\n"
    port.client.containers.files.content.retrieve.assert_awaited_once_with(
        "file_1",
        container_id="container_1",
    )


@pytest.mark.asyncio
async def test_hosted_tools_reject_openai_compatible_chat_completions():
    port = OpenAILLMPort(
        api_key="test-key",
        base_url="https://compatible.example/v1",
    )

    with pytest.raises(ValidationError, match="official OpenAI GPT-5.5"):
        await port.chat(
            [ChatMessage(role="user", content="search")],
            model="gpt-5.5",
            hosted_tools=[{"type": "web_search"}],
        )


@pytest.mark.asyncio
async def test_gpt_55_openai_compatible_route_keeps_chat_completions():
    """Custom OpenAI-compatible endpoints must not be forced onto Responses."""

    port = OpenAILLMPort(
        api_key="test-key",
        base_url="https://compatible.example/v1",
    )
    port.client = MagicMock()
    port.client.chat = MagicMock()
    port.client.chat.completions = MagicMock()
    port.client.chat.completions.create = AsyncMock(
        return_value=_make_openai_response(content="compatible")
    )

    response = await port.chat(
        [ChatMessage(role="user", content="hello")],
        model="gpt-5.5",
        reasoning_effort="high",
    )

    port.client.chat.completions.create.assert_awaited_once()
    assert response.text == "compatible"


@pytest.mark.asyncio
async def test_gpt_55_stream_maps_responses_text_reasoning_and_usage():
    """Responses streaming remains compatible with normalized chat chunks."""

    async def events():
        yield SimpleNamespace(
            type="response.reasoning_summary_text.delta",
            delta="Checking the request.",
        )
        yield SimpleNamespace(type="response.output_text.delta", delta="Done.")
        yield SimpleNamespace(
            type="response.completed",
            response=_make_responses_api_response(output_text="Done."),
        )

    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.responses = MagicMock()
    port.client.responses.create = AsyncMock(return_value=events())

    chunks = [
        chunk
        async for chunk in port.stream_chat(
            [ChatMessage(role="user", content="Check this")],
            model="gpt-5.5",
            reasoning_effort="high",
        )
    ]

    assert chunks[0].reasoning_delta == "Checking the request."
    assert chunks[1].delta == "Done."
    assert chunks[2].done is True
    assert chunks[2].tokens_prompt == 12
    assert chunks[2].tokens_completion == 7


@pytest.mark.asyncio
async def test_gpt_55_stream_terminalizes_incomplete_response_with_length_reason():
    """Responses token limits must be exposed as a terminal length chunk."""

    incomplete = _make_responses_api_response(status="incomplete")
    incomplete.incomplete_details = SimpleNamespace(reason="max_output_tokens")

    async def events():
        yield SimpleNamespace(type="response.output_text.delta", delta="Partial")
        yield SimpleNamespace(type="response.incomplete", response=incomplete)

    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.responses = MagicMock()
    port.client.responses.create = AsyncMock(return_value=events())

    chunks = [
        chunk
        async for chunk in port.stream_chat(
            [ChatMessage(role="user", content="Think deeply")],
            model="gpt-5.5",
        )
    ]

    assert chunks[-1].done is True
    assert chunks[-1].finish_reason == "length"
    assert chunks[-1].tokens_prompt == 12
    assert chunks[-1].tokens_completion == 7


@pytest.mark.asyncio
async def test_gpt_55_stream_raises_provider_error_for_failed_response():
    """Responses failures must fail the SOIT interaction instead of looking successful."""

    failed = _make_responses_api_response(status="failed")
    failed.error = SimpleNamespace(code="server_error", message="provider failed")

    async def events():
        yield SimpleNamespace(type="response.failed", response=failed)

    port = OpenAILLMPort(api_key="test-key")
    port.client = MagicMock()
    port.client.responses = MagicMock()
    port.client.responses.create = AsyncMock(return_value=events())

    with pytest.raises(KernelError, match="OpenAI Responses stream failed") as exc_info:
        _ = [
            chunk
            async for chunk in port.stream_chat(
                [ChatMessage(role="user", content="hello")],
                model="gpt-5.5",
            )
        ]

    assert exc_info.value.code == "LLM_PROVIDER_ERROR"
    assert exc_info.value.details["provider_error_code"] == "server_error"


@pytest.mark.asyncio
async def test_gpt_55_stream_maps_function_call_deltas_and_result_history():
    """Responses function calls preserve streaming deltas and prior tool output."""

    tool = ToolDefinition(
        name="tool:function:time_now",
        description="Return the current time",
        parameters={"type": "object"},
    )
    port = OpenAILLMPort(api_key="test-key")
    safe_name = port._tool_name_alias(tool.name)

    async def events():
        yield SimpleNamespace(
            type="response.output_item.added",
            output_index=0,
            item=SimpleNamespace(
                type="function_call",
                id="fc_stream",
                call_id="call_stream",
                name=safe_name,
                arguments="",
            ),
        )
        yield SimpleNamespace(
            type="response.function_call_arguments.delta",
            output_index=0,
            delta='{"timezone":',
        )
        yield SimpleNamespace(
            type="response.function_call_arguments.delta",
            output_index=0,
            delta='"UTC"}',
        )
        yield SimpleNamespace(
            type="response.completed",
            response=_make_responses_api_response(
                output=[
                    SimpleNamespace(
                        type="function_call",
                        id="fc_stream",
                        call_id="call_stream",
                        name=safe_name,
                        arguments='{"timezone":"UTC"}',
                    )
                ]
            ),
        )

    port.client = MagicMock()
    port.client.responses = MagicMock()
    port.client.responses.create = AsyncMock(return_value=events())
    messages = [
        ChatMessage(role="user", content="What time is it?"),
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id="previous", name=tool.name, arguments={})],
        ),
        ChatMessage(
            role="tool",
            content='{"time":"10:00"}',
            tool_call_id="previous",
            name=tool.name,
        ),
    ]

    chunks = [
        chunk
        async for chunk in port.stream_chat(
            messages,
            model="gpt-5.5",
            tools=[tool],
            tool_choice="auto",
        )
    ]

    params = port.client.responses.create.call_args.kwargs
    assert params["input"][1] == {
        "type": "function_call",
        "call_id": "previous",
        "name": safe_name,
        "arguments": "{}",
    }
    assert params["input"][2] == {
        "type": "function_call_output",
        "call_id": "previous",
        "output": '{"time":"10:00"}',
    }
    assert chunks[0].tool_call_deltas is not None
    assert chunks[0].tool_call_deltas[0].id == "call_stream"
    assert chunks[0].tool_call_deltas[0].name == tool.name
    assert chunks[1].tool_call_deltas[0].arguments_delta == '{"timezone":'
    assert chunks[2].tool_call_deltas[0].arguments_delta == '"UTC"}'
    assert chunks[-1].tool_calls is not None
    assert chunks[-1].tool_calls[0].arguments == {"timezone": "UTC"}
