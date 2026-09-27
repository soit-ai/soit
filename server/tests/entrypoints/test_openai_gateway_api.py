"""The OpenAI-compatible gateway answers OpenAI SDKs and governs every call."""

from __future__ import annotations

import array
import asyncio
import base64
import dataclasses
import io
import json
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest
from PIL import Image
from sqlmodel import select

from app.kernel.commons.errors import RateLimitExceededError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import (
    ChatStreamChunk,
    GeneratedImage,
    ImageGenerationResponse,
    ToolCallDelta,
)
from app.kernel.ports.llm.usage_estimate import estimate_text_tokens
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.runs.exporter import to_runtrace_spec
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.specs import validate_spec
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.modelhub.domain.models import Provider, ProviderModel
from app.wiring import get_container

MODEL = "model:test:chat"


def _events(body: str) -> list[Any]:
    """Parse an SSE body into its data payloads, ``[DONE]`` kept as text."""

    events: list[Any] = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        assert block.startswith("data: "), block
        data = block.removeprefix("data: ")
        events.append(data if data == "[DONE]" else json.loads(data))
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
async def test_chat_completion_answers_in_the_openai_shape(async_client, async_db, ctx) -> None:
    response = await async_client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [
                {"role": "developer", "content": "Be brief."},
                {"role": "user", "content": "hello gateway"},
            ],
            "temperature": 0.2,
            "seed": 7,
            "some_future_field": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "success" not in body
    assert body["object"] == "chat.completion"
    assert body["model"] == MODEL
    choice = body["choices"][0]
    assert choice["message"] == {"role": "assistant", "content": "hello gateway"}
    assert choice["finish_reason"] == "stop"
    usage = body["usage"]
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]

    run_id = response.headers["x-soit-run-id"]
    assert body["id"] == f"chatcmpl-{run_id}"
    run, steps = await _run(async_db, run_id)
    assert (run.mode, run.kind, run.status) == ("gateway", "chat", "succeeded")
    assert (run.subject_kind, run.subject_id) == ("user", ctx.user_id)
    assert [step.step_type for step in steps] == ["llm"]
    document = to_runtrace_spec(run, steps)
    assert validate_spec(document, "runtrace_spec") is True


@pytest.mark.asyncio
async def test_a_call_made_with_an_api_key_is_attributed_to_the_key(
    async_client, async_db, ctx: RequestContext
) -> None:
    keyed = dataclasses.replace(ctx, api_key_id="key_gateway")
    app.dependency_overrides[get_current_context] = lambda: keyed
    try:
        response = await async_client.post(
            "/v1/chat/completions",
            json={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
        )
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    assert response.status_code == 200
    run, _ = await _run(async_db, response.headers["x-soit-run-id"])
    assert (run.subject_kind, run.subject_id) == ("api_key", "key_gateway")
    assert (run.source, run.api_key_id) == ("gateway", "key_gateway")

    listed = await async_client.get(
        "/api/v1/runs", params={"source": "gateway", "api_key_id": "key_gateway"}
    )
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert [(item["id"], item["source"], item["api_key_id"]) for item in items] == [
        (run.id, "gateway", "key_gateway")
    ]


@pytest.mark.asyncio
async def test_tool_calls_come_back_as_openai_tool_calls(async_client) -> None:
    response = await async_client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "find order 42"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "lookup_order",
                        "description": "Find an order",
                        "parameters": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    },
                }
            ],
            "tool_choice": "auto",
        },
    )

    assert response.status_code == 200
    choice = response.json()["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["content"] is None
    call = choice["message"]["tool_calls"][0]
    assert call["type"] == "function"
    assert call["function"]["name"] == "lookup_order"
    assert json.loads(call["function"]["arguments"]) == {"query": "find order 42"}


@pytest.mark.asyncio
async def test_a_tool_result_turn_is_accepted(async_client) -> None:
    response = await async_client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [
                {"role": "user", "content": "find order 42"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "lookup_order", "arguments": '{"query": "42"}'},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "order 42 shipped"},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "order 42 shipped"


@pytest.mark.asyncio
async def test_a_stream_sends_chunks_then_usage_then_done(async_client, async_db) -> None:
    response = await async_client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "stream me"}],
            "stream": True,
            "stream_options": {"include_usage": True},
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    run_id = response.headers["x-soit-run-id"]
    events = _events(response.text)
    assert events[-1] == "[DONE]"
    chunks = events[:-1]
    assert all(chunk["object"] == "chat.completion.chunk" for chunk in chunks)
    assert all(chunk["id"] == f"chatcmpl-{run_id}" for chunk in chunks)
    assert chunks[0]["choices"][0]["delta"] == {"role": "assistant", "content": ""}
    text = "".join(
        chunk["choices"][0]["delta"].get("content") or ""
        for chunk in chunks
        if chunk["choices"]
    )
    assert text == "stream me"
    finishes = [chunk["choices"][0]["finish_reason"] for chunk in chunks if chunk["choices"]]
    assert finishes[-1] == "stop"
    usage_chunk = chunks[-1]
    assert usage_chunk["choices"] == []
    assert usage_chunk["usage"]["total_tokens"] >= 1

    run, steps = await _run(async_db, run_id)
    assert (run.mode, run.kind, run.status) == ("gateway", "chat", "succeeded")
    assert steps[0].status == "succeeded"


@pytest.mark.asyncio
async def test_a_stream_without_usage_option_sends_no_usage_chunk(async_client) -> None:
    response = await async_client.post(
        "/v1/chat/completions",
        json={"model": MODEL, "messages": [{"role": "user", "content": "x"}], "stream": True},
    )

    chunks = _events(response.text)[:-1]
    assert all("usage" not in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_streamed_tool_calls_arrive_as_deltas(async_client) -> None:
    port = _ScriptedStreamPort(
        [
            ChatStreamChunk(
                tool_call_deltas=[
                    ToolCallDelta(index=0, id="call_9", name="lookup_order", arguments_delta='{"query"')
                ]
            ),
            ChatStreamChunk(tool_call_deltas=[ToolCallDelta(index=0, arguments_delta=': "42"}')]),
            ChatStreamChunk(done=True, finish_reason="tool_calls", tokens_prompt=5, tokens_completion=3),
        ]
    )
    with _SwapLLMPort(port):
        response = await async_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "find order 42"}],
                "tools": [{"type": "function", "function": {"name": "lookup_order"}}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    chunks = _events(response.text)[:-1]
    deltas = [
        call
        for chunk in chunks
        if chunk["choices"]
        for call in chunk["choices"][0]["delta"].get("tool_calls") or []
    ]
    assert deltas[0] == {
        "index": 0,
        "id": "call_9",
        "type": "function",
        "function": {"name": "lookup_order", "arguments": '{"query"'},
    }
    assert "".join(delta["function"]["arguments"] for delta in deltas) == '{"query": "42"}'
    assert chunks[-1]["choices"][0]["finish_reason"] == "tool_calls"


@pytest.mark.asyncio
async def test_a_refusal_before_the_stream_answers_with_its_status(async_client, async_db) -> None:
    port = _ScriptedStreamPort(
        [],
        error=RateLimitExceededError("Rate limit exceeded", {"retry_after": 30}),
    )
    with _SwapLLMPort(port):
        response = await async_client.post(
            "/v1/chat/completions",
            json={"model": MODEL, "messages": [{"role": "user", "content": "x"}], "stream": True},
        )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"
    error = response.json()["error"]
    assert error["type"] == "rate_limit_error"
    assert error["code"] == "rate_limit_exceeded"

    runs = list((await async_db.exec(select(Run).where(Run.mode == "gateway"))).all())
    assert len(runs) == 1
    await async_db.refresh(runs[0])
    assert (runs[0].status, runs[0].error_code) == ("failed", "RATE_LIMIT_EXCEEDED")


@pytest.mark.asyncio
async def test_a_failure_mid_stream_ends_with_an_error_event(async_client, async_db) -> None:
    port = _ScriptedStreamPort(
        [ChatStreamChunk(delta="First sentence.\n")],
        error=RuntimeError("upstream exploded with secret detail"),
    )
    with _SwapLLMPort(port):
        response = await async_client.post(
            "/v1/chat/completions",
            json={"model": MODEL, "messages": [{"role": "user", "content": "x"}], "stream": True},
        )

    assert response.status_code == 200
    events = _events(response.text)
    assert events[-1] == "[DONE]"
    error = events[-2]["error"]
    assert error["type"] == "api_error"
    assert "secret detail" not in error["message"]

    run, _ = await _run(async_db, response.headers["x-soit-run-id"])
    assert (run.status, run.error_code) == ("failed", "GATEWAY_CHAT_ERROR")


PARTIAL_ANSWER = "Partial answer.\n"


class _StillGeneratingPort:
    """A model that sends one chunk and keeps generating until it is closed."""

    def __init__(self) -> None:
        self.closed = False

    async def stream_chat(self, *args: Any, **kwargs: Any) -> AsyncIterator[ChatStreamChunk]:
        del args, kwargs
        try:
            # A finished sentence, so outbound inspection releases it at once.
            yield ChatStreamChunk(delta=PARTIAL_ANSWER)
            await asyncio.Event().wait()
            yield ChatStreamChunk(delta="never sent", done=True, tokens_prompt=1, tokens_completion=1)
        finally:
            self.closed = True


async def _stream_then_disconnect(port: Any) -> str:
    """Stream a chat call at the ASGI level and disconnect after the first answer.

    At this level a disconnect is a message, as a server sends it; the
    response's own cleanup runs in the task that owns the request.
    """
    body = json.dumps(
        {"model": MODEL, "messages": [{"role": "user", "content": "hello"}], "stream": True}
    ).encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/v1/chat/completions",
        "raw_path": b"/v1/chat/completions",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    first_chunk_sent = asyncio.Event()
    request_read = False
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal request_read
        if not request_read:
            request_read = True
            return {"type": "http.request", "body": body, "more_body": False}
        await first_chunk_sent.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)
        if message["type"] == "http.response.body" and b"Partial answer." in message.get("body", b""):
            first_chunk_sent.set()

    with _SwapLLMPort(port):
        await asyncio.wait_for(app(scope, receive, send), timeout=30)
    start = next(message for message in sent if message["type"] == "http.response.start")
    return dict(start["headers"])[b"x-soit-run-id"].decode()


@pytest.mark.asyncio
async def test_a_client_that_disconnects_mid_stream_is_still_charged(async_client, async_db) -> None:
    del async_client  # Only for the dependency overrides it installs.
    port = _StillGeneratingPort()

    run_id = await _stream_then_disconnect(port)

    assert port.closed
    run, [step] = await _run(async_db, run_id)
    assert (run.status, run.error_code) == ("failed", "CLIENT_DISCONNECTED")
    await async_db.refresh(step)
    assert (step.status, step.error_code) == ("canceled", "STREAM_ABANDONED")
    assert step.metrics_json["usage_estimated"] is True
    [cost] = (await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run_id))).all()
    assert cost.step_id == step.id
    assert cost.completion_tokens == estimate_text_tokens(PARTIAL_ANSWER)
    assert cost.prompt_tokens and cost.prompt_tokens > 0
    assert cost.pricing_snapshot_json["usage_estimated"] is True


def _fail_ledger_flushes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every cost write fail at flush, leaving the transaction unusable."""

    async def record_cost(self: TraceWriter, **kwargs: Any) -> None:
        self.db.add(
            RunCostEntry(
                run_id=kwargs["run_id"],
                step_id=kwargs["step_id"],
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                billing_basis="tokens",
                billed_quantity=Decimal(1),
                # A priced row without a currency breaks a CHECK constraint.
                amount=Decimal(1),
                currency=None,
            )
        )
        await self.db.flush()

    monkeypatch.setattr(TraceWriter, "record_cost", record_cost)


@pytest.mark.asyncio
async def test_a_failed_ledger_write_still_closes_an_abandoned_run(
    async_client, async_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    del async_client
    _fail_ledger_flushes(monkeypatch)

    run_id = await _stream_then_disconnect(_StillGeneratingPort())

    run, _ = await _run(async_db, run_id)
    assert (run.status, run.error_code) == ("failed", "CLIENT_DISCONNECTED")


@pytest.mark.asyncio
async def test_a_failed_ledger_write_still_closes_a_failed_run(
    async_client, async_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fail_ledger_flushes(monkeypatch)
    port = _ScriptedStreamPort(
        [ChatStreamChunk(delta=PARTIAL_ANSWER)],
        error=RuntimeError("upstream dropped the stream"),
    )
    with _SwapLLMPort(port):
        response = await async_client.post(
            "/v1/chat/completions",
            json={"model": MODEL, "messages": [{"role": "user", "content": "x"}], "stream": True},
        )

    assert _events(response.text)[-1] == "[DONE]"
    run, _ = await _run(async_db, response.headers["x-soit-run-id"])
    assert (run.status, run.error_code) == ("failed", "GATEWAY_CHAT_ERROR")


@pytest.mark.asyncio
async def test_invalid_requests_answer_in_the_openai_shape(async_client) -> None:
    missing = await async_client.post("/v1/chat/completions", json={"model": MODEL})
    assert missing.status_code == 400
    assert missing.json()["error"]["param"] == "messages"

    several = await async_client.post(
        "/v1/chat/completions",
        json={"model": MODEL, "messages": [{"role": "user", "content": "x"}], "n": 2},
    )
    assert several.status_code == 400
    assert several.json()["error"]["type"] == "invalid_request_error"

    bad_arguments = await async_client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {"id": "c1", "function": {"name": "f", "arguments": "not json"}}
                    ],
                }
            ],
        },
    )
    assert bad_arguments.status_code == 400
    assert bad_arguments.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_models_lists_what_a_call_can_name(async_client, async_db, ctx) -> None:
    scope = {"tenant_id": ctx.tenant_id, "workspace_id": ctx.workspace_id}
    live = Provider(**scope, kind="openai", slug="openai-main", name="OpenAI main")
    off = Provider(**scope, kind="anthropic", slug="claude", name="Claude", status="disabled")
    async_db.add(live)
    async_db.add(off)
    for model_id, extra in (
        ("gpt-live", {}),
        ("gpt-disabled", {"status": "disabled"}),
        ("gpt-gone", {"sync_status": "platform_removed"}),
        ("gpt-dropped", {"sync_status": "user_removed"}),
    ):
        async_db.add(
            ProviderModel(
                **scope,
                provider_id=live.id,
                provider_kind="openai",
                model_id=model_id,
                **extra,
            )
        )
    async_db.add(
        ProviderModel(**scope, provider_id=off.id, provider_kind="anthropic", model_id="claude-x")
    )
    await async_db.commit()

    response = await async_client.get("/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert [model["id"] for model in body["data"]] == ["model:openai-main:gpt-live"]
    assert body["data"][0]["object"] == "model"
    assert body["data"][0]["owned_by"] == "openai-main"
    assert isinstance(body["data"][0]["created"], int)


@pytest.mark.asyncio
async def test_a_key_limited_to_some_models_sees_and_calls_only_those(
    async_client, async_db, ctx
) -> None:
    scope = {"tenant_id": ctx.tenant_id, "workspace_id": ctx.workspace_id}
    provider = Provider(**scope, kind="openai", slug="openai-main", name="OpenAI main")
    async_db.add(provider)
    for model_id in ("gpt-live", "gpt-other"):
        async_db.add(
            ProviderModel(**scope, provider_id=provider.id, provider_kind="openai", model_id=model_id)
        )
    await async_db.commit()
    keyed = dataclasses.replace(
        ctx, api_key_id="key_models", allowed_models=frozenset({"model:openai-main:gpt-live"})
    )
    app.dependency_overrides[get_current_context] = lambda: keyed
    try:
        listed = await async_client.get("/v1/models")
        refused = await async_client.post(
            "/v1/chat/completions",
            json={"model": "model:openai-main:gpt-other", "messages": [{"role": "user", "content": "x"}]},
        )
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    assert [model["id"] for model in listed.json()["data"]] == ["model:openai-main:gpt-live"]
    assert refused.status_code == 403
    assert refused.json()["error"]["type"] == "permission_error"
    assert refused.json()["error"]["param"] == "model"


@pytest.mark.asyncio
async def test_embeddings_answer_in_the_openai_shape(async_client, async_db) -> None:
    response = await async_client.post(
        "/v1/embeddings",
        json={"model": "model:test:embedder", "input": ["alpha", "beta"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert [item["index"] for item in body["data"]] == [0, 1]
    assert body["data"][0] == {"object": "embedding", "index": 0, "embedding": [0.0, 0.0, 0.0]}
    assert body["usage"]["prompt_tokens"] == body["usage"]["total_tokens"]
    run, _ = await _run(async_db, response.headers["x-soit-run-id"])
    assert (run.mode, run.kind, run.status) == ("gateway", "embedding", "succeeded")


@pytest.mark.asyncio
async def test_embeddings_can_be_base64_float32(async_client) -> None:
    response = await async_client.post(
        "/v1/embeddings",
        json={"model": "model:test:embedder", "input": "alpha", "encoding_format": "base64"},
    )

    encoded = response.json()["data"][0]["embedding"]
    decoded = array.array("f")
    decoded.frombytes(base64.b64decode(encoded))
    assert list(decoded) == [0.0, 0.0, 0.0]


def _png(size: tuple[int, int] = (64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def _openai_mask(size: tuple[int, int] = (64, 64)) -> bytes:
    """Left half transparent: the region to edit in OpenAI's convention."""
    mask = Image.new("RGBA", size, (0, 0, 0, 255))
    for x in range(size[0] // 2):
        for y in range(size[1]):
            mask.putpixel((x, y), (0, 0, 0, 0))
    buffer = io.BytesIO()
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


class _CapturingEditPort:
    def __init__(self) -> None:
        self.mask: bytes | None = None

    async def edit_image(
        self,
        image: bytes,
        prompt: str,
        model: str,
        mask: bytes | None = None,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> ImageGenerationResponse:
        self.mask = mask
        return ImageGenerationResponse(
            images=[GeneratedImage(b64_json=base64.b64encode(_png()).decode()) for _ in range(n)],
            model=model,
        )


async def _edit(async_client, *, mask: bytes | None = None, **fields: str):
    files = {"image": ("source.png", _png(), "image/png")}
    if mask is not None:
        files["mask"] = ("mask.png", mask, "image/png")
    data = {"model": "model:test:painter", "prompt": "fill the left half", **fields}
    return await async_client.post("/v1/images/edits", files=files, data=data)


@pytest.mark.asyncio
async def test_image_edits_take_the_openai_form_and_mask_convention(
    async_client, async_db
) -> None:
    port = _CapturingEditPort()
    with _SwapLLMPort(port):
        response = await _edit(async_client, mask=_openai_mask(), n="2", size="64x64")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert all(set(item) == {"b64_json"} for item in body["data"])
    assert port.mask is not None
    with Image.open(io.BytesIO(port.mask)) as received:
        # Transparent in the caller's mask arrives as white: edit here.
        assert received.convert("L").getpixel((0, 0)) == 255
        assert received.convert("L").getpixel((63, 0)) == 0
    run, _ = await _run(async_db, response.headers["x-soit-run-id"])
    assert (run.mode, run.kind, run.status) == ("gateway", "image", "succeeded")


@pytest.mark.asyncio
async def test_image_edits_refuse_masks_they_cannot_read(async_client) -> None:
    no_alpha = await _edit(async_client, mask=_png())
    assert no_alpha.status_code == 400
    assert "alpha channel" in no_alpha.json()["error"]["message"]

    wrong_size = await _edit(async_client, mask=_openai_mask((32, 32)))
    assert wrong_size.status_code == 400
    assert "dimensions" in wrong_size.json()["error"]["message"]


@pytest.mark.asyncio
async def test_image_sizes_outside_what_providers_serve_are_refused(async_client) -> None:
    edit = await _edit(async_client, size="12x12")
    assert edit.status_code == 400
    assert edit.json()["error"]["param"] == "size"

    generation = await async_client.post(
        "/v1/images/generations",
        json={"model": "model:test:painter", "prompt": "x", "size": "9999x9999"},
    )
    assert generation.status_code == 400
    assert generation.json()["error"]["param"] == "size"


@pytest.mark.asyncio
async def test_image_generation_answers_in_the_openai_shape(async_client, async_db) -> None:
    response = await async_client.post(
        "/v1/images/generations",
        json={"model": "model:test:painter", "prompt": "a red dot", "n": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["created"], int)
    assert len(body["data"]) == 2
    assert all(set(item) == {"b64_json"} for item in body["data"])
    run, _ = await _run(async_db, response.headers["x-soit-run-id"])
    assert (run.mode, run.kind, run.status) == ("gateway", "image", "succeeded")


@pytest.mark.asyncio
async def test_the_gateway_is_left_out_of_the_enveloped_openapi(async_client) -> None:
    response = await async_client.get("/api/v1/openapi.json")

    paths = response.json()["paths"]
    operation = paths["/v1/chat/completions"]["post"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert "success" not in json.dumps(schema)
    assert operation["tags"] == ["openai-compatible"]


class _CapturingGeneratePort(_CapturingEditPort):
    def __init__(self) -> None:
        super().__init__()
        self.generate_kwargs: dict[str, Any] | None = None
        self.edit_kwargs: dict[str, Any] | None = None

    async def generate_image(
        self, prompt: str, model: str, n: int = 1, size: str | None = None, **kwargs: Any
    ):
        self.generate_kwargs = kwargs
        return ImageGenerationResponse(
            images=[GeneratedImage(b64_json=base64.b64encode(_png()).decode()) for _ in range(n)],
            model=model,
        )

    async def edit_image(
        self,
        image: bytes,
        prompt: str,
        model: str,
        mask: bytes | None = None,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ):
        self.edit_kwargs = kwargs
        return await super().edit_image(image, prompt, model, mask=mask, n=n, size=size, **kwargs)


async def _generate(async_client, **fields: Any):
    body = {"model": "model:test:painter", "prompt": "a red dot", **fields}
    return await async_client.post("/v1/images/generations", json=body)


@pytest.mark.asyncio
async def test_image_generation_forwards_background_and_output_format(async_client) -> None:
    port = _CapturingGeneratePort()
    with _SwapLLMPort(port):
        response = await _generate(async_client, background="transparent", output_format="webp")

    assert response.status_code == 200, response.text
    assert port.generate_kwargs["background"] == "transparent"
    assert port.generate_kwargs["output_format"] == "webp"


@pytest.mark.asyncio
async def test_image_generation_sends_no_option_it_was_not_given(async_client) -> None:
    port = _CapturingGeneratePort()
    with _SwapLLMPort(port):
        response = await _generate(async_client)

    assert response.status_code == 200, response.text
    assert "background" not in port.generate_kwargs
    assert "output_format" not in port.generate_kwargs


@pytest.mark.asyncio
async def test_an_auto_background_is_the_providers_default(async_client) -> None:
    # OpenAI's SDK sends auto; it means what leaving the field out means.
    port = _CapturingGeneratePort()
    with _SwapLLMPort(port):
        generation = await _generate(async_client, background="auto", output_format="jpeg")
        edit = await _edit(async_client, background="auto", output_format="jpeg")

    assert generation.status_code == 200, generation.text
    assert edit.status_code == 200, edit.text
    assert "background" not in port.generate_kwargs
    assert port.generate_kwargs["output_format"] == "jpeg"
    assert "background" not in port.edit_kwargs
    assert port.edit_kwargs["output_format"] == "jpeg"


@pytest.mark.asyncio
async def test_a_transparent_jpeg_is_refused_before_a_run_opens(async_client, async_db) -> None:
    port = _CapturingGeneratePort()
    with _SwapLLMPort(port):
        generation = await _generate(async_client, background="transparent", output_format="jpeg")
        edit = await _edit(async_client, background="transparent", output_format="jpeg")

    for response in (generation, edit):
        assert response.status_code == 400
        assert response.json()["error"]["param"] == "output_format"
        assert "x-soit-run-id" not in response.headers
    assert port.generate_kwargs is None
    assert port.edit_kwargs is None
    runs = (await async_db.exec(select(Run).where(Run.kind == "image"))).all()
    assert runs == []


@pytest.mark.asyncio
async def test_image_formats_it_cannot_label_are_refused(async_client) -> None:
    generation = await _generate(async_client, output_format="gif")
    edit = await _edit(async_client, output_format="gif")

    assert generation.status_code == 400
    assert edit.status_code == 400
