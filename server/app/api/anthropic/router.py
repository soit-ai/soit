"""Anthropic-compatible entry point: any Anthropic SDK pointed at SOIT.

``POST /v1/messages`` is an ordinary governed model call, the same as the
OpenAI-compatible ``/v1/chat/completions``: it runs through the LLM policy
gateway (rate limits, quotas, credit and budget guards, content safety,
egress, cost) and is one run with ``mode="gateway"`` whose subject is the API
key, or the user when the call authenticates with a session. Only the wire
shapes differ: Messages requests and responses, Anthropic's named stream
events and Anthropic's error bodies. The run id travels in the
``x-soit-run-id`` header.

Clients authenticate with ``x-api-key`` (what Anthropic SDKs send) or a
Bearer token. The ``anthropic-version`` and ``anthropic-beta`` headers are
accepted and not interpreted.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from functools import partial
from typing import Annotated, Any

import anyio
import orjson
from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.anthropic.convert import (
    message_body,
    stop_reason,
    to_chat_messages,
    to_tool_choice,
    to_tool_definitions,
    usage,
)
from app.api.anthropic.schemas import CountTokensRequest, MessagesRequest
from app.api.gateway_runs import (
    CLEANUP_TIMEOUT_SECONDS,
    RUN_ID_HEADER,
    SUMMARY_LIMIT,
    GatewayStreamingResponse,
    StreamState,
    close_abandoned,
    close_model_stream,
    close_run,
    fail_run,
    open_run,
)
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.infra.db.session import get_async_db
from app.kernel.commons.errors import KernelError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ChatMessage, ChatStreamChunk
from app.kernel.ports.llm.usage_estimate import estimate_prompt_tokens
from app.kernel.runtime.runs.writer import TraceWriter
from app.middleware.error_handler import ERROR_CODE_TO_STATUS
from app.middleware.openai_errors import anthropic_error_body
from app.wiring import get_container

logger = logging.getLogger(__name__)

router = APIRouter()


def _chat_kwargs(payload: MessagesRequest) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    tools = to_tool_definitions(payload.tools)
    if tools:
        kwargs["tools"] = tools
        tool_choice = to_tool_choice(payload.tool_choice)
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
    if payload.top_p is not None:
        kwargs["top_p"] = payload.top_p
    if payload.stop_sequences:
        kwargs["stop"] = payload.stop_sequences
    return kwargs


@router.post("/messages")
async def create_message(
    payload: MessagesRequest,
    ctx: Annotated[RequestContext, Depends(require_workspace_write_ctx)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    response: Response,
):
    """Messages, whole or streamed as Anthropic's named events."""

    messages = to_chat_messages(payload.system, payload.messages)
    # Refuses what cannot be served before any run opens.
    kwargs = _chat_kwargs(payload)
    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)
    run_id = await open_run(
        trace_writer,
        ctx,
        kind="chat",
        summary=f"model={payload.model}, messages={len(messages)}, stream={payload.stream}",
    )
    await db.commit()
    kwargs["run_id"] = run_id

    if payload.stream:
        return await _start_stream(db, trace_writer, llm_port, run_id, payload, messages, kwargs)

    response.headers[RUN_ID_HEADER] = run_id
    try:
        result = await llm_port.chat(
            messages, payload.model, payload.temperature, payload.max_tokens, **kwargs
        )
        await trace_writer.update_run_status(
            run_id,
            "succeeded",
            output_summary=(result.text or "")[:SUMMARY_LIMIT] or None,
        )
        await db.commit()
    except Exception as exc:
        await fail_run(trace_writer, db, run_id, exc, fallback_code="GATEWAY_CHAT_ERROR")
        raise
    return message_body(message_id=f"msg_{run_id}", model=payload.model, response=result)


@router.post("/messages/count_tokens")
async def count_message_tokens(
    payload: CountTokensRequest,
    _ctx: Annotated[RequestContext, Depends(require_workspace_read_ctx)],
):
    """An estimate of the prompt's tokens; no model is called and no run opens.

    The count is SOIT's own estimate, not the model provider's tokenizer, so it
    can differ from what the call is later billed for.
    """

    messages = to_chat_messages(payload.system, payload.messages)
    tools = to_tool_definitions(payload.tools)
    return {"input_tokens": estimate_prompt_tokens(messages, tools)}


def _sse(event: str, body: dict[str, Any]) -> bytes:
    return b"event: " + event.encode() + b"\ndata: " + orjson.dumps(body) + b"\n\n"


def _stream_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, KernelError):
        return anthropic_error_body(ERROR_CODE_TO_STATUS.get(exc.code, 500), message=exc.message)
    # Anything else is an internal failure whose text is not the client's.
    return anthropic_error_body(500, message="The model call failed")


async def _start_stream(
    db: AsyncSession,
    trace_writer: TraceWriter,
    llm_port: Any,
    run_id: str,
    payload: MessagesRequest,
    messages: list[ChatMessage],
    kwargs: dict[str, Any],
) -> StreamingResponse:
    stream = llm_port.stream_chat(
        messages, payload.model, payload.temperature, payload.max_tokens, **kwargs
    )
    # The gateway refuses (rate limit, quota, credit, a blocked prompt) before
    # its first event, so pulling that event here lets a refusal answer with
    # its own status code instead of an error event inside a 200 stream.
    try:
        first: ChatStreamChunk | None = await anext(stream)
    except StopAsyncIteration:
        first = None
    except Exception as exc:
        await fail_run(trace_writer, db, run_id, exc, fallback_code="GATEWAY_CHAT_ERROR")
        raise
    estimated_input = estimate_prompt_tokens(messages, kwargs.get("tools"))
    state = StreamState()
    return GatewayStreamingResponse(
        # The request's session stays open until the body has been sent.
        _stream_events(db, trace_writer, run_id, payload, stream, first, estimated_input, state),
        state=state,
        abandon=partial(close_abandoned, stream, trace_writer, db, run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            RUN_ID_HEADER: run_id,
        },
    )


class _Blocks:
    """Content blocks of a streamed message, which Anthropic opens one at a time."""

    def __init__(self) -> None:
        self._next = 0
        self._open: tuple[str, int | None] | None = None  # ("text", None) or ("tool", index)

    def close(self) -> list[bytes]:
        if self._open is None:
            return []
        self._open = None
        return [_sse("content_block_stop", {"type": "content_block_stop", "index": self._next - 1})]

    def text(self, delta: str) -> list[bytes]:
        events: list[bytes] = []
        if self._open != ("text", None):
            events += self.close()
            events.append(self._start({"type": "text", "text": ""}))
            self._open = ("text", None)
        events.append(self._delta({"type": "text_delta", "text": delta}))
        return events

    def tool_start(self, index: int, call_id: str, name: str) -> list[bytes]:
        events = self.close()
        events.append(
            self._start({"type": "tool_use", "id": call_id, "name": name, "input": {}})
        )
        self._open = ("tool", index)
        return events

    def tool_arguments(self, partial_json: str) -> list[bytes]:
        if not partial_json:
            return []
        return [self._delta({"type": "input_json_delta", "partial_json": partial_json})]

    def is_open_tool(self, index: int) -> bool:
        return self._open == ("tool", index)

    def _start(self, block: dict[str, Any]) -> bytes:
        event = _sse(
            "content_block_start",
            {"type": "content_block_start", "index": self._next, "content_block": block},
        )
        self._next += 1
        return event

    def _delta(self, delta: dict[str, Any]) -> bytes:
        return _sse(
            "content_block_delta",
            {"type": "content_block_delta", "index": self._next - 1, "delta": delta},
        )


async def _stream_events(
    db: AsyncSession,
    trace_writer: TraceWriter,
    run_id: str,
    payload: MessagesRequest,
    stream: AsyncIterator[ChatStreamChunk],
    first: ChatStreamChunk | None,
    estimated_input: int,
    state: StreamState,
) -> AsyncIterator[bytes]:
    prompt_tokens = completion_tokens = 0
    raw_finish: str | None = None
    saw_tool_calls = False
    text_parts: list[str] = []
    blocks = _Blocks()

    async def parts() -> AsyncIterator[ChatStreamChunk]:
        if first is None:
            return
        yield first
        async for part in stream:
            yield part

    yield _sse(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": f"msg_{run_id}",
                "type": "message",
                "role": "assistant",
                "model": payload.model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                # The provider's count arrives with the last chunk; until then
                # this is the gateway's estimate, and message_delta corrects it.
                "usage": usage(estimated_input, 1),
            },
        },
    )
    yield _sse("ping", {"type": "ping"})
    try:
        async for part in parts():
            prompt_tokens = part.tokens_prompt or prompt_tokens
            completion_tokens = part.tokens_completion or completion_tokens
            raw_finish = part.finish_reason or raw_finish
            if part.delta:
                text_parts.append(part.delta)
                for event in blocks.text(part.delta):
                    yield event
            if part.tool_call_deltas:
                saw_tool_calls = True
                for delta in part.tool_call_deltas:
                    if delta.id or delta.name or not blocks.is_open_tool(delta.index):
                        for event in blocks.tool_start(
                            delta.index,
                            delta.id or f"toolu_{run_id}_{delta.index}",
                            delta.name or "",
                        ):
                            yield event
                    for event in blocks.tool_arguments(delta.arguments_delta):
                        yield event
            elif part.tool_calls and not saw_tool_calls:
                # A provider that reports calls only once, whole, still
                # streams them in delta form.
                saw_tool_calls = True
                for index, call in enumerate(part.tool_calls):
                    for event in blocks.tool_start(index, call.id, call.name):
                        yield event
                    for event in blocks.tool_arguments(orjson.dumps(call.arguments).decode()):
                        yield event
    except Exception as exc:
        state.finished = True
        # A disconnect landing mid-write must not leave the run open.
        with anyio.move_on_after(CLEANUP_TIMEOUT_SECONDS, shield=True) as scope:
            # The failure may be the gateway's own, with the model still
            # generating; closing its stream settles the call either way.
            await close_model_stream(stream, run_id)
            await fail_run(trace_writer, db, run_id, exc, fallback_code="GATEWAY_CHAT_ERROR")
        if scope.cancelled_caught:
            logger.warning("Closing a failed gateway run timed out", extra={"run_id": run_id})
        yield _sse("error", _stream_error(exc))
        return

    state.finished = True
    with anyio.move_on_after(CLEANUP_TIMEOUT_SECONDS, shield=True) as scope:
        await close_run(
            trace_writer,
            db,
            run_id,
            "succeeded",
            output_summary="".join(text_parts)[:SUMMARY_LIMIT] or None,
        )
    if scope.cancelled_caught:
        logger.warning("Closing a finished gateway run timed out", extra={"run_id": run_id})
    for event in blocks.close():
        yield event
    yield _sse(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {
                "stop_reason": stop_reason(raw_finish, has_tool_calls=saw_tool_calls),
                "stop_sequence": None,
            },
            "usage": usage(prompt_tokens or estimated_input, completion_tokens),
        },
    )
    yield _sse("message_stop", {"type": "message_stop"})

