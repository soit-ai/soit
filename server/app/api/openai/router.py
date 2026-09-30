"""OpenAI-compatible entry point: any OpenAI SDK pointed at SOIT.

Every call is an ordinary governed model call: it runs through the same LLM
policy gateway as SOIT's own agents (rate limits, quotas, credit and budget
guards, content safety, egress, cost), and each request is one run with
``mode="gateway"`` whose subject is the API key, or the user when the call
authenticates with a session. Responses and errors use OpenAI's shapes; the
run id travels in the ``x-soit-run-id`` header.
"""

from __future__ import annotations

import array
import base64
import logging
import re
import time
from collections.abc import AsyncIterator
from functools import partial
from typing import Annotated, Any, Literal

import anyio
import orjson
from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

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
from app.api.openai.convert import (
    chunk_body,
    completion_body,
    finish_reason,
    to_chat_messages,
    to_tool_definitions,
    tool_call_deltas_out,
    usage,
)
from app.api.openai.dependencies import get_model_catalog
from app.api.openai.schemas import (
    MAX_IMAGE_PROMPT_CHARS,
    ChatCompletionRequest,
    EmbeddingRequest,
    ImageGenerationRequest,
    validate_image_size,
)
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.infra.db.session import get_async_db
from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.catalog import ModelCatalogPort
from app.kernel.ports.llm.image_mask import (
    assert_mask_matches_image,
    openai_alpha_to_mask,
)
from app.kernel.ports.llm.interface import ChatMessage, ChatStreamChunk
from app.kernel.runtime.attachments.service import AttachmentService
from app.kernel.runtime.images.service import (
    ImageJobRequest,
    check_image_job,
    execute_image_job,
)
from app.kernel.runtime.runs.writer import TraceWriter
from app.middleware.error_handler import ERROR_CODE_TO_STATUS
from app.middleware.openai_errors import openai_error_body
from app.wiring import get_container
from app.wiring.image_job import keep_image_run_alive

logger = logging.getLogger(__name__)

router = APIRouter()

_DONE = b"data: [DONE]\n\n"
MAX_UPLOAD_IMAGE_BYTES = AttachmentService.MAX_FILE_SIZE


def _chat_kwargs(payload: ChatCompletionRequest, run_id: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"run_id": run_id}
    tools = to_tool_definitions(payload.tools)
    if tools:
        kwargs["tools"] = tools
        if payload.tool_choice is not None:
            kwargs["tool_choice"] = payload.tool_choice
    for key in ("top_p", "response_format", "stop", "seed"):
        value = getattr(payload, key)
        if value is not None:
            kwargs[key] = value
    return kwargs


@router.post("/chat/completions")
async def create_chat_completion(
    payload: ChatCompletionRequest,
    ctx: Annotated[RequestContext, Depends(require_workspace_write_ctx)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    response: Response,
):
    """Chat Completions, whole or streamed as ``chat.completion.chunk`` events."""

    messages = to_chat_messages(payload.messages)
    max_tokens = payload.max_completion_tokens or payload.max_tokens
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

    if payload.stream:
        return await _start_stream(
            db, trace_writer, llm_port, run_id, payload, messages, max_tokens
        )

    response.headers[RUN_ID_HEADER] = run_id
    try:
        result = await llm_port.chat(
            messages,
            payload.model,
            payload.temperature,
            max_tokens,
            **_chat_kwargs(payload, run_id),
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
    return completion_body(
        completion_id=f"chatcmpl-{run_id}",
        created=int(time.time()),
        model=payload.model,
        response=result,
    )


def _sse(body: dict[str, Any]) -> bytes:
    return b"data: " + orjson.dumps(body) + b"\n\n"


def _stream_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, KernelError):
        return openai_error_body(
            ERROR_CODE_TO_STATUS.get(exc.code, 500),
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
    # Anything else is an internal failure whose text is not the client's.
    return openai_error_body(500, code="INTERNAL_ERROR", message="The model call failed")


async def _start_stream(
    db: AsyncSession,
    trace_writer: TraceWriter,
    llm_port: Any,
    run_id: str,
    payload: ChatCompletionRequest,
    messages: list[ChatMessage],
    max_tokens: int | None,
) -> StreamingResponse:
    stream = llm_port.stream_chat(
        messages,
        payload.model,
        payload.temperature,
        max_tokens,
        **_chat_kwargs(payload, run_id),
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
    return _streaming_response(db, trace_writer, run_id, payload, stream, first)


def _streaming_response(
    db: AsyncSession,
    trace_writer: TraceWriter,
    run_id: str,
    payload: ChatCompletionRequest,
    stream: AsyncIterator[ChatStreamChunk],
    first: ChatStreamChunk | None,
) -> GatewayStreamingResponse:
    state = StreamState()
    return GatewayStreamingResponse(
        # The request's session stays open until the body has been sent.
        _stream_events(db, trace_writer, run_id, payload, stream, first, state),
        state=state,
        abandon=partial(close_abandoned, stream, trace_writer, db, run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            RUN_ID_HEADER: run_id,
        },
    )


async def _stream_events(
    db: AsyncSession,
    trace_writer: TraceWriter,
    run_id: str,
    payload: ChatCompletionRequest,
    stream: AsyncIterator[ChatStreamChunk],
    first: ChatStreamChunk | None,
    state: StreamState,
) -> AsyncIterator[bytes]:
    completion_id = f"chatcmpl-{run_id}"
    created = int(time.time())
    include_usage = bool(payload.stream_options and payload.stream_options.include_usage)
    prompt_tokens = completion_tokens = 0
    raw_finish: str | None = None
    saw_tool_calls = False
    text_parts: list[str] = []

    def chunk(delta: dict[str, Any] | None, **extra: Any) -> bytes:
        return _sse(
            chunk_body(
                completion_id=completion_id,
                created=created,
                model=payload.model,
                delta=delta,
                **extra,
            )
        )

    async def parts() -> AsyncIterator[ChatStreamChunk]:
        if first is None:
            return
        yield first
        async for part in stream:
            yield part

    yield chunk({"role": "assistant", "content": ""})
    try:
        async for part in parts():
            prompt_tokens = part.tokens_prompt or prompt_tokens
            completion_tokens = part.tokens_completion or completion_tokens
            raw_finish = part.finish_reason or raw_finish
            if part.delta:
                text_parts.append(part.delta)
                yield chunk({"content": part.delta})
            if part.tool_call_deltas:
                saw_tool_calls = True
                yield chunk({"tool_calls": tool_call_deltas_out(part.tool_call_deltas)})
            elif part.tool_calls and not saw_tool_calls:
                # A provider that reports calls only once, whole, still
                # streams them in delta form.
                saw_tool_calls = True
                yield chunk(
                    {
                        "tool_calls": [
                            {
                                "index": index,
                                "id": call.id,
                                "type": "function",
                                "function": {
                                    "name": call.name,
                                    "arguments": orjson.dumps(call.arguments).decode(),
                                },
                            }
                            for index, call in enumerate(part.tool_calls)
                        ]
                    }
                )
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
        yield _sse(_stream_error(exc))
        yield _DONE
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
    yield chunk({}, finish=finish_reason(raw_finish, has_tool_calls=saw_tool_calls))
    if include_usage:
        yield chunk(None, usage_block=usage(prompt_tokens, completion_tokens))
    yield _DONE


@router.get("/models")
async def list_models(
    ctx: Annotated[RequestContext, Depends(require_workspace_read_ctx)],
    catalog: Annotated[ModelCatalogPort, Depends(get_model_catalog)],
):
    """The workspace's callable models, by the ref a call names.

    A key limited to some models lists only those, so a client that picks a
    model from the list never picks one it will be refused.
    """

    entries = [
        {
            "id": model.id,
            "object": "model",
            "created": int(model.created_at.timestamp()),
            "owned_by": model.owned_by,
        }
        for model in await catalog.list_callable_models()
    ]
    if ctx.allowed_models is not None:
        entries = [entry for entry in entries if entry["id"] in ctx.allowed_models]
    return {"object": "list", "data": entries}


def _embedding_value(vector: list[float], encoding_format: str) -> list[float] | str:
    if encoding_format != "base64":
        return vector
    # OpenAI's base64 form is the vector as little-endian float32 bytes.
    packed = array.array("f", vector)
    if packed.itemsize != 4:
        raise RuntimeError("float32 arrays are required for base64 embeddings")
    return base64.b64encode(packed.tobytes()).decode("ascii")


@router.post("/embeddings")
async def create_embeddings(
    payload: EmbeddingRequest,
    ctx: Annotated[RequestContext, Depends(require_workspace_write_ctx)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    response: Response,
):
    """Embeddings in OpenAI's ``list`` of ``embedding`` objects."""

    texts = [payload.input] if isinstance(payload.input, str) else payload.input
    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)
    run_id = await open_run(
        trace_writer,
        ctx,
        kind="embedding",
        summary=f"model={payload.model}, texts={len(texts)}",
    )
    await db.commit()
    response.headers[RUN_ID_HEADER] = run_id
    embed_kwargs: dict[str, Any] = {"run_id": run_id}
    if payload.dimensions is not None:
        embed_kwargs["dimensions"] = payload.dimensions
    try:
        result = await llm_port.embed(texts=texts, model=payload.model, **embed_kwargs)
        await trace_writer.update_run_status(
            run_id, "succeeded", output_summary=f"embeddings={len(result.embeddings)}"
        )
        await db.commit()
    except Exception as exc:
        await fail_run(trace_writer, db, run_id, exc, fallback_code="GATEWAY_EMBED_ERROR")
        raise
    return {
        "object": "list",
        "data": [
            {
                "object": "embedding",
                "index": index,
                "embedding": _embedding_value(vector, payload.encoding_format),
            }
            for index, vector in enumerate(result.embeddings)
        ],
        "model": payload.model,
        "usage": {"prompt_tokens": result.tokens_used, "total_tokens": result.tokens_used},
    }


async def _image_response(
    request: ImageJobRequest,
    *,
    ctx: RequestContext,
    db: AsyncSession,
    response: Response,
    summary: str,
) -> dict[str, Any]:
    """Run one governed image job and answer in OpenAI's ``created`` + ``data`` shape."""

    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)
    await check_image_job(llm_port, request)
    run_id = await open_run(trace_writer, ctx, kind="image", summary=summary)
    await db.commit()
    response.headers[RUN_ID_HEADER] = run_id
    try:
        # The job the /api/v1/images routes run, so a gateway image passes the
        # same content check before it is returned.
        async with keep_image_run_alive(db.bind, run_id):
            outcome = await execute_image_job(
                request,
                run_id=run_id,
                ctx=ctx,
                llm_port=llm_port,
                trace_writer=trace_writer,
                content_safety=container.get_content_safety_port(ctx, trace_writer),
            )
        await trace_writer.update_run_status(
            run_id, "succeeded", output_summary=f"images={len(outcome.results)}"
        )
        await db.commit()
    except Exception as exc:
        await fail_run(trace_writer, db, run_id, exc, fallback_code="GATEWAY_IMAGE_ERROR")
        raise
    data: list[dict[str, Any]] = []
    for image in outcome.results:
        if request.response_format == "url" and image.url:
            data.append({"url": image.url})
        elif image.b64_json:
            data.append({"b64_json": image.b64_json})
        elif image.url:
            data.append({"url": image.url})
    return {"created": int(time.time()), "data": data}


# OpenAI image parameters SOIT does not send to providers, each with the
# values that ask for no more than leaving the parameter out does: OpenAI's
# documented default.
_UNSENT_IMAGE_PARAMS: dict[str, tuple[Any, ...]] = {
    "style": ("vivid",),
    "moderation": ("auto",),
    "output_compression": (100,),
    "input_fidelity": ("low",),
    "partial_images": (0,),
    "stream": (False,),
}


def _refuse_unsent_params(**values: Any) -> None:
    """Refuse an OpenAI image parameter SOIT would otherwise drop.

    Each one changes the image or how it is delivered, so answering as if it
    had been applied would return and bill something other than what was
    asked for. Refused here, before a run opens.
    """
    for name, value in values.items():
        accepted = _UNSENT_IMAGE_PARAMS[name]
        if value is None or any(type(value) is type(ok) and value == ok for ok in accepted):
            continue
        choices = " or ".join(orjson.dumps(ok).decode() for ok in accepted)
        raise ValidationError(
            f"SOIT does not send {name} to image providers; omit it"
            + (f" or send {choices}" if choices else ""),
            {"param": name},
        )


# Quality values that ask for the provider's own default, as leaving the
# parameter out does: OpenAI's auto, and standard, the DALL-E default, which
# gpt-image would refuse if it were sent.
_DEFAULT_QUALITIES = frozenset({"auto", "standard"})


def _image_options(
    background: str | None, output_format: str | None, quality: str | None = None
) -> dict[str, Any]:
    """What an image job forwards of OpenAI's ``background`` and ``quality`` values.

    ``auto`` leaves the choice to the provider, as leaving it out does, so it
    is not sent, nor is a ``standard`` quality. Any other quality goes to the
    provider as given, where the route carries it, and prices the call when
    the model lists a price for it. A transparent background cannot be
    encoded as JPEG, so that pair is refused here rather than billed for an
    image that cannot be what was asked for.
    """
    if background == "transparent" and output_format == "jpeg":
        raise ValidationError(
            "A transparent background needs output_format png or webp",
            {"param": "output_format"},
        )
    options: dict[str, Any] = {}
    if background in ("transparent", "opaque"):
        options["background"] = background
    if quality is not None and quality not in _DEFAULT_QUALITIES:
        if not re.fullmatch(r"[a-z]{1,16}", quality):
            raise ValidationError("quality must be a lowercase word", {"param": "quality"})
        options["quality"] = quality
    return options


@router.post("/images/generations")
async def create_image(
    payload: ImageGenerationRequest,
    ctx: Annotated[RequestContext, Depends(require_workspace_write_ctx)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    response: Response,
):
    """Image generation in OpenAI's ``created`` + ``data`` shape."""

    _refuse_unsent_params(
        style=payload.style,
        moderation=payload.moderation,
        output_compression=payload.output_compression,
        partial_images=payload.partial_images,
        stream=payload.stream,
    )
    return await _image_response(
        ImageJobRequest(
            kind="generate",
            model=payload.model,
            prompt=payload.prompt,
            n=payload.n,
            size=payload.size,
            response_format=payload.response_format,
            output_format=payload.output_format,
            extra=_image_options(payload.background, payload.output_format, payload.quality),
        ),
        ctx=ctx,
        db=db,
        response=response,
        summary=f"model={payload.model}, n={payload.n}, size={payload.size or 'default'}",
    )


async def _read_upload(upload: UploadFile, *, field: str) -> bytes:
    data = await upload.read(MAX_UPLOAD_IMAGE_BYTES + 1)
    if not data:
        raise ValidationError(f"{field} is empty", {"param": field})
    if len(data) > MAX_UPLOAD_IMAGE_BYTES:
        raise ValidationError(
            f"{field} exceeds the {MAX_UPLOAD_IMAGE_BYTES // (1024 * 1024)} MiB limit",
            {"param": field},
        )
    return data


@router.post("/images/edits")
async def edit_image(
    ctx: Annotated[RequestContext, Depends(require_workspace_write_ctx)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    response: Response,
    image: Annotated[UploadFile, File()],
    prompt: Annotated[str, Form(min_length=1, max_length=MAX_IMAGE_PROMPT_CHARS)],
    model: Annotated[str, Form(min_length=1)],
    mask: Annotated[UploadFile | None, File()] = None,
    n: Annotated[int, Form(ge=1, le=4)] = 1,
    size: Annotated[str | None, Form()] = None,
    response_format: Annotated[Literal["b64_json", "url"], Form()] = "b64_json",
    output_format: Annotated[Literal["png", "jpeg", "webp"] | None, Form()] = None,
    background: Annotated[Literal["transparent", "opaque", "auto"] | None, Form()] = None,
    quality: Annotated[str | None, Form()] = None,
    input_fidelity: Annotated[str | None, Form()] = None,
    output_compression: Annotated[int | None, Form()] = None,
    partial_images: Annotated[int | None, Form()] = None,
    stream: Annotated[bool | None, Form()] = None,
):
    """Image editing from OpenAI's multipart form.

    The mask follows OpenAI's convention, transparent marks the region to
    edit, and is converted to SOIT's white-is-edit mask so every provider
    reads the same selection. OpenAI parameters SOIT does not send are taken
    only to be refused, as on generations.
    """

    _refuse_unsent_params(
        input_fidelity=input_fidelity,
        output_compression=output_compression,
        partial_images=partial_images,
        stream=stream,
    )
    try:
        validate_image_size(size)
    except ValueError as exc:
        raise ValidationError(str(exc), {"param": "size"}) from exc
    options = _image_options(background, output_format, quality)
    source = await _read_upload(image, field="image")
    selection: bytes | None = None
    if mask is not None:
        selection = openai_alpha_to_mask(await _read_upload(mask, field="mask"))
        assert_mask_matches_image(source, selection)

    return await _image_response(
        ImageJobRequest(
            kind="edit",
            model=model,
            prompt=prompt,
            n=n,
            size=size,
            response_format=response_format,
            output_format=output_format,
            image=source,
            mask=selection,
            extra=options,
        ),
        ctx=ctx,
        db=db,
        response=response,
        summary=f"model={model}, n={n}, mask={'yes' if selection else 'no'}",
    )
