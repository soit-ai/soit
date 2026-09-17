"""Durable worker for claimed AG-UI response interactions."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.agui.agent import PersistentAgUiAgentEmitter
from app.adapters.agui.responses import AgUiInteractionProtocolAdapter
from app.infra.db.session import get_async_session_local
from app.kernel.commons.errors import ConflictError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.common import lease
from app.kernel.runtime.db.models.responses import ResponseInteraction
from app.kernel.runtime.responses.schemas import ResponseCreateRequest
from app.kernel.runtime.tasks.service import TaskService
from app.settings.settings import settings
from app.wiring.services import (
    build_agent_service,
    build_response_projection_coordinator,
)

logger = logging.getLogger(__name__)


def _default_session_factory() -> AsyncSession:
    return get_async_session_local()()


def bounded_concurrency(requested: int) -> int:
    """Cap in-flight executions to what one process's connection pool sustains.

    An execution holds no connection while it waits on the model, but every
    other phase of it does, and the claim loop and each lease heartbeat need
    one too. The load ladder put 64 executions on a 30-connection pool: the
    heartbeats starved and throughput fell below 24 in flight. Four
    connections are kept back for the loop and heartbeats.
    """
    ceiling = max(1, settings.database_pool_size + settings.database_max_overflow - 4)
    requested = max(1, int(requested or 1))
    if requested > ceiling:
        logger.warning(
            "Response worker concurrency %s exceeds what the pool sustains; using %s",
            requested,
            ceiling,
            extra={"pool_size": settings.database_pool_size, "max_overflow": settings.database_max_overflow},
        )
        return ceiling
    return requested


class GlobalResponseInteractionWorker:
    """Lease and execute persisted interaction jobs across API restarts."""

    def __init__(
        self,
        db_factory: Callable[[], AsyncSession] | None = None,
        *,
        worker_id: str | None = None,
        lease_seconds: int | None = None,
        heartbeat_interval_seconds: float | None = None,
    ) -> None:
        self.db_factory = db_factory or _default_session_factory
        self.worker_id = worker_id or f"response-worker-{uuid.uuid4()}"
        self.lease_seconds = lease.normalize_lease_seconds(
            lease_seconds or settings.response_interaction_lease_seconds
        )
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

    async def _claim_next(self, db: AsyncSession) -> ResponseInteraction | None:
        return await lease.claim_next(
            db,
            ResponseInteraction,
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )

    async def _heartbeat(
        self,
        interaction_pk: str,
        interaction_id: str,
        attempt_count: int,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        await lease.LeaseHeartbeat(
            self.db_factory,
            ResponseInteraction,
            interaction_pk,
            worker_id=self.worker_id,
            attempt_count=attempt_count,
            lease_seconds=self.lease_seconds,
            interval_seconds=self.heartbeat_interval_seconds,
            log_label=f"Durable response interaction lease {interaction_id}",
        ).run(stop, lease_lost)

    async def _assert_lease(self, db: AsyncSession, interaction_pk: str, attempt_count: int) -> None:
        """Fail the execution if another worker now owns the interaction.

        This reads on the execution's own session. A separate session would
        need a second pooled connection while the execution's transaction
        holds its first, so past pool/2 executions every one of them would
        wait on the others: the load ladder found exactly that deadlock.

        Reading our own session means seeing our own staged writes, and the
        terminal transition clears ``lease_owner`` before the final events
        are persisted. A takeover is therefore judged by ``attempt_count``,
        which only a reclaim bumps; a cleared owner with our attempt count
        is our own release, not a loss.
        """
        current = await db.get(ResponseInteraction, interaction_pk)
        if current is not None:
            await db.refresh(current)
        owned = (
            current is not None
            and current.attempt_count == attempt_count
            and current.lease_owner in (self.worker_id, None)
        )
        if not owned:
            raise ConflictError("Interaction execution lease was lost")

    @staticmethod
    def _context(interaction: ResponseInteraction) -> RequestContext:
        data = dict(interaction.request_context_json or {})
        return RequestContext(**data)

    async def _terminalize_orphan(
        self,
        db: AsyncSession,
        interaction: ResponseInteraction,
        ctx: RequestContext,
    ) -> None:
        coordinator = build_response_projection_coordinator(db=db, ctx=ctx)
        service = coordinator.response_service
        response = await coordinator.response_service.get_response(str(interaction.response_id))
        protocol = AgUiInteractionProtocolAdapter()
        events = await service.list_response_events(
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
                stored = await service.append_event(
                    response=response,
                    event_type=text_end.type,
                    payload=text_end.payload,
                    source=protocol.source,
                    protocol_version=protocol.protocol_version,
                    interaction_id=interaction.interaction_id,
                )
                await service.publish_persisted_event(stored)

        if response.status == "succeeded":
            await service.update_interaction_status(interaction.interaction_id, "succeeded")
            if not has_terminal_event:
                stored = await service.append_event(
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
                await service.publish_persisted_event(stored)
            return

        if response.status == "canceled":
            await service.update_interaction_status(interaction.interaction_id, "canceled")
            if not has_terminal_event:
                stored = await service.append_event(
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
                await service.publish_persisted_event(stored)
            return

        if response.status != "failed":
            response = await service.fail_response(
                response=response,
                error_code="interaction_worker_lost",
                error_message="Response execution was interrupted",
                failed_event_type=None,
            )
        if response.run_id:
            await service.trace_writer.update_run_status(
                response.run_id,
                "failed",
                error_code="interaction_worker_lost",
                error_message="Response execution was interrupted",
            )
        if response.task_id:
            task_service = TaskService(db, ctx)
            task = await task_service.get_task(response.task_id)
            if task.status not in {"succeeded", "failed", "canceled", "expired"}:
                await task_service.transition_task(
                    task_id=task.id,
                    status="failed",
                    error_code="interaction_worker_lost",
                    error_message="Response execution was interrupted",
                )
        await service.update_interaction_status(interaction.interaction_id, "failed")
        if not has_terminal_event:
            stored = await service.append_event(
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
            await service.publish_persisted_event(stored)

    async def _terminalize_prebind_resume_failure(
        self,
        db: AsyncSession,
        interaction: ResponseInteraction,
        ctx: RequestContext,
        resume_execution: dict,
    ) -> None:
        coordinator = build_response_projection_coordinator(db=db, ctx=ctx)
        service = coordinator.response_service
        response = await service.get_response(str(resume_execution.get("response_id") or ""))
        canceled = response.status == "canceled"
        if response.status not in {"succeeded", "failed", "canceled"}:
            response = await service.fail_response(
                response=response,
                error_code="agent_execution_failed",
                error_message="Agent execution failed",
                failed_event_type=None,
            )
        run_id = str(resume_execution.get("run_id") or response.run_id or "")
        if run_id and not canceled:
            await service.trace_writer.update_run_status(
                run_id,
                "failed",
                error_code="agent_execution_failed",
                error_message="Agent execution failed",
            )
        task_id = str(resume_execution.get("task_id") or response.task_id or "")
        if task_id:
            task_service = TaskService(db, ctx)
            task = await task_service.get_task(task_id)
            if task.status not in {"succeeded", "failed", "canceled", "expired"}:
                if canceled:
                    await task_service.cancel_task(task_id=task.id)
                else:
                    await task_service.transition_task(
                        task_id=task.id,
                        status="failed",
                        error_code="agent_execution_failed",
                        error_message="Agent execution failed",
                    )
        await service.create_interaction(
            interaction_id=interaction.interaction_id,
            parent_interaction_id=interaction.parent_interaction_id,
            response=response,
            request_hash=interaction.request_hash,
        )
        terminal_status = "canceled" if canceled else "failed"
        await service.update_interaction_status(interaction.interaction_id, terminal_status)
        if interaction.parent_interaction_id:
            await service.update_interaction_status(
                interaction.parent_interaction_id,
                terminal_status,
            )
        protocol = AgUiInteractionProtocolAdapter()
        events = await service.list_response_events(
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
                stored = await service.append_event(
                    response=response,
                    event_type=text_end.type,
                    payload=text_end.payload,
                    source=protocol.source,
                    protocol_version=protocol.protocol_version,
                    interaction_id=interaction.interaction_id,
                )
                await service.publish_persisted_event(stored)
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
            stored = await service.append_event(
                response=response,
                event_type=event.type,
                payload=event.payload,
                source=protocol.source,
                protocol_version=protocol.protocol_version,
                interaction_id=interaction.interaction_id,
            )
            await service.publish_persisted_event(stored)
        await db.commit()

    async def _execute(self, db: AsyncSession, interaction: ResponseInteraction) -> None:
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
                await self._assert_lease(db, interaction.id, interaction.attempt_count)
                try:
                    await anext(iterator)
                except StopAsyncIteration:
                    break
            await db.commit()
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
                    db,
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
        await db.commit()

    async def claim(self) -> ResponseInteraction | None:
        """Claim the next ready interaction on a session of its own.

        The claim commits, so the row it returns is detached and can be
        executed on any session; that is what lets one poller feed many
        concurrent executions.
        """
        db = self.db_factory()
        try:
            return await self._claim_next(db)
        finally:
            await db.close()

    async def run_once(self) -> ResponseInteraction | None:
        interaction = await self.claim()
        if interaction is None:
            return None
        return await self.execute_claimed(interaction)

    async def execute_claimed(self, interaction: ResponseInteraction) -> ResponseInteraction:
        """Execute a claimed interaction, terminalizing it if execution fails."""
        db = self.db_factory()
        heartbeat_stop = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat_task: asyncio.Task | None = None
        execute_task: asyncio.Task | None = None
        lease_wait_task: asyncio.Task | None = None
        try:
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
                    await db.rollback()
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
                await db.rollback()
                current = await db.get(ResponseInteraction, interaction.id)
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
                    await db.commit()
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
                        extra={"interaction_id": interaction.interaction_id},
                    )
            await db.close()

    async def run_loop(self, poll_interval: float = 0.25, concurrency: int = 1) -> None:
        """Claim from one loop and execute up to ``concurrency`` interactions at once.

        One poller per process keeps idle polling at one query per interval
        however many executions may run, and a claim that finds work claims
        again at once, so a backlog drains as fast as slots free up rather
        than one row per interval. Executions mostly wait on the model with
        their transaction committed, so the slot count is not bounded by the
        connection pool.
        """
        poll_interval = max(0.05, poll_interval)
        slots = asyncio.Semaphore(max(1, int(concurrency or 1)))
        in_flight: set[asyncio.Task] = set()

        async def execute(interaction: ResponseInteraction) -> None:
            try:
                await self.execute_claimed(interaction)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Durable response interaction execution failed outside recovery",
                    extra={"interaction_id": interaction.interaction_id},
                )
            finally:
                slots.release()

        try:
            while True:
                await slots.acquire()
                try:
                    interaction = await self.claim()
                except asyncio.CancelledError:
                    slots.release()
                    raise
                except Exception:
                    slots.release()
                    logger.exception("Durable response interaction poll failed")
                    await asyncio.sleep(poll_interval)
                    continue
                if interaction is None:
                    slots.release()
                    await asyncio.sleep(poll_interval)
                    continue
                task = asyncio.create_task(execute(interaction))
                in_flight.add(task)
                task.add_done_callback(in_flight.discard)
        finally:
            for task in list(in_flight):
                task.cancel()
            for task in list(in_flight):
                with contextlib.suppress(asyncio.CancelledError):
                    await task
