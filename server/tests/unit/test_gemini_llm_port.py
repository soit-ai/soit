"""Native Gemini adapter: chat, tools with thought signatures, streams and embeddings."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.adapters.llm import gemini
from app.adapters.llm.gemini import REPLAYED_SIGNATURE, GeminiLLMPort
from app.adapters.llm.router import RuntimeProviderConfig, _default_native_factory
from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.ports.llm.interface import (
    ChatImage,
    ChatMessage,
    ToolCall,
    ToolDefinition,
)

MODEL = "model:gemini:gemini-2.5-flash"
SEARCH = ToolDefinition(
    name="tool:plugin:search",
    description="Search the knowledge base",
    parameters={"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
)


class _Wire:
    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0)

    @property
    def body(self) -> dict[str, Any]:
        return json.loads(self.requests[-1].content)


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch):
    def install(*responses: httpx.Response) -> _Wire:
        recorder = _Wire(*responses)
        real = httpx.AsyncClient

        class Client(real):  # type: ignore[misc, valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, transport=httpx.MockTransport(recorder.handler), **kwargs)

        monkeypatch.setattr(gemini.httpx, "AsyncClient", Client)
        return recorder

    monkeypatch.setattr(gemini, "_signatures", gemini.OrderedDict())
    return install


def _answer(parts: list[dict[str, Any]], *, finish: str = "STOP", **usage: int) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": finish}],
            "usageMetadata": usage or {"promptTokenCount": 10, "candidatesTokenCount": 5},
            "modelVersion": "gemini-2.5-flash-001",
        },
    )


@pytest.mark.asyncio
async def test_a_chat_is_one_generate_content_call(wire) -> None:
    recorder = wire(_answer([{"text": "Paris."}], promptTokenCount=12, candidatesTokenCount=3, thoughtsTokenCount=40))

    response = await GeminiLLMPort(api_key="gk").chat(
        [ChatMessage(role="system", content="Be brief."), ChatMessage(role="user", content="Capital of France?")],
        MODEL,
        temperature=0.2,
        max_tokens=64,
        stop="END",
        top_p=0.9,
        seed=7,
    )

    request = recorder.requests[0]
    assert str(request.url) == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    )
    assert request.headers["x-goog-api-key"] == "gk"
    body = recorder.body
    assert body["systemInstruction"] == {"parts": [{"text": "Be brief."}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": "Capital of France?"}]}]
    assert body["generationConfig"] == {
        "temperature": 0.2,
        "maxOutputTokens": 64,
        "topP": 0.9,
        "seed": 7,
        "stopSequences": ["END"],
    }
    assert (response.text, response.finish_reason, response.model) == ("Paris.", "stop", "gemini-2.5-flash-001")
    # Thinking is output the call is charged for.
    assert (response.tokens_prompt, response.tokens_completion) == (12, 43)


@pytest.mark.asyncio
async def test_structured_output_sends_the_json_schema_as_it_is(wire) -> None:
    recorder = wire(_answer([{"text": "{\"city\": \"Paris\"}"}]))
    schema = {"type": "object", "properties": {"city": {"type": "string"}}, "additionalProperties": False}

    await GeminiLLMPort(api_key="gk").chat(
        [ChatMessage(role="user", content="x")],
        MODEL,
        response_format={"type": "json_schema", "json_schema": {"name": "city", "schema": schema}},
    )

    config = recorder.body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseJsonSchema"] == schema


@pytest.mark.asyncio
async def test_a_tool_call_comes_back_under_its_soit_name_and_its_signature_is_returned(wire) -> None:
    port = GeminiLLMPort(api_key="gk")
    alias = port._name_maps([SEARCH])[0][SEARCH.name]
    recorder = wire(
        _answer(
            [{"functionCall": {"id": "fc_1", "name": alias, "args": {"q": "refunds"}}, "thoughtSignature": "sig-abc"}]
        ),
        _answer([{"text": "Refunds take 5 days."}]),
    )

    first = await port.chat([ChatMessage(role="user", content="Refund policy?")], MODEL, tools=[SEARCH], tool_choice="required")

    declared = recorder.body["tools"][0]["functionDeclarations"][0]
    assert declared["name"] == alias
    assert declared["parametersJsonSchema"] == SEARCH.parameters
    assert recorder.body["toolConfig"] == {"functionCallingConfig": {"mode": "ANY"}}
    assert first.finish_reason == "tool_calls"
    (call,) = first.tool_calls or []
    assert (call.id, call.name, call.arguments) == ("fc_1", SEARCH.name, {"q": "refunds"})

    await port.chat(
        [
            ChatMessage(role="user", content="Refund policy?"),
            ChatMessage(role="assistant", content=None, tool_calls=[call]),
            ChatMessage(role="tool", content=json.dumps({"hits": ["5 days"]}), tool_call_id="fc_1"),
        ],
        MODEL,
        tools=[SEARCH],
    )

    model_turn, result_turn = recorder.body["contents"][1:]
    assert model_turn["role"] == "model"
    assert model_turn["parts"][0]["functionCall"] == {"id": "fc_1", "name": alias, "args": {"q": "refunds"}}
    assert model_turn["parts"][0]["thoughtSignature"] == "sig-abc"
    assert result_turn == {
        "role": "user",
        "parts": [{"functionResponse": {"name": alias, "response": {"hits": ["5 days"]}, "id": "fc_1"}}],
    }


@pytest.mark.asyncio
async def test_calls_from_elsewhere_are_replayed_with_the_documented_placeholder(wire) -> None:
    recorder = wire(_answer([{"text": "done"}]))

    await GeminiLLMPort(api_key="gk").chat(
        [
            ChatMessage(role="user", content="go"),
            ChatMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(id="a", name=SEARCH.name, arguments={"q": "x"}),
                    ToolCall(id="b", name=SEARCH.name, arguments={"q": "y"}),
                ],
            ),
            ChatMessage(role="tool", content="plain text result", tool_call_id="a"),
            ChatMessage(role="tool", content="second", tool_call_id="b"),
        ],
        MODEL,
        tools=[SEARCH],
    )

    model_turn, results = recorder.body["contents"][1:]
    assert [part["thoughtSignature"] for part in model_turn["parts"]] == [REPLAYED_SIGNATURE] * 2
    # Parallel results travel in one turn; a non-JSON result is wrapped.
    assert [part["functionResponse"]["response"] for part in results["parts"]] == [
        {"content": "plain text result"},
        {"content": "second"},
    ]


@pytest.mark.parametrize(
    "choice, config",
    [
        ("auto", {"mode": "AUTO"}),
        ("none", {"mode": "NONE"}),
        ({"type": "function", "function": {"name": SEARCH.name}}, {"mode": "ANY", "allowedFunctionNames": ["ALIAS"]}),
    ],
)
@pytest.mark.asyncio
async def test_tool_choice_maps_to_function_calling_config(wire, choice: Any, config: dict[str, Any]) -> None:
    port = GeminiLLMPort(api_key="gk")
    recorder = wire(_answer([{"text": "ok"}]))
    alias = port._name_maps([SEARCH])[0][SEARCH.name]

    await port.chat([ChatMessage(role="user", content="x")], MODEL, tools=[SEARCH], tool_choice=choice)

    expected = {**config, **({"allowedFunctionNames": [alias]} if "allowedFunctionNames" in config else {})}
    assert recorder.body["toolConfig"] == {"functionCallingConfig": expected}


@pytest.mark.asyncio
async def test_images_go_inline_and_a_web_address_is_refused(wire) -> None:
    recorder = wire(_answer([{"text": "a cat"}]))
    port = GeminiLLMPort(api_key="gk")

    await port.chat(
        [ChatMessage(role="user", content="What is this?", images=[ChatImage(url="data:image/png;base64,iVBORw0K")])],
        MODEL,
    )
    assert recorder.body["contents"][0]["parts"][1] == {"inlineData": {"mimeType": "image/png", "data": "iVBORw0K"}}

    with pytest.raises(ValidationError, match="inline"):
        await port.chat(
            [ChatMessage(role="user", content="x", images=[ChatImage(url="https://example.com/cat.png")])], MODEL
        )


@pytest.mark.asyncio
async def test_a_blocked_prompt_finishes_as_filtered(wire) -> None:
    wire(httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}, "usageMetadata": {"promptTokenCount": 4}}))

    response = await GeminiLLMPort(api_key="gk").chat([ChatMessage(role="user", content="x")], MODEL)

    assert (response.text, response.finish_reason, response.tokens_prompt) == ("", "content_filter", 4)


@pytest.mark.asyncio
async def test_a_provider_error_is_raised_as_an_http_status_error(wire) -> None:
    wire(httpx.Response(429, json={"error": {"code": 429, "message": "quota"}}))

    with pytest.raises(httpx.HTTPStatusError) as raised:
        await GeminiLLMPort(api_key="gk").chat([ChatMessage(role="user", content="x")], MODEL)
    assert raised.value.response.status_code == 429


def _sse(*chunks: dict[str, Any]) -> httpx.Response:
    body = "".join(f"data: {json.dumps(chunk)}\r\n\r\n" for chunk in chunks)
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())


@pytest.mark.asyncio
async def test_a_stream_yields_text_and_whole_tool_calls_then_usage(wire) -> None:
    port = GeminiLLMPort(api_key="gk")
    alias = port._name_maps([SEARCH])[0][SEARCH.name]
    recorder = wire(
        _sse(
            {"candidates": [{"content": {"parts": [{"text": "Let me "}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "check."}]}}]},
            {
                "candidates": [
                    {
                        "content": {"parts": [{"functionCall": {"name": alias, "args": {"q": "refunds"}}}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 9},
            },
        )
    )

    chunks = [chunk async for chunk in port.stream_chat([ChatMessage(role="user", content="x")], MODEL, tools=[SEARCH])]

    request = recorder.requests[0]
    assert request.url.path.endswith("/models/gemini-2.5-flash:streamGenerateContent")
    assert request.url.params["alt"] == "sse"
    assert "".join(chunk.delta for chunk in chunks) == "Let me check."
    (delta,) = [d for chunk in chunks for d in chunk.tool_call_deltas or []]
    assert (delta.index, delta.name, json.loads(delta.arguments_delta)) == (0, SEARCH.name, {"q": "refunds"})
    assert delta.id and delta.id.startswith("call_")
    final = chunks[-1]
    assert final.done
    assert (final.tokens_prompt, final.tokens_completion, final.finish_reason) == (20, 9, "tool_calls")
    assert [call.name for call in final.tool_calls or []] == [SEARCH.name]


@pytest.mark.asyncio
async def test_embeddings_are_one_batch_call(wire) -> None:
    recorder = wire(httpx.Response(200, json={"embeddings": [{"values": [0.1, 0.2]}, {"values": [0.3, 0.4]}]}))

    response = await GeminiLLMPort(api_key="gk").embed(
        ["hello", "a longer text"], "model:gemini:gemini-embedding-001", dimensions=2
    )

    assert recorder.requests[0].url.path.endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert recorder.body["requests"][0] == {
        "model": "models/gemini-embedding-001",
        "outputDimensionality": 2,
        "content": {"parts": [{"text": "hello"}]},
    }
    assert response.embeddings == [[0.1, 0.2], [0.3, 0.4]]
    # No count comes back: four characters a token, rounded up per text.
    assert response.tokens_used == 2 + 4


def test_a_base_url_with_its_api_version_is_kept() -> None:
    assert GeminiLLMPort(api_key="k", base_url="https://proxy.example/v1beta/").base_url == "https://proxy.example/v1beta"
    assert GeminiLLMPort(api_key="k", base_url="https://proxy.example").base_url == "https://proxy.example/v1beta"


def _config(**overrides: Any) -> RuntimeProviderConfig:
    values: dict[str, Any] = {
        "provider_id": "prov_gemini",
        "slug": "gemini",
        "kind": "gemini",
        "adapter_backend": "native",
        "status": "active",
        "provider_model_id": "gemini-2.5-flash",
        "model_id": "gemini-2.5-flash",
        "model_status": "active",
        "capability_matrix": {},
        "pricing": {},
    }
    values.update(overrides)
    return RuntimeProviderConfig(**values)


def test_the_router_builds_the_native_adapter_for_gemini() -> None:
    port = _default_native_factory(_config(), {"api_key": "gk"})
    assert isinstance(port, GeminiLLMPort)
    assert port.egress_base_url == "https://generativelanguage.googleapis.com"

    with pytest.raises(KernelError) as missing:
        _default_native_factory(_config(), {})
    assert missing.value.code == "MODEL_PROVIDER_CREDENTIAL_REQUIRED"
