"""The run lifecycle every gateway entry point shares.

A gateway call is one run with ``mode="gateway"`` whose subject is the API key,
or the user when the call authenticates with a session. The OpenAI-compatible
and Anthropic-compatible entry points open and close that run the same way and
stream under the same cleanup guarantees; only the wire shapes differ.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import anyio
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ChatStreamChunk
from app.kernel.runtime.runs.writer import TraceWriter

logger = logging.getLogger(__name__)

RUN_ID_HEADER = "x-soit-run-id"
GATEWAY_MODE = "gateway"
SUMMARY_LIMIT = 8192
# How long closing a streamed call may take once its body stops; it runs
# shielded from the cancellation that ends the response, and covers closing
# the model call (which writes the ledger) and the run.
CLEANUP_TIMEOUT_SECONDS = 90.0


def subject(ctx: RequestContext) -> tuple[str, str]:
    if ctx.api_key_id:
        return "api_key", ctx.api_key_id
    return "user", ctx.user_id


async def open_run(
    trace_writer: TraceWriter, ctx: RequestContext, *, kind: str, summary: str
) -> str:
    subject_kind, subject_id = subject(ctx)
    run = await trace_writer.create_run(
        GATEWAY_MODE,
        kind=kind,
        subject_kind=subject_kind,
        subject_id=subject_id,
        input_summary=summary,
        source=GATEWAY_MODE,
    )
    await trace_writer.update_run_status(run.id, "running")
    return run.id


async def close_run(
    trace_writer: TraceWriter,
    db: AsyncSession,
    run_id: str,
    status: str,
    **fields: Any,
) -> None:
    """Write the run's final status and commit it.

    A database write that failed earlier in the request (the model call
    recording its usage, say) leaves the transaction unusable; what it held
    is lost, but the run still closes after a rollback.
    """
    try:
        await trace_writer.update_run_status(run_id, status, **fields)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        await trace_writer.update_run_status(run_id, status, **fields)
        await db.commit()


async def fail_run(
    trace_writer: TraceWriter,
    db: AsyncSession,
    run_id: str,
    exc: BaseException,
    *,
    fallback_code: str,
) -> None:
    await close_run(
        trace_writer,
        db,
        run_id,
        "failed",
        error_code=getattr(exc, "code", None) or fallback_code,
        error_message=str(exc)[:2000],
    )


class StreamState:
    """Whether the body of a streamed call ran to its end."""

    finished = False


class GatewayStreamingResponse(StreamingResponse):
    """Streams a gateway call and closes it however streaming stops.

    A disconnect can cancel the response before its body starts or while it
    waits on ``send``. The body generator would then only be closed whenever
    it is collected, from another task, and one that never started runs no
    cleanup at all. So the response closes the body itself and, unless the
    body finished, closes the model stream (which records the call's usage)
    and fails the run, in the task that owns the request's session.
    """

    def __init__(
        self,
        content: AsyncIterator[bytes],
        *,
        state: StreamState,
        abandon: Callable[[], Awaitable[None]],
        **kwargs: Any,
    ) -> None:
        super().__init__(content, **kwargs)
        self._state = state
        self._abandon = abandon

    async def stream_response(self, send: Any) -> None:
        try:
            await super().stream_response(send)
        finally:
            # The body task is being cancelled when the client has gone; an
            # unshielded await would be cancelled again before the run closes.
            with anyio.move_on_after(CLEANUP_TIMEOUT_SECONDS, shield=True) as scope:
                aclose = getattr(self.body_iterator, "aclose", None)
                if aclose is not None:
                    await aclose()
                if not self._state.finished:
                    await self._abandon()
            if scope.cancelled_caught:
                logger.warning("Closing an abandoned gateway stream timed out")


async def close_model_stream(stream: AsyncIterator[ChatStreamChunk], run_id: str) -> None:
    """Close a model stream; the model call records its usage as it closes."""

    aclose = getattr(stream, "aclose", None)
    if aclose is None:
        return
    try:
        await aclose()
    except Exception:
        logger.warning("Could not close a gateway model stream", extra={"run_id": run_id})


async def close_abandoned(
    stream: AsyncIterator[ChatStreamChunk],
    trace_writer: TraceWriter,
    db: AsyncSession,
    run_id: str,
) -> None:
    """Close the model stream of a call whose client went away, then its run."""

    await close_model_stream(stream, run_id)
    try:
        await close_run(
            trace_writer,
            db,
            run_id,
            "failed",
            error_code="CLIENT_DISCONNECTED",
            error_message="The client closed the stream before it finished",
        )
    except Exception:
        logger.warning("Could not close an abandoned gateway run", extra={"run_id": run_id})
        with contextlib.suppress(Exception):
            await db.rollback()
