""" handlers

SSE request handlers.
"""

from typing import AsyncGenerator
import logging
import json
import asyncio

from app.kernel.contracts.context import RequestContext
from app.kernel.responses.schemas import ResponseCreateRequest
from app.modules.workflow.application.service import WorkflowService
from app.wiring import get_container
from app.wiring.services import build_response_projection_coordinator


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
        from app.kernel.commons.ids import generate_run_id
        from app.kernel.trace.models import RunStep, Run
        from sqlalchemy import select, and_
        
        run_id = generate_run_id()
        
        # Send initial event
        yield f"event: start\n"
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
                "workflow_id": payload.get("subject_id"),
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
            
            yield f"event: compiled\n"
            yield f"data: {json.dumps({'run_id': run_id, 'status': 'compiled'})}\n\n"
            
            # Reuse the workflow service engine so SSE execution matches normal runtime wiring.
            db = self.workflow_service.db
            container = get_container()
            execution_engine = self.workflow_service.engine
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

            # Start execution in background
            execution_task = asyncio.create_task(execution_engine.execute(execution_plan))

            while True:
                if execution_task.done() and event_queue.empty():
                    break

                now = asyncio.get_running_loop().time()
                timeout = max(0.1, next_fallback_at - now)
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    steps_query = select(RunStep).where(
                        and_(
                            RunStep.run_id == run_id,
                            RunStep.tenant_id == ctx.tenant_id,
                            RunStep.workspace_id == ctx.workspace_id,
                        )
                    ).order_by(RunStep.created_at)
                    steps = list(db.exec(steps_query).all())
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
                result = await execution_task
            except Exception as exec_error:
                # Execution failed
                yield f"event: error\n"
                yield f"data: {json.dumps({'run_id': run_id, 'error': str(exec_error)})}\n\n"
                return
            
            # Get final run status
            run = db.get(Run, run_id)
            
            if run:
                yield f"event: complete\n"
                payload = {
                    "run_id": run_id,
                    "status": run.status,
                    "output_summary": run.output_summary[:500] if run.output_summary else None,
                }
                yield f"data: {json.dumps(payload)}\n\n"
            else:
                yield f"event: complete\n"
                yield f"data: {json.dumps({'run_id': run_id, 'status': terminal_status or 'completed'})}\n\n"
            
        except asyncio.CancelledError:
            self.logger.info("sse.cancelled", extra={"run_id": run_id})
            raise
        except Exception as e:
            yield f"event: error\n"
            yield f"data: {json.dumps({'run_id': run_id, 'error': str(e)})}\n\n"
        finally:
            if subscription_id and event_bus:
                try:
                    await event_bus.unsubscribe(subscription_id)
                except Exception:
                    pass
            if execution_task and not execution_task.done():
                execution_task.cancel()

    async def stream_run(
        self,
        ctx: RequestContext,
        run_id: str,
        last_event_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream run events and replay missed steps when possible."""
        from app.kernel.trace.models import RunStep, Run
        from sqlalchemy import select, and_

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
                "workflow_id": payload.get("subject_id"),
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
            run = db.exec(run_query).first()
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
            steps = list(db.exec(steps_query).all())
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
                    "workflow_id": run.subject_id,
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
                except asyncio.TimeoutError:
                    steps_query = select(RunStep).where(
                        and_(
                            RunStep.run_id == run_id,
                            RunStep.tenant_id == ctx.tenant_id,
                            RunStep.workspace_id == ctx.workspace_id,
                        )
                    ).order_by(RunStep.created_at)
                    steps = list(db.exec(steps_query).all())
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
                    run = db.get(Run, run_id) or run
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
    
    async def stream_chat(
        self,
        ctx: RequestContext,
        workflow_id: str,
        messages: list,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion (SSE).
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
            messages: Chat messages.
            
        Yields:
            SSE formatted data chunks.
        """
        await self.workflow_service.get_workflow(workflow_id)
        projection_coordinator = build_response_projection_coordinator(db=self.workflow_service.db, ctx=ctx)
        payload = ResponseCreateRequest(
            input={"messages": messages},
            stream=True,
            metadata={
                "source": "sse.chat",
                "workflow_id": workflow_id,
            },
        )

        async for item in projection_coordinator.execute_stream(payload):
            yield f"event: {item['event']}\n"
            yield f"data: {json.dumps(item['data'])}\n\n"
        yield "data: [DONE]\n\n"
