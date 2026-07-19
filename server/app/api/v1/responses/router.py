"""Routes for the northbound Responses resource and semantic event API."""

import asyncio
import json
from dataclasses import asdict
from typing import Annotated

from ag_ui.core import RunAgentInput
from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import StreamingResponse

from app.adapters.agui.agent import PersistentAgUiAgentEmitter
from app.adapters.agui.responses import (
    AgUiInteractionProtocolAdapter,
    AgUiResponseRequestAdapter,
)
from app.api.v1.agent.dependencies import AgentStreamExecutor, get_agent_stream_executor
from app.api.v1.attachments.dependencies import get_attachment_service
from app.api.v1.observe.dependencies import get_observe_service
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.api.v1.responses.dependencies import (
    ResponseInteractionExecutor,
    get_response_interaction_executor,
    get_response_projection_coordinator,
    get_response_service,
)
from app.api.v1.responses.handlers import ResponseHandlers
from app.infra.db.pagination import PaginatedResponse
from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import RESOURCE_AGENT, require_resource_run_async
from app.kernel.runtime.attachments.service import AttachmentService
from app.kernel.runtime.db.models.threads import generate_thread_message_id
from app.kernel.runtime.responses.orchestrator import ResponseProjectionCoordinator
from app.kernel.runtime.responses.schemas import (
    ResponseCancelResult,
    ResponseCreateRequest,
    ResponseDetailRead,
    ResponseEventRead,
    ResponseRead,
    RunResponseTimelineRead,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.responses.streaming import tail_response_events
from app.kernel.runtime.tasks.service import TaskService
from app.modules.observe.application.schemas import ApprovalResolve
from app.modules.observe.application.service import ObserveService
from app.settings.settings import settings

router = APIRouter()
_background_interaction_tasks: set[asyncio.Task] = set()


class _DisconnectAwareQueue(asyncio.Queue[dict | None]):
    """Bounded live queue that releases producers when the SSE consumer leaves."""

    def __init__(self, maxsize: int) -> None:
        super().__init__(maxsize=maxsize)
        self._consumer_closed = asyncio.Event()

    def close_consumer(self) -> None:
        self._consumer_closed.set()

    async def put(self, item: dict | None) -> None:
        if self._consumer_closed.is_set():
            return
        put_task = asyncio.create_task(super().put(item))
        close_task = asyncio.create_task(self._consumer_closed.wait())
        done, _ = await asyncio.wait(
            {put_task, close_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if put_task in done:
            close_task.cancel()
            try:
                await close_task
            except asyncio.CancelledError:
                pass
            return
        put_task.cancel()
        try:
            await put_task
        except asyncio.CancelledError:
            pass


def _format_sse(event_type: str, payload: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _format_agui_sse(event_id: str, payload: dict) -> str:
    return f"id: {event_id}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _resolve_after_sequence(
    response_id: str,
    after_sequence: int | None,
    last_event_id: str | None,
) -> int:
    if not last_event_id:
        return max(0, after_sequence or 0)
    prefix, separator, raw_sequence = last_event_id.rpartition(":")
    if not separator or prefix != response_id:
        raise ValidationError("Last-Event-ID does not belong to this response")
    try:
        return max(0, int(raw_sequence))
    except ValueError as exc:
        raise ValidationError("Last-Event-ID has an invalid sequence") from exc


async def _resolve_agui_approval_resumes(
    run_input: RunAgentInput,
    *,
    agent_id: str,
    observe_service: ObserveService,
    response_service: ResponseService,
) -> tuple[
    list[dict],
    dict[str, str] | None,
    list[tuple[str, ApprovalResolve]],
]:
    if not run_input.resume:
        return [], None, []

    if not run_input.parent_run_id:
        raise ValidationError("Approval resume requires parentRunId")
    parent_interaction = response_service.get_interaction(run_input.parent_run_id)
    if parent_interaction is None or parent_interaction.status != "waiting_approval":
        raise ValidationError("Approval resume parent is not waiting for approval")
    linked_response = response_service.get_response(parent_interaction.response_id)
    if (
        linked_response.status != "running"
        or not linked_response.run_id
        or not linked_response.task_id
        or linked_response.thread_id != run_input.thread_id
        or linked_response.agent_id != agent_id
        or parent_interaction.run_id != linked_response.run_id
        or parent_interaction.thread_id != linked_response.thread_id
    ):
        raise ValidationError("Approval resume resources do not match the parent interaction")

    approvals = await observe_service.list_approvals(
        limit=200,
        offset=0,
        run_id=linked_response.run_id,
        task_id=linked_response.task_id,
    )
    approvals_by_interrupt = {
        str((item.details_json or {}).get("interrupt_id") or ""): item
        for item in approvals
        if (item.details_json or {}).get("interrupt_id")
    }
    pending_resolutions: list[tuple[str, ApprovalResolve]] = []
    prepared_entries: list[tuple[object, object, dict, str]] = []
    for entry in run_input.resume:
        approval = approvals_by_interrupt.get(entry.interrupt_id)
        if approval is None:
            raise ValidationError(f"Approval interrupt not found: {entry.interrupt_id}")
        if (
            approval.run_id != linked_response.run_id
            or approval.task_id != linked_response.task_id
            or approval.thread_id != linked_response.thread_id
            or approval.agent_id != linked_response.agent_id
        ):
            raise ValidationError("Approval interrupt resources do not match the parent interaction")

        payload = entry.payload if isinstance(entry.payload, dict) else {}
        target_status = "canceled"
        if entry.status == "resolved":
            target_status = (
                "rejected"
                if payload.get("decision") == "rejected" or payload.get("approved") is False
                else "approved"
            )
        if approval.status not in {"pending", target_status}:
            raise ValidationError(
                f"Approval {approval.id} is already resolved as {approval.status}"
            )
        pending_resolutions.append(
            (
                approval.id,
                ApprovalResolve(
                    status=target_status,
                    resolution_note="Resolved from the AG-UI approval interrupt",
                ),
            )
        )
        prepared_entries.append((entry, approval, payload, target_status))

    resolved_entries: list[dict] = []
    for entry, approval, payload, target_status in prepared_entries:
        resolved_entries.append(
            {
                "interrupt_id": entry.interrupt_id,
                "status": entry.status,
                "payload": payload,
                "approval_id": approval.id,
                "approval_status": target_status,
            }
        )
    return (
        resolved_entries,
        {
            "run_id": linked_response.run_id,
            "task_id": linked_response.task_id,
            "thread_id": linked_response.thread_id or "",
            "agent_id": linked_response.agent_id or "",
            "response_id": linked_response.id,
        },
        pending_resolutions,
    )


@router.post("", response_model=ResponseRead, status_code=status.HTTP_201_CREATED)
async def create_response(
    payload: RunAgentInput | ResponseCreateRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    projection_coordinator: ResponseProjectionCoordinator = Depends(get_response_projection_coordinator),
    execute_agent_stream: AgentStreamExecutor = Depends(get_agent_stream_executor),
    execute_interaction: ResponseInteractionExecutor = Depends(get_response_interaction_executor),
    observe_service: ObserveService = Depends(get_observe_service),
    attachment_service: AttachmentService = Depends(get_attachment_service),
):
    """Create a response resource and expose semantics for the underlying run."""

    if isinstance(payload, RunAgentInput):
        request_adapter = AgUiResponseRequestAdapter()
        try:
            attachment_ids = request_adapter.attachment_ids(payload)
            internal_payload = request_adapter.to_internal(payload)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        projection_coordinator.validate_interaction_request(internal_payload, payload.run_id)
        existing_interaction = projection_coordinator.response_service.get_interaction(
            payload.run_id
        )
        attachment_service.validate_thread_target(
            payload.thread_id,
            agent_id=internal_payload.agent_id,
        )

        resolved_resumes: list[dict] = []
        resume_execution: dict[str, str] | None = None
        pending_approval_resolutions: list[tuple[str, ApprovalResolve]] = []
        if internal_payload.agent_id:
            await require_resource_run_async(
                ctx,
                RESOURCE_AGENT,
                internal_payload.agent_id,
            )
            if existing_interaction is None:
                (
                    resolved_resumes,
                    resume_execution,
                    pending_approval_resolutions,
                ) = await _resolve_agui_approval_resumes(
                    payload,
                    agent_id=internal_payload.agent_id,
                    observe_service=observe_service,
                    response_service=projection_coordinator.response_service,
                )
        else:
            if payload.resume:
                raise ValidationError(
                    "AG-UI resume is only supported for published Agent mode"
                )
            attachments = await attachment_service.resolve_for_message(
                attachment_ids,
                thread_id=payload.thread_id,
            )
            internal_payload = request_adapter.to_internal(
                payload,
                attachments=attachments,
            )

        agent_inputs: dict | None = None
        assistant_message_id: str | None = None
        if internal_payload.agent_id:
            agent_inputs = request_adapter.to_agent_inputs(payload)
            assistant_message_id = generate_thread_message_id()
            agent_inputs["_agui_context"]["assistant_message_id"] = assistant_message_id
            if attachment_ids:
                agent_inputs["_attachment_ids"] = attachment_ids
            if resolved_resumes:
                agent_inputs["_agui_resume"] = resolved_resumes
                agent_inputs["_resume_execution"] = resume_execution

        execution_json = {
            "mode": "agent" if internal_payload.agent_id else "direct",
            "agent_id": internal_payload.agent_id,
            "agent_inputs": agent_inputs or {},
            "assistant_message_id": assistant_message_id,
            "payload": internal_payload.model_dump(mode="json"),
        }

        request_hash = str(internal_payload.metadata.get("request_hash") or payload.run_id)

        async def generate_persisted(
            response_id: str,
            *,
            interaction_id: str | None = None,
        ):
            async for item in tail_response_events(
                projection_coordinator.response_service,
                response_id,
                interaction_id=interaction_id,
            ):
                if item["kind"] == "heartbeat":
                    yield ": heartbeat\n\n"
                elif item["kind"] == "done":
                    return
                else:
                    event = item["event"]
                    yield _format_agui_sse(
                        f"{event.response_id}:{event.sequence}",
                        event.payload_json,
                    )

        async def generate_claimed_interaction(interaction_id: str):
            while True:
                projection_coordinator.response_service.db.expire_all()
                interaction = projection_coordinator.response_service.get_interaction(
                    interaction_id
                )
                if interaction is None:
                    raise ValidationError("Claimed interaction no longer exists")
                if interaction.response_id:
                    async for chunk in generate_persisted(
                        interaction.response_id,
                        interaction_id=interaction.interaction_id,
                    ):
                        yield chunk
                    return
                if interaction.status in {"failed", "canceled"}:
                    if interaction.status == "failed":
                        yield _format_agui_sse(
                            "",
                            {
                                "type": "RUN_ERROR",
                                "code": "interaction_execution_failed",
                                "message": "Response execution failed",
                            },
                        )
                    return
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.1)

        response_service = projection_coordinator.response_service
        if pending_approval_resolutions:
            if response_service.db is None or observe_service.db is not response_service.db:
                raise ValidationError(
                    "Approval resume requires one atomic database transaction"
                )
            try:
                response_service.claim_interaction_resume(
                    parent_interaction_id=payload.parent_run_id or "",
                    resume_interaction_id=payload.run_id,
                )
                await observe_service.resolve_approvals(
                    pending_approval_resolutions,
                    commit=False,
                )
                _, owns_claim = response_service.claim_interaction(
                    interaction_id=payload.run_id,
                    parent_interaction_id=payload.parent_run_id,
                    thread_id=payload.thread_id,
                    request_hash=request_hash,
                    execution_json=execution_json,
                    request_context_json=asdict(ctx),
                    commit=False,
                )
                response_service.db.commit()
            except Exception:
                response_service.db.rollback()
                raise
        else:
            _, owns_claim = response_service.claim_interaction(
                interaction_id=payload.run_id,
                parent_interaction_id=payload.parent_run_id,
                thread_id=payload.thread_id,
                request_hash=request_hash,
                execution_json=execution_json,
                request_context_json=asdict(ctx),
            )
        if not owns_claim:
            return StreamingResponse(
                generate_claimed_interaction(payload.run_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        if not settings.response_interaction_inline_execution:
            return StreamingResponse(
                generate_claimed_interaction(payload.run_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        if internal_payload.agent_id:
            if agent_inputs is None or assistant_message_id is None:
                raise ValidationError("Agent interaction execution payload is incomplete")
            queue = _DisconnectAwareQueue(maxsize=256)

            async def run_agent_interaction() -> None:
                emitter: PersistentAgUiAgentEmitter | None = None

                async def emit_agent_event(event: str, data: dict) -> None:
                    if emitter is not None:
                        await emitter(event, data)

                async def bind_response(response, response_service) -> None:
                    nonlocal emitter
                    emitter = PersistentAgUiAgentEmitter(
                        response_service=response_service,
                        interaction_id=payload.run_id,
                        parent_interaction_id=payload.parent_run_id,
                        thread_id=payload.thread_id,
                        assistant_message_id=assistant_message_id,
                        queue=queue,
                    )
                    await emitter.bind_response(
                        response,
                        request_hash=str(internal_payload.metadata.get("request_hash") or ""),
                    )

                try:
                    result = await execute_agent_stream(
                        internal_payload.agent_id or "",
                        agent_inputs,
                        emit_agent_event,
                        bind_response,
                        {
                            "protocol": "ag-ui",
                            "protocol_version": "0.1.19",
                            "interaction_id": payload.run_id,
                            "parent_interaction_id": payload.parent_run_id,
                        },
                    )
                    if emitter is not None and not emitter.terminal_emitted:
                        if result.get("status") == "waiting_approval":
                            await emitter.interrupt(result)
                        else:
                            await emitter.complete(result)
                except Exception as exc:
                    if emitter is not None:
                        if not emitter.terminal_emitted:
                            await emitter.fail(exc)
                    else:
                        projection_coordinator.response_service.update_interaction_status(
                            payload.run_id,
                            "failed",
                        )
                        await queue.put(
                            {
                                "id": "",
                                "data": {
                                    "type": "RUN_ERROR",
                                    "code": getattr(exc, "code", None) or "agent_execution_failed",
                                    "message": "Agent execution failed",
                                },
                            }
                        )
                finally:
                    if emitter is not None:
                        await emitter.done()
                    else:
                        await queue.put(None)

            task = asyncio.create_task(run_agent_interaction())
            _background_interaction_tasks.add(task)
            task.add_done_callback(_background_interaction_tasks.discard)

            async def generate_agent():
                try:
                    while True:
                        item = await queue.get()
                        if item is None:
                            break
                        if item["id"]:
                            yield _format_agui_sse(item["id"], item["data"])
                        else:
                            yield f"data: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
                finally:
                    queue.close_consumer()

            return StreamingResponse(
                generate_agent(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        queue = _DisconnectAwareQueue(maxsize=256)

        async def run_direct_interaction() -> None:
            protocol = AgUiInteractionProtocolAdapter()
            try:
                async for item in execute_interaction(
                    internal_payload,
                    interaction_id=payload.run_id,
                    parent_interaction_id=payload.parent_run_id,
                    protocol=protocol,
                ):
                    await queue.put(item)
            except Exception as exc:
                error_code = (
                    getattr(exc, "code", None) or "response_execution_failed"
                )
                terminal = protocol.run_error(
                    code=error_code,
                    message="Response execution failed",
                )
                stored = projection_coordinator.response_service.fail_interaction_execution(
                    payload.run_id,
                    error_code=error_code,
                    error_message="Response execution failed",
                    terminal_event=terminal.payload,
                    source=protocol.source,
                    protocol_version=protocol.protocol_version,
                )
                await queue.put(
                    {
                        "id": (
                            f"{stored.response_id}:{stored.sequence}"
                            if stored is not None
                            else ""
                        ),
                        "data": stored.payload_json if stored is not None else terminal.payload,
                    }
                )
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_direct_interaction())
        _background_interaction_tasks.add(task)
        task.add_done_callback(_background_interaction_tasks.discard)

        async def generate_agui():
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    if item["id"]:
                        yield _format_agui_sse(item["id"], item["data"])
                    else:
                        yield f"data: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
            finally:
                queue.close_consumer()

        return StreamingResponse(
            generate_agui(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    response = await projection_coordinator.execute(payload)
    return ResponseRead.model_validate(response)


@router.get("/by-run/{run_id}", response_model=RunResponseTimelineRead)
async def get_run_response_timeline(
    run_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """Read response semantic projections grouped under a run."""

    handlers = ResponseHandlers(service)
    return await handlers.get_run_timeline(ctx, run_id)


@router.get("/{response_id}", response_model=ResponseRead)
async def get_response(
    response_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """Read a response resource projection."""

    handlers = ResponseHandlers(service)
    return await handlers.get_response(ctx, response_id)


@router.get("/{response_id}/detail", response_model=ResponseDetailRead)
async def get_response_detail(
    response_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """Read a response projection with semantic events and tool-call projections."""

    handlers = ResponseHandlers(service)
    return await handlers.get_response_detail(ctx, response_id)


@router.get("/{response_id}/events", response_model=PaginatedResponse[ResponseEventRead])
async def list_response_events(
    response_id: str,
    page_token: str | None = None,
    page_size: int = 100,
    after_sequence: int | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """List persisted response semantic events."""

    handlers = ResponseHandlers(service)
    return await handlers.list_response_events(
        ctx,
        response_id,
        page_token=page_token,
        page_size=page_size,
        after_sequence=after_sequence,
    )


@router.get(
    "/{response_id}/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "text/event-stream": {"schema": {"type": "string"}},
            }
        }
    },
)
async def stream_response_events(
    response_id: str,
    after_sequence: int | None = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """Replay persisted response events as SSE."""

    del ctx

    cursor = _resolve_after_sequence(response_id, after_sequence, last_event_id)
    response = service.get_response(response_id)
    is_agui = (response.metadata_json or {}).get("protocol") == "ag-ui"

    async def generate():
        async for item in tail_response_events(service, response_id, after_sequence=cursor):
            if item["kind"] == "heartbeat":
                yield ": heartbeat\n\n"
                continue
            if item["kind"] == "done":
                if not is_agui:
                    yield "data: [DONE]\n\n"
                return
            event = item["event"]
            if event.source == "ag-ui":
                yield _format_agui_sse(f"{event.response_id}:{event.sequence}", event.payload_json)
            else:
                yield _format_sse(event.type, event.payload_json)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{response_id}/cancel", response_model=ResponseCancelResult)
async def cancel_response(
    response_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ResponseService = Depends(get_response_service),
):
    """Cancel a response resource projection."""

    response = service.get_response(response_id)
    if response.metadata_json.get("protocol") == "ag-ui":
        was_active = response.status not in {"succeeded", "failed", "canceled"}
        interaction_id = str(response.metadata_json.get("interaction_id") or "")
        active_interaction_id = interaction_id
        interaction = service.get_interaction(interaction_id) if interaction_id else None
        if (
            interaction is not None
            and interaction.status == "resuming"
            and interaction.resume_interaction_id
        ):
            active_interaction_id = interaction.resume_interaction_id
        response = service.cancel_response(response_id, emit_event=False)
        if was_active and response.status == "canceled" and active_interaction_id:
            if response.task_id:
                TaskService(service.db, ctx).cancel_task(task_id=response.task_id)
            if interaction_id and interaction_id != active_interaction_id:
                service.update_interaction_status(interaction_id, "canceled")
            service.update_interaction_status(active_interaction_id, "canceled")
            protocol = AgUiInteractionProtocolAdapter()
            events = service.list_response_events(
                response.id,
                limit=10_000,
                offset=0,
                interaction_id=active_interaction_id,
            )
            for message_id in protocol.active_text_message_ids(events):
                text_end = protocol.text_ended(message_id=message_id)
                stored = service.append_event(
                    response=response,
                    event_type=text_end.type,
                    payload=text_end.payload,
                    source=protocol.source,
                    protocol_version=protocol.protocol_version,
                    interaction_id=active_interaction_id,
                )
                service.publish_persisted_event(stored)
            event = protocol.run_cancelled(
                thread_id=response.thread_id,
                interaction_id=active_interaction_id,
            )
            stored = service.append_event(
                response=response,
                event_type=event.type,
                payload=event.payload,
                source=protocol.source,
                protocol_version=protocol.protocol_version,
                interaction_id=active_interaction_id,
            )
            service.publish_persisted_event(stored)
        return ResponseCancelResult(
            response=ResponseRead.model_validate(response),
            action="cancel",
        )

    handlers = ResponseHandlers(service)
    return await handlers.cancel_response(ctx, response_id)
