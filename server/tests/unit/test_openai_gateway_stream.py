"""A gateway stream the client abandons still closes its run and its model call."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.api.openai.router import _stream_error, _stream_events
from app.api.openai.schemas import ChatCompletionRequest
from app.kernel.commons.errors import CreditExhaustedError
from app.kernel.ports.llm.interface import ChatStreamChunk


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


@pytest.mark.asyncio
async def test_an_abandoned_stream_fails_the_run_and_closes_the_model_stream() -> None:
    closed: list[bool] = []

    async def endless() -> AsyncIterator[ChatStreamChunk]:
        try:
            while True:
                yield ChatStreamChunk(delta="more ")
        finally:
            closed.append(True)

    writer = _Writer()
    session = _Session()
    stream = endless()
    first = await anext(stream)
    events = _stream_events(
        session,  # type: ignore[arg-type]
        writer,  # type: ignore[arg-type]
        "run_1",
        ChatCompletionRequest(model="m", messages=[{"role": "user", "content": "x"}]),
        stream,
        first,
    )

    assert b'"role":"assistant"' in await anext(events)
    assert b'"content":"more "' in await anext(events)
    await events.aclose()

    assert writer.updates == [("run_1", "failed", "CLIENT_DISCONNECTED")]
    assert session.commits == 1
    assert closed == [True]


@pytest.mark.asyncio
async def test_a_finished_stream_is_not_treated_as_abandoned() -> None:
    async def short() -> AsyncIterator[ChatStreamChunk]:
        yield ChatStreamChunk(delta="done", finish_reason="stop")

    writer = _Writer()
    stream = short()
    first = await anext(stream)
    events = _stream_events(
        _Session(),  # type: ignore[arg-type]
        writer,  # type: ignore[arg-type]
        "run_2",
        ChatCompletionRequest(model="m", messages=[{"role": "user", "content": "x"}]),
        stream,
        first,
    )

    body = [event async for event in events]

    assert body[-1] == b"data: [DONE]\n\n"
    assert writer.updates == [("run_2", "succeeded", None)]


def test_stream_errors_carry_the_status_type_without_internal_text() -> None:
    assert _stream_error(CreditExhaustedError())["error"]["type"] == "insufficient_quota"
    internal = _stream_error(RuntimeError("password=hunter2 in provider trace"))
    assert internal["error"] == {
        "message": "The model call failed",
        "type": "api_error",
        "param": None,
        "code": "internal_error",
    }
