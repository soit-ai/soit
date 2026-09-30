"""The Anthropic-compatible gateway answers Anthropic SDKs and governs every call."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlmodel import select

from app.kernel.commons.errors import RateLimitExceededError
from app.kernel.ports.llm.interface import ChatStreamChunk, ToolCallDelta
from app.kernel.runtime.db.models.runs import Run, RunStep
from app.wiring import get_container

MODEL = "model:test:chat"
LOOKUP = {
    "name": "lookup_order",
    "description": "Find an order",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}


def _events(body: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse an SSE body into (event name, data) pairs."""

    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        assert lines[0].startswith("event: "), block
        assert lines[1].startswith("data: "), block
        events.append((lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))))
    return events


class _ScriptedStreamPort:
    """A model whose stream is scripted: chunks, then optionally a failure."""

    def __init__(self, chunks: list[ChatStreamChunk], error: Exception | None = None) -> None:
        self.chunks = chunks
        self.error = error

    async def stream_chat(self, *args: Any, **kwargs: Any) -> AsyncIterator[ChatStreamChunk]:
        del args, kwargs
        for chunk in self.chunks:
            yield chunk
        if self.error is not None:
            raise self.error


class _SwapLLMPort:
    def __init__(self, port: Any) -> None:
        self.port = port

    def __enter__(self) -> None:
        container = get_container()
        self.original = container.get("llm_port")
        container.register_singleton("llm_port", self.port)

    def __exit__(self, *exc: object) -> None:
        get_container().register_singleton("llm_port", self.original)


async def _run(async_db, run_id: str) -> tuple[Run, list[RunStep]]:
    run = await async_db.get(Run, run_id)
    assert run is not None
    await async_db.refresh(run)
    steps = list((await async_db.exec(select(RunStep).where(RunStep.run_id == run_id))).all())
    return run, steps


@pytest.mark.asyncio
async def test_a_message_answers_in_the_anthropic_shape(async_client, async_db, ctx) -> None:
    response = await async_client.post(
        "/v1/messages",
        json={
            "model": MODEL,
            "max_tokens": 256,
            "system": "Be brief.",
            "messages": [{"role": "user", "content": "hello gateway"}],
            "temperature": 0.2,
            "top_k": 5,
            "metadata": {"user_id": "u1"},
            "some_future_field": True,
        },
        headers={"anthropic-version": "2023-06-01"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "success" not in body
    run_id = response.headers["x-soit-run-id"]
    assert body["id"] == f"msg_{run_id}"
    assert (body["type"], body["role"], body["model"]) == ("message", "assistant", MODEL)
    assert body["content"] == [{"type": "text", "text": "hello gateway"}]
    assert (body["stop_reason"], body["stop_sequence"]) == ("end_turn", None)
    assert set(body["usage"]) == {"input_tokens", "output_tokens"}

    run, steps = await _run(async_db, run_id)
    assert (run.mode, run.kind, run.status, run.source) == ("gateway", "chat", "succeeded", "gateway")
    assert (run.subject_kind, run.subject_id) == ("user", ctx.user_id)
    assert [step.step_type for step in steps] == ["llm"]


@pytest.mark.asyncio
async def test_tool_use_comes_back_as_a_tool_use_block(async_client) -> None:
    response = await async_client.post(
        "/v1/messages",
        json={
            "model": MODEL,
            "max_tokens": 256,
            "messages": [{"role": "user", "content": "find order 42"}],
            "tools": [LOOKUP],
            "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stop_reason"] == "tool_use"
    block = body["content"][-1]
    assert block["type"] == "tool_use"
    assert block["name"] == "lookup_order"
    assert block["input"] == {"query": "find order 42"}


@pytest.mark.asyncio
async def test_a_tool_result_turn_is_accepted(async_client) -> None:
    response = await async_client.post(
        "/v1/messages",
        json={
            "model": MODEL,
            "max_tokens": 256,
            "messages": [
                {"role": "user", "content": "find order 42"},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "id": "toolu_1", "name": "lookup_order", "input": {"query": "42"}}
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "order 42 shipped"}
                    ],
                },
            ],
            "tools": [LOOKUP],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["type"] == "message"


@pytest.mark.asyncio
async def test_a_stream_uses_anthropics_named_events(async_client, async_db) -> None:
    response = await async_client.post(
        "/v1/messages",
        json={
            "model": MODEL,
            "max_tokens": 256,
            "stream": True,
            "messages": [{"role": "user", "content": "stream this please"}],
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.text)
    names = [name for name, _ in events]
    assert names[0] == "message_start"
    assert names[1] == "ping"
    assert names[-1] == "message_stop"
    assert names[-2] == "message_delta"
    assert "content_block_start" in names and "content_block_stop" in names
    text = "".join(
        data["delta"]["text"] for name, data in events if name == "content_block_delta"
    )
    assert text == "stream this please"
    start = events[0][1]["message"]
    assert start["id"] == f"msg_{response.headers['x-soit-run-id']}"
    assert start["content"] == [] and start["stop_reason"] is None
    delta = dict(events)["message_delta"]
    assert delta["delta"]["stop_reason"] == "end_turn"
    assert delta["usage"]["output_tokens"] >= 1

    run, _ = await _run(async_db, response.headers["x-soit-run-id"])
    assert run.status == "succeeded"


@pytest.mark.asyncio
async def test_streamed_tool_calls_open_tool_use_blocks_in_order(async_client) -> None:
    port = _ScriptedStreamPort(
        [
            ChatStreamChunk(delta="Looking."),
            ChatStreamChunk(
                tool_call_deltas=[ToolCallDelta(index=0, id="call_1", name="lookup_order", arguments_delta="")]
            ),
            ChatStreamChunk(tool_call_deltas=[ToolCallDelta(index=0, arguments_delta='{"query":')]),
            ChatStreamChunk(tool_call_deltas=[ToolCallDelta(index=0, arguments_delta=' "42"}')]),
            ChatStreamChunk(
                tool_call_deltas=[ToolCallDelta(index=1, id="call_2", name="lookup_order", arguments_delta="{}")]
            ),
            ChatStreamChunk(done=True, tokens_prompt=11, tokens_completion=7, finish_reason="tool_calls"),
        ]
    )
    with _SwapLLMPort(port):
        response = await async_client.post(
            "/v1/messages",
            json={
                "model": MODEL,
                "max_tokens": 64,
                "stream": True,
                "messages": [{"role": "user", "content": "go"}],
                "tools": [LOOKUP],
            },
        )

    assert response.status_code == 200, response.text
    events = _events(response.text)
    # Blocks open one at a time, each closed before the next starts. The
    # gateway's outbound safety check may hold text back behind tool calls, so
    # the order of block kinds is not asserted, only that every one arrives whole.
    open_index: int | None = None
    blocks: dict[int, dict[str, Any]] = {}
    for name, data in events:
        if name == "content_block_start":
            assert open_index is None
            assert data["index"] == len(blocks)
            open_index = data["index"]
            blocks[open_index] = {"block": data["content_block"], "delta": ""}
        elif name == "content_block_delta":
            assert open_index == data["index"]
            delta = data["delta"]
            blocks[open_index]["delta"] += delta.get("text") or delta.get("partial_json")
        elif name == "content_block_stop":
            assert open_index == data["index"]
            open_index = None
    assert open_index is None
    tools = [b for b in blocks.values() if b["block"]["type"] == "tool_use"]
    texts = [b for b in blocks.values() if b["block"]["type"] == "text"]
    assert [(b["block"]["id"], b["block"]["name"]) for b in tools] == [
        ("call_1", "lookup_order"),
        ("call_2", "lookup_order"),
    ]
    assert json.loads(tools[0]["delta"]) == {"query": "42"}
    assert json.loads(tools[1]["delta"]) == {}
    assert [b["delta"] for b in texts] == ["Looking."]
    final = dict(events)["message_delta"]
    assert final["delta"]["stop_reason"] == "tool_use"
    assert final["usage"] == {"input_tokens": 11, "output_tokens": 7}


@pytest.mark.asyncio
async def test_a_failure_after_the_stream_starts_is_an_error_event(async_client, async_db) -> None:
    port = _ScriptedStreamPort(
        [ChatStreamChunk(delta="First sentence.\n")], error=RuntimeError("secret provider detail")
    )
    with _SwapLLMPort(port):
        response = await async_client.post(
            "/v1/messages",
            json={
                "model": MODEL,
                "max_tokens": 64,
                "stream": True,
                "messages": [{"role": "user", "content": "go"}],
            },
        )

    assert response.status_code == 200
    events = _events(response.text)
    assert events[-1][0] == "error"
    assert events[-1][1] == {
        "type": "error",
        "error": {"type": "api_error", "message": "The model call failed"},
    }
    assert "secret provider detail" not in response.text
    assert "message_stop" not in [name for name, _ in events]
    run, _ = await _run(async_db, response.headers["x-soit-run-id"])
    assert run.status == "failed"


@pytest.mark.asyncio
async def test_a_refusal_before_the_stream_answers_with_its_own_status(async_client, async_db) -> None:
    port = _ScriptedStreamPort([], error=RateLimitExceededError("Too many calls", {"retry_after": 7}))
    with _SwapLLMPort(port):
        response = await async_client.post(
            "/v1/messages",
            json={
                "model": MODEL,
                "max_tokens": 64,
                "stream": True,
                "messages": [{"role": "user", "content": "go"}],
            },
        )

    assert response.status_code == 429
    assert response.json() == {
        "type": "error",
        "error": {"type": "rate_limit_error", "message": "Too many calls"},
    }
    assert response.headers["retry-after"] == "7"
    runs = list((await async_db.exec(select(Run).where(Run.mode == "gateway"))).all())
    assert len(runs) == 1
    await async_db.refresh(runs[0])
    assert (runs[0].status, runs[0].error_code) == ("failed", "RATE_LIMIT_EXCEEDED")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "status", "error_type"),
    [
        ({"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}, 400, "invalid_request_error"),
        (
            {
                "model": MODEL,
                "max_tokens": 8,
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [{"name": "search", "type": "web_search_20250305"}],
            },
            400,
            "invalid_request_error",
        ),
        (
            {
                "model": MODEL,
                "max_tokens": 8,
                "messages": [{"role": "user", "content": [{"type": "document", "source": {}}]}],
            },
            400,
            "invalid_request_error",
        ),
    ],
)
async def test_refusals_use_anthropics_error_body(async_client, payload, status, error_type) -> None:
    response = await async_client.post("/v1/messages", json=payload)

    assert response.status_code == status
    body = response.json()
    assert body["type"] == "error"
    assert body["error"]["type"] == error_type
    assert body["error"]["message"]
    assert "success" not in body and "code" not in body


@pytest.mark.asyncio
async def test_an_unknown_messages_route_is_a_not_found_error(async_client) -> None:
    response = await async_client.get("/v1/messages/nothing")

    assert response.status_code in (404, 405)
    assert response.json()["type"] == "error"


@pytest.mark.asyncio
async def test_a_refused_request_opens_no_run(async_client, async_db) -> None:
    before = len((await async_db.exec(select(Run))).all())

    response = await async_client.post(
        "/v1/messages",
        json={
            "model": MODEL,
            "max_tokens": 8,
            "messages": [{"role": "user", "content": [{"type": "document", "source": {}}]}],
        },
    )

    assert response.status_code == 400
    assert len((await async_db.exec(select(Run))).all()) == before


@pytest.mark.asyncio
async def test_count_tokens_estimates_without_a_model_call(async_client, async_db) -> None:
    before = len((await async_db.exec(select(Run))).all())

    response = await async_client.post(
        "/v1/messages/count_tokens",
        json={
            "model": MODEL,
            "system": "Be brief.",
            "messages": [{"role": "user", "content": "how many tokens is this message"}],
            "tools": [LOOKUP],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["input_tokens"] > 10
    assert len((await async_db.exec(select(Run))).all()) == before
