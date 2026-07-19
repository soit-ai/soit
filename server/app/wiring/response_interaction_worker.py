"""Durable worker for claimed AG-UI response interactions."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.adapters.agui.agent import PersistentAgUiAgentEmitter
from app.adapters.agui.responses import AgUiInteractionProtocolAdapter
from app.infra.db.session import get_db_sync
from app.kernel.commons.errors import ConflictError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.responses import ResponseInteraction
from app.kernel.runtime.responses.schemas import ResponseCreateRequest
from app.kernel.runtime.tasks.service import TaskService
from app.settings.settings import settings
from app.wiring.services import (
    build_agent_service,
    build_response_projection_coordinator,
)

logger = logging.getLogger(__name__)


class GlobalResponseInteractionWorker:
    """Lease and execute persisted interaction jobs across API restarts."""

    def __init__(
        self,
        db_factory: Callable[[], Session] = get_db_sync,
        *,
        worker_id: str | None = None,
        lease_seconds: int | None = None,
        heartbeat_interval_seconds: float | None = None,
    ) -> None:
        self.db_factory = db_factory
        self.worker_id = worker_id or f"response-worker-{uuid.uuid4()}"
        self.lease_seconds = max(
            30,
            int(lease_seconds or settings.response_interaction_lease_seconds),
        )
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

    def _claim_next(self, db: Session) -> ResponseInteraction | None:
        now = utc_now()
        query = (
            select(ResponseInteraction)
            .where(
                or_(
                    ResponseInteraction.status == "queued",
                    and_(
                        ResponseInteraction.status == "running",
                        ResponseInteraction.lease_expires_at.is_not(None),
                        ResponseInteraction.lease_expires_at < now,
                    ),
                )
            )
            .order_by(ResponseInteraction.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = db.execute(query).scalars().first()
        if result is None:
            return None
        result.status = "running"
        result.lease_owner = self.worker_id
        result.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
        result.attempt_count = int(result.attempt_count or 0) + 1
        result.updated_at = now
        db.add(result)
        db.commit()
        db.refresh(result)
        return result

    async def _heartbeat(
        self,
        interaction_pk: str,
        interaction_id: str,
        attempt_count: int,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        interval = self.heartbeat_interval_seconds or max(
            10.0,
            self.lease_seconds / 3,
        )
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                db: Session | None = None
                try:
                    db = self.db_factory()
                    result = db.execute(
                        update(ResponseInteraction)
                        .where(
                            ResponseInteraction.id == interaction_pk,
                            ResponseInteraction.lease_owner == self.worker_id,
                            ResponseInteraction.attempt_count == attempt_count,
                            ResponseInteraction.status == "running",
                        )
                        .values(
                            lease_expires_at=utc_now()
                            + timedelta(seconds=self.lease_seconds),
                            updated_at=utc_now(),
                        )
                    )
                    db.commit()
                    if result.rowcount != 1:
                        current = db.get(ResponseInteraction, interaction_pk)
                        owns_terminal = (
                            current is not None
                            and current.lease_owner == self.worker_id
                            and current.attempt_count == attempt_count
                            and current.status != "running"
                        )
                        if not owns_terminal:
                            logger.warning(
                                "Durable response interaction lease was lost",
                                extra={"interaction_id": interaction_id},
                            )
                            lease_lost.set()
                        return
                except Exception:
                    logger.exception(
                        "Durable response interaction heartbeat failed",
                        extra={"interaction_id": interaction_id},
                    )
                finally:
                    if db is not None:
                        db.close()

    def _assert_lease(self, interaction_pk: str, attempt_count: int) -> None:
        db = self.db_factory()
        try:
            current = db.get(ResponseInteraction, interaction_pk)
            if (
                current is None
                or current.lease_owner != self.worker_id
                or current.attempt_count != attempt_count
            ):
                raise ConflictError("Interaction execution lease was lost")
        finally:
            db.close()

    @staticmethod
    def _context(interaction: ResponseInteraction) -> RequestContext:
        data = dict(interaction.request_context_json or {})
        return RequestContext(**data)

    async def _terminalize_orphan(
        self,
        db: Session,
        interaction: ResponseInteraction,
        ctx: RequestContext,
    ) -> None:
        coordinator = build_response_projection_coordinator(db=db, ctx=ctx)
        service = coordinator.response_service
        response = coordinator.response_service.get_response(str(interaction.response_id))
        protocol = AgUiInteractionProtocolAdapter()
        events = service.list_response_events(
            response.id,
            limit=10_000,
            offset=0,
            interaction_id=interaction.interaction_id,
        )
        has_terminal_event = any(
            event.type in {"RUN_FINISHED", "RUN_ERROR"} for event in events
        )
        if not has_terminal_event:
            for message_id in protocol.active_text_message_ids(events):
                text_end = protocol.text_ended(message_id=message_id)
                stored = service.append_event(
                    response=response,
                    event_type=text_end.type,
                    payload=text_end.payload,
                    source=protocol.source,
                    protocol_version=protocol.protocol_version,
                    interaction_id=interaction.interaction_id,
                )
                service.publish_persisted_event(stored)

        if response.status == "succeeded":
            service.update_interaction_status(interaction.interaction_id, "succeeded")
            if not has_terminal_event:
                stored = service.append_event(
                    response=response,
                    event_type="RUN_FINISHED",
                    payload=protocol.run_finished(
                        thread_id=interaction.thread_id,
                        interaction_id=interaction.interaction_id,
                        result={
                            "status": "succeeded",
                            "responseId": response.id,
                            "executionRunId": response.run_id,
                            "taskId": response.task_id,
                        },
                    ).payload,
                    source=protocol.source,
                    protocol_version=protocol.protocol_version,
                    interaction_id=interaction.interaction_id,
                )
                service.publish_persisted_event(stored)
            return

        if response.status == "canceled":
            service.update_interaction_status(interaction.interaction_id, "canceled")
            if not has_terminal_event:
                stored = service.append_event(
                    response=response,
                    event_type="RUN_FINISHED",
                    payload=protocol.run_cancelled(
                        thread_id=interaction.thread_id,
                        interaction_id=interaction.interaction_id,
                    ).payload,
                    source=protocol.source,
                    protocol_version=protocol.protocol_version,
                    interaction_id=interaction.interaction_id,
                )
                service.publish_persisted_event(stored)
            return

        if response.status != "failed":
            response = service.fail_response(
                response=response,
                error_code="interaction_worker_lost",
                error_message="Response execution was interrupted",
                failed_event_type=None,
            )
        if response.run_id:
            service.trace_writer.update_run_status(
                response.run_id,
                "failed",
                error_code="interaction_worker_lost",
                error_message="Response execution was interrupted",
            )
        if response.task_id:
            task_service = TaskService(db, ctx)
            task = task_service.get_task(response.task_id)
            if task.status not in {"succeeded", "failed", "canceled", "expired"}:
                task_service.transition_task(
                    task_id=task.id,
                    status="failed",
                    error_code="interaction_worker_lost",
                    error_message="Response execution was interrupted",
                )
        service.update_interaction_status(interaction.interaction_id, "failed")
        if not has_terminal_event:
            stored = service.append_event(
                response=response,
                event_type="RUN_ERROR",
                payload=protocol.run_error(
                    code="interaction_worker_lost",
                    message="Response execution was interrupted",
                ).payload,
                source=protocol.source,
                protocol_version=protocol.protocol_version,
                interaction_id=interaction.interaction_id,
            )
            service.publish_persisted_event(stored)

    async def _terminalize_prebind_resume_failure(
        self,
        db: Session,
        interaction: ResponseInteraction,
        ctx: RequestContext,
        resume_execution: dict,
    ) -> None:
        coordinator = build_response_projection_coordinator(db=db, ctx=ctx)
        service = coordinator.response_service
        response = service.get_response(str(resume_execution.get("response_id") or ""))
        canceled = response.status == "canceled"
        if response.status not in {"succeeded", "failed", "canceled"}:
            response = service.fail_response(
                response=response,
                error_code="agent_execution_failed",
                error_message="Agent execution failed",
                failed_event_type=None,
            )
        run_id = str(resume_execution.get("run_id") or response.run_id or "")
        if run_id and not canceled:
            service.trace_writer.update_run_status(
                run_id,
                "failed",
                error_code="agent_execution_failed",
                error_message="Agent execution failed",
            )
        task_id = str(resume_execution.get("task_id") or response.task_id or "")
        if task_id:
            task_service = TaskService(db, ctx)
            task = task_service.get_task(task_id)
            if task.status not in {"succeeded", "failed", "canceled", "expired"}:
                if canceled:
                    task_service.cancel_task(task_id=task.id)
                else:
                    task_service.transition_task(
                        task_id=task.id,
                        status="failed",
                        error_code="agent_execution_failed",
                        error_message="Agent execution failed",
                    )
        service.create_interaction(
            interaction_id=interaction.interaction_id,
            parent_interaction_id=interaction.parent_interaction_id,
            response=response,
            request_hash=interaction.request_hash,
        )
        terminal_status = "canceled" if canceled else "failed"
        service.update_interaction_status(interaction.interaction_id, terminal_status)
        if interaction.parent_interaction_id:
            service.update_interaction_status(
                interaction.parent_interaction_id,
                terminal_status,
            )
        protocol = AgUiInteractionProtocolAdapter()
        events = service.list_response_events(
            response.id,
            limit=10_000,
            offset=0,
            interaction_id=interaction.interaction_id,
        )
        has_terminal_event = any(
            event.type in {"RUN_FINISHED", "RUN_ERROR"} for event in events
        )
        if not has_terminal_event:
            for message_id in protocol.active_text_message_ids(events):
                text_end = protocol.text_ended(message_id=message_id)
                stored = service.append_event(
                    response=response,
                    event_type=text_end.type,
                    payload=text_end.payload,
                    source=protocol.source,
                    protocol_version=protocol.protocol_version,
                    interaction_id=interaction.interaction_id,
                )
                service.publish_persisted_event(stored)
            event = (
                protocol.run_cancelled(
                    thread_id=interaction.thread_id,
                    interaction_id=interaction.interaction_id,
                )
                if canceled
                else protocol.run_error(
                    code="agent_execution_failed",
                    message="Agent execution failed",
                )
            )
            stored = service.append_event(
                response=response,
                event_type=event.type,
                payload=event.payload,
                source=protocol.source,
                protocol_version=protocol.protocol_version,
                interaction_id=interaction.interaction_id,
            )
            service.publish_persisted_event(stored)
        db.commit()

    async def _execute(self, db: Session, interaction: ResponseInteraction) -> None:
        ctx = self._context(interaction)
        job = dict(interaction.execution_json or {})
        if interaction.response_id:
            await self._terminalize_orphan(db, interaction, ctx)
            return
        mode = str(job.get("mode") or "")
        if mode == "direct":
            coordinator = build_response_projection_coordinator(db=db, ctx=ctx)
            payload = ResponseCreateRequest.model_validate(job.get("payload") or {})
            stream = coordinator.execute_interaction_stream(
                payload,
                interaction_id=interaction.interaction_id,
                parent_interaction_id=interaction.parent_interaction_id,
                protocol=AgUiInteractionProtocolAdapter(),
            )
            iterator = aiter(stream)
            while True:
                self._assert_lease(interaction.id, interaction.attempt_count)
                try:
                    await anext(iterator)
                except StopAsyncIteration:
                    break
            db.commit()
            return
        if mode != "agent":
            raise ValueError("Interaction job mode is invalid")

        service = build_agent_service(db=db, ctx=ctx)
        emitter: PersistentAgUiAgentEmitter | None = None

        async def emit_agent_event(event: str, data: dict) -> None:
            if emitter is not None:
                await emitter(event, data)

        async def bind_response(response, response_service) -> None:
            nonlocal emitter
            emitter = PersistentAgUiAgentEmitter(
                response_service=response_service,
                interaction_id=interaction.interaction_id,
                parent_interaction_id=interaction.parent_interaction_id,
                thread_id=interaction.thread_id,
                assistant_message_id=job.get("assistant_message_id"),
                lease_guard=lambda: self._assert_lease(
                    interaction.id,
                    interaction.attempt_count,
                ),
            )
            await emitter.bind_response(
                response,
                request_hash=interaction.request_hash,
            )

        try:
            result = await service.execute_agent_streaming(
                str(job.get("agent_id") or ""),
                dict(job.get("agent_inputs") or {}),
                emit_agent_event,
                on_response_started=bind_response,
                response_metadata={
                    "protocol": "ag-ui",
                    "protocol_version": "0.1.19",
                    "interaction_id": interaction.interaction_id,
                    "parent_interaction_id": interaction.parent_interaction_id,
                },
            )
        except Exception as exc:
            if emitter is not None:
                await emitter("agent.interaction.failed", {"code": getattr(exc, "code", None)})
            else:
                resume_execution = dict(
                    (job.get("agent_inputs") or {}).get("_resume_execution") or {}
                )
                if resume_execution:
                    await self._terminalize_prebind_resume_failure(
                        db,
                        interaction,
                        ctx,
                        resume_execution,
                    )
            raise
        if emitter is None:
            raise RuntimeError("Agent execution did not bind a Response")
        await emitter("agent.interaction.finished", {"result": result})
        db.commit()

    async def run_once(self) -> ResponseInteraction | None:
        db = self.db_factory()
        interaction: ResponseInteraction | None = None
        heartbeat_stop = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat_task: asyncio.Task | None = None
        execute_task: asyncio.Task | None = None
        lease_wait_task: asyncio.Task | None = None
        try:
            interaction = self._claim_next(db)
            if interaction is None:
                return None
            heartbeat_task = asyncio.create_task(
                self._heartbeat(
                    interaction.id,
                    interaction.interaction_id,
                    interaction.attempt_count,
                    heartbeat_stop,
                    lease_lost,
                )
            )
            try:
                execute_task = asyncio.create_task(self._execute(db, interaction))
                lease_wait_task = asyncio.create_task(lease_lost.wait())
                done, _ = await asyncio.wait(
                    {execute_task, lease_wait_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if lease_wait_task in done and lease_lost.is_set():
                    execute_task.cancel()
                    try:
                        await execute_task
                    except asyncio.CancelledError:
                        pass
                    db.rollback()
                    return interaction
                lease_wait_task.cancel()
                try:
                    await lease_wait_task
                except asyncio.CancelledError:
                    pass
                await execute_task
            except Exception:
                logger.exception(
                    "Durable response interaction failed",
                    extra={"interaction_id": interaction.interaction_id},
                )
                db.rollback()
                db.expire_all()
                current = db.get(ResponseInteraction, interaction.id)
                if (
                    current is not None
                    and current.lease_owner == self.worker_id
                    and current.attempt_count == interaction.attempt_count
                    and current.status
                    not in {
                        "succeeded",
                        "failed",
                        "canceled",
                        "waiting_approval",
                    }
                ):
                    if current.response_id:
                        await self._terminalize_orphan(
                            db,
                            current,
                            self._context(current),
                        )
                    else:
                        current.status = "failed"
                        current.lease_owner = None
                        current.lease_expires_at = None
                        current.updated_at = utc_now()
                        db.add(current)
                    db.commit()
            return interaction
        finally:
            heartbeat_stop.set()
            for task in (execute_task, lease_wait_task):
                if task is not None and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            if heartbeat_task is not None:
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Durable response interaction heartbeat stopped unexpectedly",
                        extra={
                            "interaction_id": (
                                interaction.interaction_id if interaction else None
                            )
                        },
                    )
            db.close()

    async def run_loop(self, poll_interval: float = 0.25) -> None:
        while True:
            try:
                result = await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Durable response interaction poll failed")
                await asyncio.sleep(max(0.05, poll_interval))
                continue
            if result is None:
                await asyncio.sleep(max(0.05, poll_interval))
