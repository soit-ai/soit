"""Tests for the additive LiteLLM SDK port."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import ChatMessage, ToolDefinition


@pytest.mark.asyncio
async def test_litellm_chat_maps_provider_model_tools_and_usage():
    from app.adapters.llm.litellm import LiteLLMPort

    completion = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call_1",
                                function=SimpleNamespace(
                                    name="lookup", arguments=json.dumps({"id": 7})
                                ),
                            )
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=5),
            model="gpt-4.1-mini",
        )
    )
    port = LiteLLMPort(
        provider_kind="openai_compatible",
        api_key="secret-value",
        api_base="https://llm.example.com/v1",
        timeout=17.0,
        max_retries=2,
        completion_fn=completion,
        embedding_fn=AsyncMock(),
    )

    response = await port.chat(
        [ChatMessage(role="user", content="Find it")],
        model="model:workspace-gateway:gpt-4.1-mini",
        tools=[ToolDefinition(name="lookup", description="Lookup", parameters={"type": "object"})],
        tool_choice="auto",
    )

    assert response.text is None
    assert response.tokens_prompt == 11
    assert response.tokens_completion == 5
    assert response.tool_calls is not None
    assert response.tool_calls[0].arguments == {"id": 7}
    assert completion.await_args is not None
    kwargs = completion.await_args.kwargs
    assert kwargs["model"] == "openai/gpt-4.1-mini"
    assert kwargs["api_key"] == "secret-value"
    assert kwargs["api_base"] == "https://llm.example.com/v1"
    assert kwargs["timeout"] == 17.0
    assert kwargs["num_retries"] == 0
    assert kwargs["tools"][0]["function"]["name"] == "lookup"


@pytest.mark.asyncio
async def test_litellm_embedding_maps_gemini_model_and_usage():
    from app.adapters.llm.litellm import LiteLLMPort

    embedding = AsyncMock(
        return_value=SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2])],
            usage=SimpleNamespace(total_tokens=3),
            model="text-embedding-004",
        )
    )
    port = LiteLLMPort(
        provider_kind="gemini",
        api_key="secret-value",
        embedding_fn=embedding,
        completion_fn=AsyncMock(),
    )

    response = await port.embed(["hello"], model="model:gemini-team:text-embedding-004")

    assert response.embeddings == [[0.1, 0.2]]
    assert response.tokens_used == 3
    assert embedding.await_args is not None
    assert embedding.await_args.kwargs["model"] == "gemini/text-embedding-004"


@pytest.mark.asyncio
async def test_litellm_rerank_fails_explicitly_when_sdk_capability_is_missing():
    from app.adapters.llm.litellm import LiteLLMPort

    port = LiteLLMPort(
        provider_kind="anthropic",
        api_key="secret-value",
        completion_fn=AsyncMock(),
        embedding_fn=AsyncMock(),
        rerank_fn=None,
        load_sdk_defaults=False,
    )

    with pytest.raises(ValidationError, match="LiteLLM rerank capability is unavailable"):
        await port.rerank("query", ["document"], model="model:team:rerank-model")


@pytest.mark.asyncio
async def test_litellm_stream_maps_tools_and_assembles_tool_calls():
    from app.adapters.llm.litellm import LiteLLMPort

    async def events():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id="call_1",
                                function=SimpleNamespace(name="lookup", arguments='{"id"'),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
            model="gpt-test",
        )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id=None,
                                function=SimpleNamespace(name=None, arguments=":7}"),
                            )
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=None,
            model="gpt-test",
        )
        yield SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(prompt_tokens=8, completion_tokens=4),
            model="gpt-test",
        )

    completion = AsyncMock(return_value=events())
    port = LiteLLMPort(
        provider_kind="openai_compatible",
        completion_fn=completion,
        embedding_fn=AsyncMock(),
    )
    tools = [ToolDefinition(name="lookup", description="Lookup", parameters={"type": "object"})]

    chunks = [
        chunk
        async for chunk in port.stream_chat(
            [ChatMessage(role="user", content="Find it")],
            model="model:workspace-gateway:gpt-test",
            tools=tools,
            tool_choice="auto",
        )
    ]

    assert completion.await_args is not None
    assert completion.await_args.kwargs["tools"][0]["function"]["name"] == "lookup"
    assert completion.await_args.kwargs["tool_choice"] == "auto"
    assert chunks[0].tool_call_deltas is not None
    assert chunks[0].tool_call_deltas[0].index == 0
    assert chunks[0].tool_call_deltas[0].id == "call_1"
    assert chunks[0].tool_call_deltas[0].arguments_delta == '{"id"'
    assert chunks[1].finish_reason == "tool_calls"
    assert chunks[1].tool_calls is not None
    assert chunks[1].tool_calls[0].id == "call_1"
    assert chunks[1].tool_calls[0].name == "lookup"
    assert chunks[1].tool_calls[0].arguments == {"id": 7}
    assert chunks[2].tokens_prompt == 8
    assert chunks[2].tokens_completion == 4


@pytest.mark.asyncio
async def test_litellm_chat_rejects_invalid_tool_arguments_json():
    from app.adapters.llm.litellm import LiteLLMPort

    completion = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call_1",
                                function=SimpleNamespace(name="lookup", arguments="{invalid"),
                            )
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=None,
            model="gpt-test",
        )
    )
    port = LiteLLMPort(
        provider_kind="openai_compatible",
        completion_fn=completion,
        embedding_fn=AsyncMock(),
    )

    with pytest.raises(ValidationError, match="invalid tool arguments"):
        await port.chat(
            [ChatMessage(role="user", content="Find it")],
            model="model:workspace-gateway:gpt-test",
        )


@pytest.mark.asyncio
async def test_litellm_port_supports_generic_provider_prefix_and_extra_params():
    from app.adapters.llm.litellm import LiteLLMPort

    completion = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="ok", tool_calls=None),
                    finish_reason="stop",
                )
            ],
            usage=None,
            model="upstream-model",
        )
    )
    port = LiteLLMPort(
        provider_kind="company_gateway",
        litellm_provider="openrouter",
        litellm_params={"organization": "org-1"},
        api_key="secret-value",
        completion_fn=completion,
        embedding_fn=AsyncMock(),
    )

    await port.chat(
        [ChatMessage(role="user", content="hello")],
        model="model:company:gpt-test",
    )

    assert completion.await_args is not None
    assert completion.await_args.kwargs["model"] == "openrouter/gpt-test"
    assert completion.await_args.kwargs["organization"] == "org-1"
