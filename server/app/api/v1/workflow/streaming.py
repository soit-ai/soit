"""Workflow streaming handlers."""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from dataclasses import asdict
from datetime import timedelta

from sqlmodel import Session as SQLModelSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.common import lease
from app.modules.workflow.application.service import WorkflowService
from app.modules.workflow.domain.models import WorkflowRun
from app.settings.settings import settings
from app.wiring import get_container

_detached_workflow_tasks: set[asyncio.Task] = set()


def _claim_workflow_execution(
    db,
    ctx: RequestContext,
    *,
    run_id: str,
    workflow_id: str,
    inputs: dict,
) -> str:
    """Persist a leased WorkflowRun so the execution outlives this request."""
    lease_seconds = lease.normalize_lease_seconds(
        settings.workflow_execution_lease_seconds
    )
    claim = WorkflowRun(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run_id,
        workflow_id=workflow_id,
        status="running",
        inputs_json=dict(inputs or {}),
        request_context_json=asdict(ctx),
        lease_owner=f"workflow-api-{uuid.uuid4()}",
        lease_expires_at=utc_now() + timedelta(seconds=lease_seconds),
        attempt_count=1,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim.id


def _start_detached_execution(
    *,
    bind,
    ctx: RequestContext,
    plan,
    claim_id: str,
) -> asyncio.Task:
    """Run the plan on an independent session, renewing the claim's lease.

    The task is tracked at module level so it keeps running after the SSE
    response is closed. Only process death ends it early, and then the lease
    expiry makes the orphan visible.
    """

    def _session() -> SQLModelSession:
        return SQLModelSession(bind=bind, expire_on_commit=False)

    async def _execute() -> None:
        from app.wiring.services import build_workflow_service

        async def service_engine_execute(exec_db) -> None:
            service = build_workflow_service(db=exec_db, ctx=ctx)
            await service.engine.execute(plan)

        claim = None
        with _session() as probe:
            claim = probe.get(WorkflowRun, claim_id)
            worker_id = claim.lease_owner if claim else None
            attempt = claim.attempt_count if claim else 0
        stop = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat = None
        if worker_id:
            heartbeat = asyncio.create_task(
                lease.LeaseHeartbeat(
                    _session,
                    WorkflowRun,
                    claim_id,
                    worker_id=worker_id,
                    attempt_count=attempt,
                    lease_seconds=lease.normalize_lease_seconds(
                        settings.workflow_execution_lease_seconds
                    ),
                    log_label="Workflow execution lease",
                ).run(stop, lease_lost)
            )
        try:
            with _session() as exec_db:
                try:
                    await service_engine_execute(exec_db)
                finally:
                    # The engine leaves its final run transition uncommitted
                    # (request sessions used to flush it during teardown).
                    # Closing without committing would roll the terminal
                    # status back and strand the run as "running".
                    exec_db.commit()
        finally:
            stop.set()
            if heartbeat is not None:
                await heartbeat
            # The engine clears the lease on its terminal writes; a cancelled
            # or interrupted attempt may leave the claim running, in which
            # case the reaper resolves it once the lease lapses.

    task = asyncio.create_task(_execute())
    _detached_workflow_tasks.add(task)
    task.add_done_callback(_detached_workflow_tasks.discard)
    return task


def _unwrap_model(row):
    """Return the model object from SQLModel or SQLAlchemy row wrappers."""
    if isinstance(row, tuple):
        return row[0]
    if hasattr(row, "__getitem__") and not hasattr(row, "id"):
        try:
            return row[0]
        except Exception:
            return row
    return row


class SSEHandlers:
    """Handlers for SSE endpoints."""

    def __init__(self, workflow_service: WorkflowService):
        """Initialize SSE handlers.

        Args:
            workflow_service: WorkflowService instance.
        """
        self.workflow_service = workflow_service
        self.logger = logging.getLogger(__name__)

    async def _compile_execution_plan(self, workflow_id: str, inputs: dict, run_id: str):
        """Compile workflow from the new workflow domain."""

        return await self.workflow_service.compile_workflow(workflow_id, inputs, run_id)

    async def stream_execution(
        self,
        ctx: RequestContext,
        workflow_id: str,
        inputs: dict,
    ) -> AsyncGenerator[str, None]:
        """Stream workflow execution updates (SSE).

        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
            inputs: Workflow inputs.

        Yields:
            SSE formatted data chunks.
        """
        from sqlalchemy import and_, select

        from app.kernel.commons.ids import generate_run_id
        from app.kernel.runtime.db.models.runs import Run, RunStep

        run_id = generate_run_id()

        # Send initial event
        yield "event: start\n"
        yield f"data: {json.dumps({'run_id': run_id, 'status': 'started', 'request_id': ctx.request_id})}\n\n"

        execution_task = None
        subscription_id = None
        event_bus = None
        event_queue: asyncio.Queue = asyncio.Queue()
        known_step_ids: set[str] = set()
        terminal_status: str | None = None
        fallback_interval = 2.0
        next_fallback_at = asyncio.get_running_loop().time() + fallback_interval

        def _emit_step_event(payload: dict, event_id: str | None) -> None:
            data = {
                "event_id": event_id,
                "run_id": payload.get("run_id"),
                "step_id": payload.get("step_key") or payload.get("step_id"),
                "step_type": payload.get("step_type"),
                "status": payload.get("status"),
                "input_summary": payload.get("input_summary"),
                "output_summary": payload.get("output_summary"),
            }
            if event_id:
                yield f"id: {event_id}\n"
            yield "event: step\n"
            yield f"data: {json.dumps(data)}\n\n"

        def _emit_run_event(payload: dict, event_id: str | None) -> None:
            data = {
                "event_id": event_id,
                "run_id": payload.get("run_id"),
                "status": payload.get("status"),
                "mode": payload.get("mode"),
                "kind": payload.get("kind"),
                "subject_kind": payload.get("subject_kind"),
                "subject_id": payload.get("subject_id"),
                "subject_version_id": payload.get("subject_version_id"),
                "output_summary": payload.get("output_summary"),
                "error_code": payload.get("error_code"),
                "error_message": payload.get("error_message"),
                "error_step_id": payload.get("error_step_id"),
            }
            if event_id:
                yield f"id: {event_id}\n"
            yield "event: run\n"
            yield f"data: {json.dumps(data)}\n\n"

        def _emit_cost_event(payload: dict, event_id: str | None) -> None:
            data = {
                "event_id": event_id,
                "run_id": payload.get("run_id"),
                "step_id": payload.get("step_id"),
                "unit": payload.get("unit"),
                "quantity": payload.get("quantity"),
                "currency": payload.get("currency"),
                "amount": payload.get("amount"),
                "provider": payload.get("provider"),
                "model_ref": payload.get("model_ref"),
                "tool_ref": payload.get("tool_ref"),
            }
            if event_id:
                yield f"id: {event_id}\n"
            yield "event: cost\n"
            yield f"data: {json.dumps(data)}\n\n"

        async def _event_handler(event) -> None:
            await event_queue.put(event)

        try:
            # Compile workflow
            execution_plan = await self._compile_execution_plan(workflow_id, inputs, run_id)

            yield "event: compiled\n"
            yield f"data: {json.dumps({'run_id': run_id, 'status': 'compiled'})}\n\n"

            db = self.workflow_service.db
            container = get_container()
            event_bus = container.get_event_bus()
            subscription_id = await event_bus.subscribe(
                _event_handler,
                predicate=lambda event: event.run_id == run_id
                and event.type
                in {
                    "run.created",
                    "run.status",
                    "run.updated",
                    "step.created",
                    "step.status",
                    "step.updated",
                    "cost.recorded",
                },
            )

            # Claim the execution before it starts: the leased row with its
            # input snapshot is what makes the run recoverable evidence rather
            # than request-local state.
            claim_id = _claim_workflow_execution(
                db,
                ctx,
                run_id=run_id,
                workflow_id=workflow_id,
                inputs=inputs,
            )

            # Execution is detached from this request: it runs on its own
            # database session and survives the SSE consumer disconnecting.
            # This stream only tails persisted events.
            execution_task = _start_detached_execution(
                bind=db.get_bind(),
                ctx=ctx,
                plan=execution_plan,
                claim_id=claim_id,
            )

            while True:
                if execution_task.done() and event_queue.empty():
                    break

                now = asyncio.get_running_loop().time()
                timeout = max(0.1, next_fallback_at - now)
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=timeout)
                except TimeoutError:
                    steps_query = select(RunStep).where(
                        and_(
                            RunStep.run_id == run_id,
                            RunStep.tenant_id == ctx.tenant_id,
                            RunStep.workspace_id == ctx.workspace_id,
                        )
                    ).order_by(RunStep.created_at)
                    steps = [_unwrap_model(item) for item in db.exec(steps_query).all()]
                    for step in steps:
                        if step.id in known_step_ids:
                            continue
                        payload = {
                            "run_id": run_id,
                            "step_id": step.id,
                            "step_key": step.step_id,
                            "step_type": step.step_type,
                            "status": step.status,
                            "input_summary": step.input_summary,
                            "output_summary": step.output_summary,
                        }
                        for line in _emit_step_event(payload, step.id):
                            yield line
                        known_step_ids.add(step.id)
                    next_fallback_at = asyncio.get_running_loop().time() + fallback_interval
                    continue

                if event.type.startswith("step."):
                    payload = event.payload or {}
                    step_id = payload.get("step_id")
                    if step_id:
                        known_step_ids.add(step_id)
                    for line in _emit_step_event(payload, step_id or event.id):
                        yield line
                    continue

                if event.type in {"run.created", "run.status", "run.updated"}:
                    status = (event.payload or {}).get("status")
                    if status:
                        terminal_status = status
                    for line in _emit_run_event(event.payload or {}, event.id):
                        yield line
                    continue

                if event.type == "cost.recorded":
                    for line in _emit_cost_event(event.payload or {}, event.id):
                        yield line
                    continue

            # Wait for execution to complete
            try:
                await execution_task
            except Exception as exec_error:
                # Execution failed
                yield "event: error\n"
                yield f"data: {json.dumps({'run_id': run_id, 'error': str(exec_error)})}\n\n"
                return

            # Get final run status. The executor wrote it from a detached
            # session, so bypass anything this session cached.
            final_query = (
                select(Run)
                .where(
                    and_(
                        Run.id == run_id,
                        Run.tenant_id == ctx.tenant_id,
                        Run.workspace_id == ctx.workspace_id,
                    )
                )
                .execution_options(populate_existing=True)
            )
            run = _unwrap_model(db.exec(final_query).first())

            if run:
                yield "event: complete\n"
                payload = {
                    "run_id": run_id,
                    "status": run.status,
                    "output_summary": run.output_summary[:500] if run.output_summary else None,
                }
                yield f"data: {json.dumps(payload)}\n\n"
            else:
                yield "event: complete\n"
                yield f"data: {json.dumps({'run_id': run_id, 'status': terminal_status or 'completed'})}\n\n"

        except asyncio.CancelledError:
            self.logger.info("sse.cancelled", extra={"run_id": run_id})
            raise
        except Exception as e:
            yield "event: error\n"
            yield f"data: {json.dumps({'run_id': run_id, 'error': str(e)})}\n\n"
        finally:
            if subscription_id and event_bus:
                try:
                    await event_bus.unsubscribe(subscription_id)
                except Exception:
                    pass
            # Deliberately do not cancel execution_task: the consumer leaving
            # must not abort a side-effectful workflow. Cancellation goes
            # through the cancel endpoint, which the executor observes at node
            # boundaries via the persisted run status.

    async def stream_run(
        self,
        ctx: RequestContext,
        run_id: str,
        last_event_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream run events and replay missed steps when possible."""
        from sqlalchemy import and_, select

        from app.kernel.runtime.db.models.runs import Run, RunStep

        db = self.workflow_service.db
        event_queue: asyncio.Queue = asyncio.Queue()
        known_step_ids: set[str] = set()
        subscription_id = None
        event_bus = None
        terminal_status: str | None = None
        fallback_interval = 2.0
        next_fallback_at = asyncio.get_running_loop().time() + fallback_interval

        def _emit_step_event(payload: dict, event_id: str | None) -> None:
            data = {
                "event_id": event_id,
                "run_id": payload.get("run_id"),
                "step_id": payload.get("step_key") or payload.get("step_id"),
                "step_type": payload.get("step_type"),
                "status": payload.get("status"),
                "input_summary": payload.get("input_summary"),
                "output_summary": payload.get("output_summary"),
            }
            if event_id:
                yield f"id: {event_id}\n"
            yield "event: step\n"
            yield f"data: {json.dumps(data)}\n\n"

        def _emit_run_event(payload: dict, event_id: str | None) -> None:
            data = {
                "event_id": event_id,
                "run_id": payload.get("run_id"),
                "status": payload.get("status"),
                "mode": payload.get("mode"),
                "kind": payload.get("kind"),
                "subject_kind": payload.get("subject_kind"),
                "subject_id": payload.get("subject_id"),
                "subject_version_id": payload.get("subject_version_id"),
                "output_summary": payload.get("output_summary"),
                "error_code": payload.get("error_code"),
                "error_message": payload.get("error_message"),
                "error_step_id": payload.get("error_step_id"),
            }
            if event_id:
                yield f"id: {event_id}\n"
            yield "event: run\n"
            yield f"data: {json.dumps(data)}\n\n"

        def _emit_cost_event(payload: dict, event_id: str | None) -> None:
            data = {
                "event_id": event_id,
                "run_id": payload.get("run_id"),
                "step_id": payload.get("step_id"),
                "unit": payload.get("unit"),
                "quantity": payload.get("quantity"),
                "currency": payload.get("currency"),
                "amount": payload.get("amount"),
                "provider": payload.get("provider"),
                "model_ref": payload.get("model_ref"),
                "tool_ref": payload.get("tool_ref"),
            }
            if event_id:
                yield f"id: {event_id}\n"
            yield "event: cost\n"
            yield f"data: {json.dumps(data)}\n\n"

        async def _event_handler(event) -> None:
            await event_queue.put(event)

        try:
            run_query = select(Run).where(
                and_(
                    Run.id == run_id,
                    Run.tenant_id == ctx.tenant_id,
                    Run.workspace_id == ctx.workspace_id,
                )
            )
            # The execution writes from its own session, so this tailer must
            # bypass any instance this session cached earlier.
            run = _unwrap_model(
                db.exec(run_query.execution_options(populate_existing=True)).first()
            )
            if not run:
                yield "event: error\n"
                yield f"data: {json.dumps({'run_id': run_id, 'error': 'Run not found'})}\n\n"
                return

            if run.mode == "workflow" and run.subject_id:
                await self.workflow_service.get_workflow(run.subject_id)

            last_step_time = None
            if last_event_id:
                step_query = select(RunStep).where(
                    and_(
                        RunStep.id == last_event_id,
                        RunStep.run_id == run_id,
                        RunStep.tenant_id == ctx.tenant_id,
                        RunStep.workspace_id == ctx.workspace_id,
                    )
                )
                last_step = db.exec(step_query).first()
                if last_step:
                    last_step_time = last_step.created_at
                    known_step_ids.add(last_step.id)

            steps_query = select(RunStep).where(
                and_(
                    RunStep.run_id == run_id,
                    RunStep.tenant_id == ctx.tenant_id,
                    RunStep.workspace_id == ctx.workspace_id,
                    RunStep.created_at > last_step_time if last_step_time else True,
                )
            ).order_by(RunStep.created_at)
            steps = [_unwrap_model(item) for item in db.exec(steps_query).all()]
            for step in steps:
                if step.id in known_step_ids:
                    continue
                payload = {
                    "run_id": run_id,
                    "step_id": step.id,
                    "step_key": step.step_id,
                    "step_type": step.step_type,
                    "status": step.status,
                    "input_summary": step.input_summary,
                    "output_summary": step.output_summary,
                }
                for line in _emit_step_event(payload, step.id):
                    yield line
                known_step_ids.add(step.id)

            for line in _emit_run_event(
                {
                    "run_id": run.id,
                    "status": run.status,
                    "mode": run.mode,
                    "kind": run.kind,
                    "subject_kind": run.subject_kind,
                    "subject_id": run.subject_id,
                    "subject_version_id": run.subject_version_id,
                    "output_summary": run.output_summary,
                    "error_code": run.error_code,
                    "error_message": run.error_message,
                    "error_step_id": run.error_step_id,
                },
                run.id,
            ):
                yield line

            event_bus = get_container().get_event_bus()
            subscription_id = await event_bus.subscribe(
                _event_handler,
                predicate=lambda event: event.run_id == run_id
                and event.type
                in {
                    "run.created",
                    "run.status",
                    "run.updated",
                    "step.created",
                    "step.status",
                    "step.updated",
                    "cost.recorded",
                },
            )

            while True:
                current_status = terminal_status or run.status
                if current_status in ("succeeded", "failed", "canceled") and event_queue.empty():
                    break

                now = asyncio.get_running_loop().time()
                timeout = max(0.1, next_fallback_at - now)
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=timeout)
                except TimeoutError:
                    steps_query = select(RunStep).where(
                        and_(
                            RunStep.run_id == run_id,
                            RunStep.tenant_id == ctx.tenant_id,
                            RunStep.workspace_id == ctx.workspace_id,
                        )
                    ).order_by(RunStep.created_at)
                    steps = [_unwrap_model(item) for item in db.exec(steps_query).all()]
                    for step in steps:
                        if step.id in known_step_ids:
                            continue
                        payload = {
                            "run_id": run_id,
                            "step_id": step.id,
                            "step_key": step.step_id,
                            "step_type": step.step_type,
                            "status": step.status,
                            "input_summary": step.input_summary,
                            "output_summary": step.output_summary,
                        }
                        for line in _emit_step_event(payload, step.id):
                            yield line
                        known_step_ids.add(step.id)
                    # db.get would return the cached instance unchanged; the
                    # writer is another session, so force a fresh read.
                    run = (
                        _unwrap_model(
                            db.exec(
                                run_query.execution_options(populate_existing=True)
                            ).first()
                        )
                        or run
                    )
                    next_fallback_at = asyncio.get_running_loop().time() + fallback_interval
                    continue

                if event.type.startswith("step."):
                    payload = event.payload or {}
                    step_id = payload.get("step_id")
                    if step_id:
                        known_step_ids.add(step_id)
                    for line in _emit_step_event(payload, step_id or event.id):
                        yield line
                    continue

                if event.type in {"run.created", "run.status", "run.updated"}:
                    payload = event.payload or {}
                    status = payload.get("status")
                    if status:
                        terminal_status = status
                        run.status = status
                    for line in _emit_run_event(payload, event.id):
                        yield line
                    continue

                if event.type == "cost.recorded":
                    for line in _emit_cost_event(event.payload or {}, event.id):
                        yield line
                    continue

            final_status = terminal_status or run.status
            yield "event: complete\n"
            yield f"data: {json.dumps({'run_id': run_id, 'status': final_status})}\n\n"

        except asyncio.CancelledError:
            self.logger.info("sse.cancelled", extra={"run_id": run_id})
            raise
        except Exception as e:
            yield "event: error\n"
            yield f"data: {json.dumps({'run_id': run_id, 'error': str(e)})}\n\n"
        finally:
            if subscription_id and event_bus:
                try:
                    await event_bus.unsubscribe(subscription_id)
                except Exception:
                    pass
