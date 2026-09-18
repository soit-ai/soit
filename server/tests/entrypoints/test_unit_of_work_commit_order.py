"""Where the request's unit of work commits relative to the response.

Handlers and repositories only flush; the session dependency commits. With
``uvicorn --workers N`` a client that reads a 201 and immediately uses the new
row on another worker must find it committed, so for a plain response the
commit has to land before ``http.response.start`` leaves the process. A
streaming response is the opposite case: its body generator reads through the
same session after the handler returned, so that session must stay open until
the body is done.

Both tests drive the real ``get_async_db`` over the test engine instead of the
fixture override, so the request-scoped session and the function-scoped commit
run exactly as they do in production.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db import session as session_module
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.schemas import ResponseCreateRequest
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.main import app
from app.middleware.auth import get_current_context

HEADERS = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}

Timeline = list[str]


def _recording_transport(timeline: Timeline) -> ASGITransport:
    """Serve the app while noting when the response starts and finishes."""

    async def recording_app(
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        async def recording_send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                timeline.append(f"response.start:{message['status']}")
            elif message["type"] == "http.response.body" and not message.get("more_body"):
                timeline.append("response.end")
            await send(message)

        await app(scope, receive, recording_send)

    return ASGITransport(app=recording_app)


@pytest_asyncio.fixture
async def recorded_client(
    async_db: AsyncSession, ctx: RequestContext, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[AsyncClient, Timeline]]:
    """An ASGI client whose requests run the real session dependency over the test engine.

    Every commit on a request session and every response boundary is appended
    to the returned timeline, in the order they happened.
    """

    timeline: Timeline = []

    class RecordingSession(AsyncSession):
        async def commit(self) -> None:
            await super().commit()
            timeline.append("commit")

    factory = async_sessionmaker(
        bind=async_db.bind,
        class_=RecordingSession,
        expire_on_commit=False,
        autoflush=False,
    )
    monkeypatch.setattr(session_module, "get_async_session_local", lambda: factory)

    async def _override_get_current_context() -> RequestContext:
        return ctx

    app.dependency_overrides[get_current_context] = _override_get_current_context
    try:
        async with AsyncClient(
            transport=_recording_transport(timeline), base_url="http://testserver"
        ) as client:
            yield client, timeline
    finally:
        app.dependency_overrides.pop(get_current_context, None)


@pytest.mark.asyncio
async def test_plain_response_is_sent_only_after_the_unit_of_work_committed(
    recorded_client: tuple[AsyncClient, Timeline],
) -> None:
    client, timeline = recorded_client

    response = await client.post(
        "/api/v1/threads",
        json={"agent_id": "agent_demo", "title": "Committed before 201"},
        headers=HEADERS,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert "commit" in timeline, timeline
    assert timeline.index("commit") < timeline.index("response.start:201"), timeline


@pytest.mark.asyncio
async def test_plain_response_error_rolls_back_without_committing(
    recorded_client: tuple[AsyncClient, Timeline],
) -> None:
    client, timeline = recorded_client

    response = await client.get("/api/v1/threads/thread_missing", headers=HEADERS)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "commit" not in timeline, timeline


@pytest.mark.asyncio
async def test_streaming_response_keeps_the_session_open_while_the_body_streams(
    recorded_client: tuple[AsyncClient, Timeline],
    async_db: AsyncSession,
    ctx: RequestContext,
) -> None:
    client, timeline = recorded_client
    service = ResponseService(
        db=async_db,
        ctx=ctx,
        response_repo=ResponseRepository(async_db, ctx),
        event_repo=ResponseEventRepository(async_db, ctx),
        trace_writer=TraceWriter(async_db, ctx),
    )
    seeded = await service.create_response(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id=None,
            input={"messages": [{"role": "user", "content": "replay me"}]},
        ),
    )
    seeded = await service.mark_running(seeded)
    await service.complete_response(response=seeded, output_json={"text": "done"})
    await async_db.commit()
    timeline.clear()

    replay = await client.get(f"/api/v1/responses/{seeded.id}/stream", headers=HEADERS)

    assert replay.status_code == status.HTTP_200_OK
    assert replay.headers["content-type"].startswith("text/event-stream")
    body = replay.text
    assert "response.succeeded" in body, body
    assert body.rstrip().endswith("data: [DONE]"), body
    # The handler-return commit lands before the stream starts, as for any
    # response. The events were then read through the request session while
    # the body streamed, and that session's own commit only landed once the
    # body was complete: the session outlived the handler.
    assert timeline[0] == "commit", timeline
    assert timeline[1] == "response.start:200", timeline
    assert timeline.index("response.end") < len(timeline) - 1, timeline
    assert timeline[-1] == "commit", timeline
