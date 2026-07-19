from ag_ui.core import RunAgentInput

from app.adapters.agui.responses import (
    AgUiInteractionProtocolAdapter,
    AgUiResponseRequestAdapter,
)


def test_direct_request_preserves_provider_routing_hint() -> None:
    run_input = RunAgentInput.model_validate(
        {
            "threadId": "thread-1",
            "runId": "interaction-1",
            "messages": [
                {
                    "id": "message-1",
                    "role": "user",
                    "content": "hello",
                }
            ],
            "state": {},
            "tools": [],
            "context": [],
            "forwardedProps": {
                "soit": {
                    "mode": "direct",
                    "modelRef": "gpt-5.1",
                    "provider": "openai-main",
                }
            },
        }
    )

    request = AgUiResponseRequestAdapter().to_internal(run_input)

    assert request.model == "gpt-5.1"
    assert request.provider == "openai-main"


def test_direct_request_maps_hosted_tool_toggles_to_responses_tools() -> None:
    run_input = RunAgentInput.model_validate(
        {
            "threadId": "thread-1",
            "runId": "interaction-hosted-tools",
            "messages": [
                {"id": "message-1", "role": "user", "content": "Research and chart"}
            ],
            "state": {},
            "tools": [],
            "context": [],
            "forwardedProps": {
                "soit": {
                    "mode": "direct",
                    "modelRef": "gpt-5.5",
                    "webSearch": True,
                    "codeInterpreter": True,
                }
            },
        }
    )

    request = AgUiResponseRequestAdapter().to_internal(run_input)

    assert request.tools == [
        {"type": "web_search"},
        {
            "type": "code_interpreter",
            "container": {"type": "auto", "memory_limit": "4g"},
        },
    ]


def test_new_turn_uses_assistant_parent_when_tool_result_follows_it() -> None:
    run_input = RunAgentInput.model_validate(
        {
            "threadId": "thread-1",
            "runId": "interaction-2",
            "messages": [
                {
                    "id": "user-1",
                    "role": "user",
                    "content": "use the time tool",
                },
                {
                    "id": "assistant-1",
                    "role": "assistant",
                    "content": "The time is available.",
                    "toolCalls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "tool:function:time_now",
                                "arguments": "{}",
                            },
                        }
                    ],
                },
                {
                    "id": "call-1:tool",
                    "role": "tool",
                    "content": '{"result":{"iso":"2026-07-16T15:41:07+00:00"}}',
                    "toolCallId": "call-1",
                },
                {
                    "id": "user-2",
                    "role": "user",
                    "content": "repeat the prior result",
                },
            ],
            "state": {},
            "tools": [],
            "context": [],
            "forwardedProps": {
                "soit": {
                    "mode": "agent",
                    "agentId": "agent-1",
                }
            },
        }
    )

    adapter = AgUiResponseRequestAdapter()
    request = adapter.to_internal(run_input)
    agent_inputs = adapter.to_agent_inputs(run_input)

    assert request.metadata["parent_message_id"] == "assistant-1"
    assert agent_inputs["_agui_context"]["parent_message_id"] == "assistant-1"


def test_reasoning_options_are_propagated_to_direct_and_agent_execution() -> None:
    direct_input = RunAgentInput.model_validate(
        {
            "threadId": "thread-1",
            "runId": "interaction-direct",
            "messages": [{"id": "user-1", "role": "user", "content": "Think"}],
            "state": {},
            "tools": [],
            "context": [],
            "forwardedProps": {
                "soit": {
                    "mode": "direct",
                    "modelRef": "gpt-5.1",
                    "deepThinking": True,
                    "reasoningEffort": "high",
                }
            },
        }
    )
    agent_input = RunAgentInput.model_validate(
        {
            "threadId": "thread-1",
            "runId": "interaction-agent",
            "messages": [{"id": "user-2", "role": "user", "content": "Think"}],
            "state": {},
            "tools": [],
            "context": [],
            "forwardedProps": {
                "soit": {
                    "mode": "agent",
                    "agentId": "agent-1",
                    "deepThinking": True,
                    "reasoningEffort": "high",
                }
            },
        }
    )

    adapter = AgUiResponseRequestAdapter()
    direct_request = adapter.to_internal(direct_input)
    agent_inputs = adapter.to_agent_inputs(agent_input)

    assert direct_request.metadata["deep_thinking"] is True
    assert direct_request.metadata["show_reasoning"] is True
    assert direct_request.metadata["reasoning_effort"] == "high"
    assert agent_inputs["_agui_options"] == {
        "show_reasoning": True,
        "reasoning_effort": "high",
    }


def test_agui_protocol_builds_reasoning_message_lifecycle() -> None:
    protocol = AgUiInteractionProtocolAdapter()

    started = protocol.reasoning_started(message_id="reasoning-1")
    content = protocol.reasoning_content(message_id="reasoning-1", delta="Checking.")
    ended = protocol.reasoning_ended(message_id="reasoning-1")

    assert [event.type for event in started] == [
        "REASONING_START",
        "REASONING_MESSAGE_START",
    ]
    assert content.type == "REASONING_MESSAGE_CONTENT"
    assert content.payload["delta"] == "Checking."
    assert [event.type for event in ended] == [
        "REASONING_MESSAGE_END",
        "REASONING_END",
    ]
