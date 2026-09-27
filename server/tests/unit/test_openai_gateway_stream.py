"""A gateway stream the client abandons still closes its run and its model call."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.api.openai.router import _stream_error, _streaming_response
from app.api.openai.schemas import ChatCompletionRequest
from app.kernel.commons.errors import CreditExhaustedError
from app.kernel.ports.llm.interface import ChatStreamChunk, ToolCallDelta

REQUEST = ChatCompletionRequest(model="m", messages=[{"role": "user", "content": "x"}])


class _Writer:
    def __init__(self) -> None:
        self.updates: list[tuple[str, str, str | None]] = []

    async def update_run_status(self, run_id: str, status: str, **kwargs: Any) -> None:
        self.updates.append((run_id, status, kwargs.get("error_code")))


class _Session:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class _Model:
    """An endless model stream that notes when it is closed."""

    def __init__(self) -> None:
        self.closed = False

    async def stream(self) -> AsyncIterator[ChatStreamChunk]:
        try:
            while True:
                yield ChatStreamChunk(delta="more ")
        finally:
            self.closed = True


def _client_gone_after(body_messages: int) -> tuple[list[dict[str, Any]], Any]:
    """A send that fails once `body_messages` body messages went through."""

    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        bodies = sum(1 for item in sent if item["type"] == "http.response.body")
        if message["type"] == "http.response.body" and bodies >= body_messages:
            raise OSError("the client is gone")
        if message["type"] == "http.response.start" and body_messages < 0:
            raise OSError("the client is gone")
        sent.append(message)

    return sent, send


async def _stream_to(
    body_messages: int,
) -> tuple[_Writer, _Session, _Model, list[dict[str, Any]]]:
    model = _Model()
    stream = model.stream()
    # The endpoint pulls the first chunk before the response exists.
    first = await anext(stream)
    writer, session = _Writer(), _Session()
    response = _streaming_response(
        session,  # type: ignore[arg-type]
        writer,  # type: ignore[arg-type]
        "run_1",
        REQUEST,
        stream,
        first,
    )
    sent, send = _client_gone_after(body_messages)
    with pytest.raises(OSError):
        await response.stream_response(send)
    return writer, session, model, sent


@pytest.mark.asyncio
async def test_a_client_gone_mid_stream_fails_the_run_and_closes_the_model_stream() -> None:
    writer, session, model, sent = await _stream_to(2)

    assert [item["type"] for item in sent] == [
        "http.response.start",
        "http.response.body",
        "http.response.body",
    ]
    assert writer.updates == [("run_1", "failed", "CLIENT_DISCONNECTED")]
    assert session.commits == 1
    # Closed before streaming returned, not whenever the stream is collected.
    assert model.closed


@pytest.mark.asyncio
async def test_a_client_gone_before_the_body_starts_still_closes_the_call() -> None:
    writer, session, model, sent = await _stream_to(-1)

    assert sent == []
    assert writer.updates == [("run_1", "failed", "CLIENT_DISCONNECTED")]
    assert session.commits == 1
    assert model.closed


@pytest.mark.asyncio
async def test_a_finished_stream_is_not_treated_as_abandoned() -> None:
    async def short() -> AsyncIterator[ChatStreamChunk]:
        yield ChatStreamChunk(delta="done", finish_reason="stop")

    writer, session = _Writer(), _Session()
    stream = short()
    first = await anext(stream)
    response = _streaming_response(
        session,  # type: ignore[arg-type]
        writer,  # type: ignore[arg-type]
        "run_2",
        REQUEST,
        stream,
        first,
    )
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await response.stream_response(send)

    bodies = [item["body"] for item in sent if item["type"] == "http.response.body"]
    assert bodies[-2] == b"data: [DONE]\n\n"
    assert writer.updates == [("run_2", "succeeded", None)]
    assert session.commits == 1


@pytest.mark.asyncio
async def test_a_failure_of_the_gateway_itself_closes_the_model_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[bool] = []

    async def calls() -> AsyncIterator[ChatStreamChunk]:
        try:
            yield ChatStreamChunk(delta="Looking it up.")
            yield ChatStreamChunk(tool_call_deltas=[ToolCallDelta(index=0, name="lookup")])
            yield ChatStreamChunk(delta="never read")
        finally:
            closed.append(True)

    def broken(deltas: Any) -> Any:
        del deltas
        raise TypeError("cannot render the call")

    monkeypatch.setattr("app.api.openai.router.tool_call_deltas_out", broken)
    writer, session = _Writer(), _Session()
    stream = calls()
    first = await anext(stream)
    response = _streaming_response(
        session,  # type: ignore[arg-type]
        writer,  # type: ignore[arg-type]
        "run_3",
        REQUEST,
        stream,
        first,
    )
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await response.stream_response(send)

    # The model stream is closed now, so its call settles in this task.
    assert closed == [True]
    assert writer.updates == [("run_3", "failed", "GATEWAY_CHAT_ERROR")]
    assert session.commits == 1


def test_stream_errors_carry_the_status_type_without_internal_text() -> None:
    assert _stream_error(CreditExhaustedError())["error"]["type"] == "insufficient_quota"
    internal = _stream_error(RuntimeError("password=hunter2 in provider trace"))
    assert internal["error"] == {
        "message": "The model call failed",
        "type": "api_error",
        "param": None,
        "code": "internal_error",
    }
