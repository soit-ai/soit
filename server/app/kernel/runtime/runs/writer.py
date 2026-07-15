"""Trace writer: authoritative run/step/cost rows in the request DB transaction.

Wave C: Prometheus counters, OTel trace/export for run/step lifecycle and cost rows are
applied by outbox consumers (``app.kernel.observe.handlers``), gated by
``event_consumer_checkpoint`` and dispatcher checkpoints. Optional ``event_bus``
remains best-effort only.
"""

import asyncio
from datetime import UTC
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.kernel.commons.ids import (
    generate_artifact_id,
    generate_run_id,
    generate_step_id,
    generate_ulid,
)
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.events.bus import Event, EventBus
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.kernel.observe.context import (
    set_run_context,
    set_step_context,
)
from app.kernel.observe.event_types import ObserveEventType
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep
from app.kernel.runtime.runs.events import RunEventType


class TraceWriter:
    """Write trace data to database and object storage."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        event_bus: EventBus | None = None,
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

    def _emit_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        run_id: str | None = None,
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
        kind: str | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        subject_version_id: str | None = None,
        input_summary: str | None = None,
        run_id: str | None = None,
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
        outbox_payload: dict[str, Any] = {
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
            workspace_id=self.ctx.workspace_id,
            subject_type="run",
            subject_id=run.id,
            run_id=run.id,
            correlation_id=run.id,
            producer="kernel.trace.writer",
            occurred_at=run.started_at,
            payload=outbox_payload,
        )
        OutboxPublisher(OutboxRepository(self.db)).publish(envelope)
        self.db.flush()
        self.db.refresh(run)

        set_run_context(run.id)

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

        return run

    def update_run_status(
        self,
        run_id: str,
        status: str,
        output_summary: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        error_step_id: str | None = None,
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
            if run.started_at:
                started_at = run.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=UTC)
                duration_seconds = (run.ended_at - started_at).total_seconds()
                run.duration_ms = int(duration_seconds * 1000)
        run.updated_at = utc_now()

        self.db.flush()
        status_payload: dict[str, Any] = {
            "run_id": run.id,
            "old_status": old_status,
            "new_status": status,
            "mode": run.mode,
            "tenant_id": self.ctx.tenant_id,
        }
        OutboxPublisher(OutboxRepository(self.db)).publish(
            DomainEventEnvelope(
                event_id=generate_ulid(),
                event_type=ObserveEventType.RUN_STATUS_UPDATED,
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                subject_type="run",
                subject_id=run.id,
                run_id=run.id,
                correlation_id=run.id,
                producer="kernel.trace.writer",
                occurred_at=run.updated_at,
                payload=status_payload,
            )
        )
        self.db.flush()
        self.db.refresh(run)

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
        step_id: str | None = None,
        node_id: str | None = None,
        input_summary: str | None = None,
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
        self.db.flush()
        step_payload: dict[str, Any] = {
            "run_id": step.run_id,
            "step_row_id": step.id,
            "step_key": step.step_id,
            "step_type": step.step_type,
            "tenant_id": self.ctx.tenant_id,
            "status": step.status,
        }
        OutboxPublisher(OutboxRepository(self.db)).publish(
            DomainEventEnvelope(
                event_id=f"evt_step_created_{step.id}",
                event_type=ObserveEventType.STEP_CREATED,
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                subject_type="run_step",
                subject_id=step.id,
                run_id=step.run_id,
                correlation_id=step.run_id,
                producer="kernel.trace.writer",
                occurred_at=step.started_at,
                payload=step_payload,
            )
        )
        self.db.flush()
        self.db.refresh(step)

        set_step_context(step.id)

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

        return step

    def update_step_status(
        self,
        step_id: str,
        status: str,
        output_summary: str | None = None,
        metrics: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        error_details: dict[str, Any] | None = None,
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

        if status == "failed":
            run = self.db.get(Run, step.run_id)
            if run and run.tenant_id == self.ctx.tenant_id and run.workspace_id == self.ctx.workspace_id:
                run.error_step_id = step.id
                if error_code:
                    run.error_code = error_code
                if error_message:
                    run.error_message = error_message[:8192]
                run.updated_at = utc_now()

        step_status_payload: dict[str, Any] = {
            "step_row_id": step.id,
            "run_id": step.run_id,
            "old_status": old_status,
            "new_status": status,
            "step_type": step.step_type,
            "tenant_id": self.ctx.tenant_id,
        }
        self.db.flush()
        OutboxPublisher(OutboxRepository(self.db)).publish(
            DomainEventEnvelope(
                event_id=generate_ulid(),
                event_type=ObserveEventType.STEP_STATUS_UPDATED,
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                subject_type="run_step",
                subject_id=step.id,
                run_id=step.run_id,
                correlation_id=step.run_id,
                producer="kernel.trace.writer",
                occurred_at=utc_now(),
                payload=step_status_payload,
            )
        )
        self.db.flush()
        self.db.refresh(step)

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
        metrics: dict[str, Any],
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

        self.db.flush()
        self.db.refresh(step)
        return step

    def create_artifact(
        self,
        run_id: str,
        artifact_type: str,
        storage_key: str,
        meta: dict[str, Any] | None = None,
        step_id: str | None = None,
        mime: str | None = None,
        size_bytes: int | None = None,
        sha256: str | None = None,
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
        self.db.flush()
        self.db.refresh(artifact)
        return artifact

    def record_cost(
        self,
        *,
        run_id: str,
        step_id: str | None,
        unit: str,
        quantity: Decimal | int | float,
        currency: str = "USD",
        amount: Decimal | int | float | None = None,
        provider: str | None = None,
        provider_id: str | None = None,
        provider_slug: str | None = None,
        provider_kind: str | None = None,
        model_ref: str | None = None,
        upstream_model: str | None = None,
        tool_ref: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
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
            provider_id=provider_id,
            provider_slug=provider_slug,
            provider_kind=provider_kind,
            model_ref=model_ref,
            upstream_model=upstream_model,
            tool_ref=tool_ref,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        self.db.add(entry)
        self.db.flush()

        cost_payload: dict[str, Any] = {
            "cost_entry_id": entry.id,
            "tenant_id": self.ctx.tenant_id,
            "run_id": entry.run_id,
            "step_id": entry.step_id,
            "unit": entry.unit,
            "quantity": str(entry.quantity),
            "currency": entry.currency,
            "amount": str(entry.amount),
            "provider": entry.provider,
            "provider_id": entry.provider_id,
            "provider_slug": entry.provider_slug,
            "provider_kind": entry.provider_kind,
            "model_ref": entry.model_ref,
            "upstream_model": entry.upstream_model,
            "tool_ref": entry.tool_ref,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        OutboxPublisher(OutboxRepository(self.db)).publish(
            DomainEventEnvelope(
                event_id=f"evt_cost_{entry.id}",
                event_type=ObserveEventType.COST_RECORDED,
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                subject_type="cost_entry",
                subject_id=entry.id,
                run_id=entry.run_id,
                correlation_id=entry.run_id,
                producer="kernel.trace.writer",
                occurred_at=utc_now(),
                payload=cost_payload,
            )
        )
        self.db.flush()
        self.db.refresh(entry)

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
