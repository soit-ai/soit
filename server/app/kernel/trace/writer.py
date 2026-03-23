""" writer

Trace writer interface (DB + artifact storage).
"""

from typing import Optional, Dict, Any
import asyncio
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from decimal import Decimal
from app.kernel.events.bus import Event, EventBus
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.kernel.runtime.events import RunEventType
from app.kernel.trace.models import Run, RunStep, RunArtifact, RunCostEntry
from app.kernel.contracts.context import RequestContext
from app.kernel.commons.ids import (
    generate_run_id,
    generate_step_id,
    generate_artifact_id,
    generate_ulid,
)
from app.kernel.commons.time import utc_now
from app.kernel.observability.context import (
    set_run_context,
    set_step_context,
)
from app.kernel.observability.tracing import tracer
from app.kernel.trace.exporter import OpenTelemetryExporter
from app.kernel.observability.metrics import (
    run_count,
    run_duration,
    step_count,
    step_duration,
    tokens_total,
    cost_total,
    active_runs,
)


class TraceWriter:
    """Write trace data to database and object storage."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        event_bus: Optional[EventBus] = None,
    ):
        """Initialize trace writer.
        
        Args:
            db: Database session.
            ctx: Request context.
            event_bus: Optional event bus for trace events.
        """
        self.db = db
        self.ctx = ctx
        self.event_bus = event_bus
        self.exporter = OpenTelemetryExporter()
        self.tracer = tracer

    def _emit_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        *,
        run_id: Optional[str] = None,
    ) -> None:
        """Emit a trace event without affecting DB writes."""
        if not self.event_bus:
            return

        event = Event(
            id=generate_ulid(),
            type=event_type,
            payload=payload,
            created_at=utc_now(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            run_id=run_id,
            trace_id=getattr(self.ctx, "trace_id", None),
        )

        try:
            publish_sync = getattr(self.event_bus, "publish_sync", None)
            if callable(publish_sync):
                publish_sync(event)
                return

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.event_bus.publish(event))
                return
            except RuntimeError:
                asyncio.run(self.event_bus.publish(event))
        except Exception:
            return
    
    def create_run(
        self,
        mode: str,
        *,
        kind: Optional[str] = None,
        subject_kind: Optional[str] = None,
        subject_id: Optional[str] = None,
        subject_version_id: Optional[str] = None,
        input_summary: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Run:
        """Create a new run.
        
        Args:
            mode: Execution mode (chat/workflow/agent/knowledge/memory/etc.).
            subject_kind: Optional primary execution subject kind.
            subject_id: Optional primary execution subject ID.
            subject_version_id: Optional primary execution subject version ID.
            input_summary: Optional input summary (max 8KB).
            
        Returns:
            Created Run instance.
        """
        resolved_subject_kind = subject_kind or mode
        resolved_subject_id = subject_id

        run = Run(
            id=run_id or generate_run_id(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            user_id=self.ctx.user_id,
            trace_id=getattr(self.ctx, "trace_id", None),
            mode=mode,
            kind=kind or mode,
            subject_kind=resolved_subject_kind,
            subject_id=resolved_subject_id,
            subject_version_id=subject_version_id,
            status="queued",
            input_summary=input_summary[:8192] if input_summary else None,
            started_at=utc_now(),
        )
        self.db.add(run)
        outbox_payload: Dict[str, Any] = {
            "run_id": run.id,
            "status": run.status,
            "mode": run.mode,
            "kind": run.kind,
            "subject_kind": run.subject_kind,
            "subject_id": run.subject_id,
            "subject_version_id": run.subject_version_id,
        }
        envelope = DomainEventEnvelope(
            event_id=f"evt_run_created_{run.id}",
            event_type=RunEventType.CREATED,
            tenant_id=self.ctx.tenant_id,
            subject_type="run",
            subject_id=run.id,
            run_id=run.id,
            correlation_id=run.id,
            producer="kernel.trace.writer",
            occurred_at=run.started_at,
            payload=outbox_payload,
        )
        OutboxPublisher(OutboxRepository(self.db)).publish(envelope)
        self.db.commit()
        self.db.refresh(run)

        set_run_context(run.id)
        self.tracer.trace_run(run, {"event": "created"})
        self.exporter.export_run(run)

        self._emit_event(
            "run.created",
            {
                "run_id": run.id,
                "status": run.status,
                "mode": run.mode,
                "kind": run.kind,
                "subject_kind": run.subject_kind,
                "subject_id": run.subject_id,
                "subject_version_id": run.subject_version_id,
            },
            run_id=run.id,
        )
        
        # Update metrics
        run_count.labels(mode=mode, status="queued", tenant_id=self.ctx.tenant_id).inc()
        active_runs.labels(mode=mode, tenant_id=self.ctx.tenant_id).inc()
        
        return run
    
    def update_run_status(
        self,
        run_id: str,
        status: str,
        output_summary: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        error_step_id: Optional[str] = None,
    ) -> Run:
        """Update run status.
        
        Args:
            run_id: Run ID.
            status: New status.
            output_summary: Optional output summary (max 8KB).
            
        Returns:
            Updated Run instance.
        """
        run = self.db.get(Run, run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")
        
        # Verify scope
        if run.tenant_id != self.ctx.tenant_id or run.workspace_id != self.ctx.workspace_id:
            raise ValueError("Run scope mismatch")
        
        old_status = run.status
        run.status = status
        if output_summary:
            run.output_summary = output_summary[:8192]
        if error_code:
            run.error_code = error_code
        if error_message:
            run.error_message = error_message[:8192]
        elif status == "failed" and output_summary:
            run.error_message = output_summary[:8192]
        if error_step_id:
            run.error_step_id = error_step_id
        if status in ("succeeded", "failed", "canceled"):
            run.ended_at = utc_now()
            # Calculate duration
            if run.started_at:
                started_at = run.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                duration_seconds = (run.ended_at - started_at).total_seconds()
                run.duration_ms = int(duration_seconds * 1000)
                run_duration.labels(mode=run.mode, tenant_id=self.ctx.tenant_id).observe(duration_seconds)
            # Decrement active runs
            active_runs.labels(mode=run.mode, tenant_id=self.ctx.tenant_id).dec()
        run.updated_at = utc_now()
        
        # Update metrics
        if old_status != status:
            run_count.labels(mode=run.mode, status=status, tenant_id=self.ctx.tenant_id).inc()
        
        self.db.commit()
        self.db.refresh(run)

        self.tracer.trace_run(run, {"event": "status"})
        self.exporter.export_run(run)

        self._emit_event(
            "run.status",
            {
                "run_id": run.id,
                "status": run.status,
                "mode": run.mode,
                "kind": run.kind,
                "output_summary": run.output_summary,
                "subject_kind": run.subject_kind,
                "subject_id": run.subject_id,
                "subject_version_id": run.subject_version_id,
                "error_code": run.error_code,
                "error_message": run.error_message,
                "error_step_id": run.error_step_id,
            },
            run_id=run.id,
        )
        self._emit_event(
            "run.updated",
            {
                "run_id": run.id,
                "status": run.status,
                "mode": run.mode,
                "kind": run.kind,
                "output_summary": run.output_summary,
                "subject_kind": run.subject_kind,
                "subject_id": run.subject_id,
                "subject_version_id": run.subject_version_id,
                "error_code": run.error_code,
                "error_message": run.error_message,
                "error_step_id": run.error_step_id,
            },
            run_id=run.id,
        )
        return run
    
    def create_step(
        self,
        run_id: str,
        step_type: str,
        step_id: Optional[str] = None,
        node_id: Optional[str] = None,
        input_summary: Optional[str] = None,
    ) -> RunStep:
        """Create a new step.
        
        Args:
            run_id: Run ID.
            step_type: Step type (llm/retrieval/rerank/tool/workflow_node/agent_plan/memory_write/io/other).
            step_id: Optional step ID (e.g., "st_node1" for workflow nodes).
            node_id: Optional node ID.
            input_summary: Optional input summary (max 8KB).
            
        Returns:
            Created RunStep instance.
        """
        step = RunStep(
            id=generate_step_id(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            trace_id=getattr(self.ctx, "trace_id", None),
            run_id=run_id,
            step_id=step_id,
            step_type=step_type,
            node_id=node_id,
            status="queued",
            input_summary=input_summary[:8192] if input_summary else None,
            started_at=utc_now(),
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)

        set_step_context(step.id)
        self.tracer.trace_step(step, {"event": "created"})
        self.exporter.export_step(step)

        self._emit_event(
            "step.created",
            {
                "run_id": step.run_id,
                "step_id": step.id,
                "step_key": step.step_id,
                "step_type": step.step_type,
                "status": step.status,
                "node_id": step.node_id,
                "input_summary": step.input_summary,
            },
            run_id=step.run_id,
        )
        
        # Update metrics
        step_count.labels(step_type=step_type, status="queued", tenant_id=self.ctx.tenant_id).inc()
        
        return step
    
    def update_step_status(
        self,
        step_id: str,
        status: str,
        output_summary: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> RunStep:
        """Update step status.
        
        Args:
            step_id: Step ID.
            status: New status.
            output_summary: Optional output summary (max 8KB).
            metrics: Optional metrics dictionary.
            error_code: Optional error code.
            error_message: Optional error message.
            error_details: Optional error details.
            
        Returns:
            Updated RunStep instance.
        """
        step = self.db.get(RunStep, step_id)
        if not step:
            raise ValueError(f"Step not found: {step_id}")
        
        # Verify scope
        if step.tenant_id != self.ctx.tenant_id or step.workspace_id != self.ctx.workspace_id:
            raise ValueError("Step scope mismatch")
        
        old_status = step.status
        step.status = status
        if output_summary:
            step.output_summary = output_summary[:8192]
        if metrics:
            merged = dict(step.metrics_json or {})
            merged.update(metrics)
            step.metrics_json = merged
        if error_code:
            step.error_code = error_code
        if error_message:
            step.error_message = error_message
        if error_details:
            step.error_details = error_details
        if status in ("succeeded", "failed", "skipped", "canceled"):
            step.ended_at = utc_now()
            # Calculate duration
            if step.started_at:
                started_at = step.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                duration_seconds = (step.ended_at - started_at).total_seconds()
                step_duration.labels(step_type=step.step_type, tenant_id=self.ctx.tenant_id).observe(duration_seconds)
        
        if status == "failed":
            run = self.db.get(Run, step.run_id)
            if run and run.tenant_id == self.ctx.tenant_id and run.workspace_id == self.ctx.workspace_id:
                run.error_step_id = step.id
                if error_code:
                    run.error_code = error_code
                if error_message:
                    run.error_message = error_message[:8192]
                run.updated_at = utc_now()

        # Update metrics
        if old_status != status:
            step_count.labels(step_type=step.step_type, status=status, tenant_id=self.ctx.tenant_id).inc()
        
        self.db.commit()
        self.db.refresh(step)

        self.tracer.trace_step(step, {"event": "status"})
        self.exporter.export_step(step)

        self._emit_event(
            "step.status",
            {
                "run_id": step.run_id,
                "step_id": step.id,
                "step_key": step.step_id,
                "step_type": step.step_type,
                "status": step.status,
                "node_id": step.node_id,
                "input_summary": step.input_summary,
                "output_summary": step.output_summary,
                "error_code": step.error_code,
                "error_message": step.error_message,
            },
            run_id=step.run_id,
        )
        self._emit_event(
            "step.updated",
            {
                "run_id": step.run_id,
                "step_id": step.id,
                "step_key": step.step_id,
                "step_type": step.step_type,
                "status": step.status,
                "node_id": step.node_id,
                "input_summary": step.input_summary,
                "output_summary": step.output_summary,
                "error_code": step.error_code,
                "error_message": step.error_message,
            },
            run_id=step.run_id,
        )
        return step

    def update_step_metrics(
        self,
        step_id: str,
        metrics: Dict[str, Any],
    ) -> RunStep:
        """Merge metrics into an existing step without changing status."""
        step = self.db.get(RunStep, step_id)
        if not step:
            raise ValueError(f"Step not found: {step_id}")

        if step.tenant_id != self.ctx.tenant_id or step.workspace_id != self.ctx.workspace_id:
            raise ValueError("Step scope mismatch")

        merged = dict(step.metrics_json or {})
        merged.update(metrics or {})
        step.metrics_json = merged

        self.db.commit()
        self.db.refresh(step)
        return step
    
    def create_artifact(
        self,
        run_id: str,
        artifact_type: str,
        storage_key: str,
        meta: Optional[Dict[str, Any]] = None,
        step_id: Optional[str] = None,
        mime: Optional[str] = None,
        size_bytes: Optional[int] = None,
        sha256: Optional[str] = None,
    ) -> RunArtifact:
        """Create a new artifact.
        
        Args:
            run_id: Run ID.
            artifact_type: Artifact type (file/log/blob/json).
            storage_key: Storage key (object storage path).
            meta: Optional metadata (mime, size, hash, etc.).
            
        Returns:
            Created RunArtifact instance.
        """
        artifact = RunArtifact(
            id=generate_artifact_id(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            run_id=run_id,
            step_id=step_id,
            type=artifact_type,
            storage_key=storage_key,
            mime=mime,
            size_bytes=size_bytes,
            sha256=sha256,
            meta_json=meta,
        )
        self.db.add(artifact)
        self.db.commit()
        self.db.refresh(artifact)
        return artifact

    def record_cost(
        self,
        *,
        run_id: str,
        step_id: Optional[str],
        unit: str,
        quantity: Decimal | int | float,
        currency: str = "USD",
        amount: Decimal | int | float | None = None,
        provider: Optional[str] = None,
        model_ref: Optional[str] = None,
        tool_ref: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
    ) -> RunCostEntry:
        """Record a normalized cost entry."""
        qty = Decimal(str(quantity))
        amt = Decimal(str(amount if amount is not None else 0))

        entry = RunCostEntry(
            run_id=run_id,
            step_id=step_id,
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            currency=currency,
            amount=amt,
            unit=unit,
            quantity=qty,
            provider=provider,
            model_ref=model_ref,
            tool_ref=tool_ref,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        if prompt_tokens:
            tokens_total.labels(type="prompt", tenant_id=self.ctx.tenant_id).inc(prompt_tokens)
        if completion_tokens:
            tokens_total.labels(type="completion", tenant_id=self.ctx.tenant_id).inc(completion_tokens)
        if unit in ("embeddings", "embedding"):
            tokens_total.labels(type="embedding", tenant_id=self.ctx.tenant_id).inc(float(qty))
        if amt and amt > 0:
            cost_total.labels(resource_type=unit, tenant_id=self.ctx.tenant_id).inc(float(amt))

        self._emit_event(
            "cost.recorded",
            {
                "run_id": entry.run_id,
                "step_id": entry.step_id,
                "unit": entry.unit,
                "quantity": str(entry.quantity),
                "currency": entry.currency,
                "amount": str(entry.amount),
                "provider": entry.provider,
                "model_ref": entry.model_ref,
                "tool_ref": entry.tool_ref,
            },
            run_id=entry.run_id,
        )
        return entry
