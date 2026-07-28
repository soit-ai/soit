"""Trace writer: authoritative run/step/cost rows in the request DB transaction.

Wave C: Prometheus counters, OTel trace/export for run/step lifecycle and cost rows are
applied by outbox consumers (``app.kernel.observe.handlers``), gated by
``event_consumer_checkpoint`` and dispatcher checkpoints. Optional ``event_bus``
remains best-effort only.
"""

import asyncio
import re
from datetime import UTC
from decimal import Decimal
from typing import Any

from sqlalchemy import update
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
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep
from app.kernel.runtime.runs.events import RunEventType
from app.kernel.runtime.status import (
    RuntimeTransitionError,
    validate_run_transition,
    validate_step_transition,
)


def _json_safe(value: Any) -> Any:
    """Return a deterministic JSON-compatible copy of pricing evidence."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _build_pricing_snapshot(
    *,
    snapshot: dict[str, Any] | None,
    billing_basis: str,
    billed_quantity: Decimal,
    currency: str | None,
    amount: Decimal | None,
    provider: str | None,
    provider_id: str | None,
    provider_slug: str | None,
    provider_kind: str | None,
    model_ref: str | None,
    upstream_model: str | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    latency_ms: int | None = None,
) -> dict[str, Any]:
    """Complete the immutable pricing snapshot required on every cost row."""
    result = _json_safe(snapshot or {})
    if not isinstance(result, dict):
        result = {}

    result.setdefault("schema_version", 1)
    result.setdefault("source", "runtime")
    result.setdefault("priced", amount is not None)
    result.setdefault("billing_basis", billing_basis)
    result.setdefault("billing_unit", billing_basis)
    result.setdefault("unit_size", 1)
    result.setdefault("rates", {})
    result.setdefault("configured_pricing", {})

    model = result.get("model")
    if not isinstance(model, dict):
        model = {}
    model.setdefault("requested", model_ref)
    model.setdefault("resolved", model_ref)
    model.setdefault("upstream", upstream_model)
    result["model"] = model

    provider_snapshot = result.get("provider")
    if not isinstance(provider_snapshot, dict):
        provider_snapshot = {}
    provider_snapshot.setdefault("name", provider)
    provider_snapshot.setdefault("id", provider_id)
    provider_snapshot.setdefault("slug", provider_slug)
    provider_snapshot.setdefault("kind", provider_kind)
    result["provider"] = provider_snapshot

    quantities = result.get("quantities")
    if not isinstance(quantities, dict):
        quantities = {}
    quantities.setdefault("quantity", format(billed_quantity, "f"))
    if prompt_tokens is not None:
        quantities.setdefault("prompt_tokens", prompt_tokens)
    if completion_tokens is not None:
        quantities.setdefault("completion_tokens", completion_tokens)
    if total_tokens is not None:
        quantities.setdefault("total_tokens", total_tokens)
    if latency_ms is not None:
        quantities.setdefault("latency_ms", latency_ms)
    result["quantities"] = quantities

    result["currency"] = currency
    result["amount"] = format(amount, "f") if amount is not None else None
    return result


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

    def emit_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        run_id: str | None = None,
    ) -> None:
        """Emit a best-effort runtime notification after durable state is committed."""

        self._emit_event(event_type, payload, run_id=run_id)

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
        request_id: str | None = None,
        parent_run_id: str | None = None,
        source_run_id: str | None = None,
        attempt_no: int = 1,
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

        if attempt_no < 1:
            raise ValueError("attempt_no must be at least 1")
        if parent_run_id:
            parent = self.db.get(Run, parent_run_id)
            if not parent or parent.tenant_id != self.ctx.tenant_id or parent.workspace_id != self.ctx.workspace_id:
                raise ValueError("Parent run scope mismatch")

        run = Run(
            id=run_id or generate_run_id(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            user_id=self.ctx.user_id,
            trace_id=getattr(self.ctx, "trace_id", None),
            request_id=request_id or getattr(self.ctx, "request_id", None),
            parent_run_id=parent_run_id,
            source_run_id=source_run_id,
            attempt_no=attempt_no,
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
            "request_id": run.request_id,
            "parent_run_id": run.parent_run_id,
            "source_run_id": run.source_run_id,
            "attempt_no": run.attempt_no,
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
                "request_id": run.request_id,
                "parent_run_id": run.parent_run_id,
                "source_run_id": run.source_run_id,
                "attempt_no": run.attempt_no,
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
        target_status = validate_run_transition(old_status, status)
        if old_status == target_status:
            if output_summary:
                run.output_summary = output_summary[:8192]
            if error_code:
                run.error_code = error_code
            if error_message:
                run.error_message = error_message[:8192]
            if error_step_id:
                run.error_step_id = error_step_id
            self.db.flush()
            self.db.refresh(run)
            return run

        changed_at = utc_now()
        values: dict[str, Any] = {
            "status": target_status,
            "updated_at": changed_at,
        }
        if output_summary:
            values["output_summary"] = output_summary[:8192]
        if error_code:
            values["error_code"] = error_code
        if error_message:
            values["error_message"] = error_message[:8192]
        elif target_status == "failed" and output_summary:
            values["error_message"] = output_summary[:8192]
        if error_step_id:
            values["error_step_id"] = error_step_id
        if target_status in ("succeeded", "failed", "canceled", "expired"):
            values["ended_at"] = changed_at
            if run.started_at:
                started_at = run.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=UTC)
                duration_seconds = (changed_at - started_at).total_seconds()
                values["duration_ms"] = int(duration_seconds * 1000)

        result = self.db.execute(
            update(Run)
            .where(
                Run.id == run_id,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
                Run.status == old_status,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            self.db.expire_all()
            current = self.db.get(Run, run_id)
            if current and current.status == target_status:
                return current
            if current:
                validate_run_transition(current.status, target_status)
            raise RuntimeTransitionError(f"Concurrent run transition rejected: {old_status} -> {target_status}")

        self.db.expire(run)
        self.db.refresh(run)
        status_payload: dict[str, Any] = {
            "run_id": run.id,
            "old_status": old_status,
            "new_status": target_status,
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
        target_status = validate_step_transition(old_status, status)
        if old_status == target_status:
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
            self.db.flush()
            self.db.refresh(step)
            return step

        changed_at = utc_now()
        values = {"status": target_status}
        if output_summary:
            values["output_summary"] = output_summary[:8192]
        if metrics:
            merged = dict(step.metrics_json or {})
            merged.update(metrics)
            values["metrics_json"] = merged
        if error_code:
            values["error_code"] = error_code
        if error_message:
            values["error_message"] = error_message
        if error_details:
            values["error_details"] = error_details
        if target_status in ("succeeded", "failed", "skipped", "canceled", "expired"):
            values["ended_at"] = changed_at

        result = self.db.execute(
            update(RunStep)
            .where(
                RunStep.id == step_id,
                RunStep.tenant_id == self.ctx.tenant_id,
                RunStep.workspace_id == self.ctx.workspace_id,
                RunStep.status == old_status,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            self.db.expire_all()
            current = self.db.get(RunStep, step_id)
            if current and current.status == target_status:
                return current
            if current:
                validate_step_transition(current.status, target_status)
            raise RuntimeTransitionError(f"Concurrent step transition rejected: {old_status} -> {target_status}")

        self.db.expire(step)
        self.db.refresh(step)

        if target_status == "failed":
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
            "new_status": target_status,
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
        run = self.db.get(Run, run_id)
        if not run or run.tenant_id != self.ctx.tenant_id or run.workspace_id != self.ctx.workspace_id:
            raise ValueError("Run scope mismatch")
        if step_id:
            step = self.db.get(RunStep, step_id)
            if (
                not step
                or step.run_id != run_id
                or step.tenant_id != self.ctx.tenant_id
                or step.workspace_id != self.ctx.workspace_id
            ):
                raise ValueError("Step scope mismatch")
        prefix = f"tenants/{self.ctx.tenant_id}/workspaces/{self.ctx.workspace_id}/runs/{run_id}/"
        if not storage_key.startswith(prefix):
            raise ValueError("Artifact storage key must use the canonical run prefix")
        if size_bytes is None or size_bytes < 0:
            raise ValueError("Artifact size_bytes evidence is required")
        if not sha256 or not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
            raise ValueError("Artifact SHA256 evidence is required")

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
        billing_basis: str,
        billed_quantity: Decimal | int | float,
        entry_type: str | None = None,
        currency: str | None = None,
        amount: Decimal | int | float | None = None,
        pricing_snapshot_json: dict[str, Any] | None = None,
        provider: str | None = None,
        provider_id: str | None = None,
        provider_slug: str | None = None,
        provider_kind: str | None = None,
        model_ref: str | None = None,
        upstream_model: str | None = None,
        tool_ref: str | None = None,
        source_port: str | None = None,
        operation: str | None = None,
        source_ref: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        latency_ms: int | None = None,
        request_count: int | None = None,
        embedding_count: int | None = None,
        rerank_count: int | None = None,
        vector_count: int | None = None,
        storage_bytes: int | None = None,
    ) -> RunCostEntry:
        """Record one usage fact with optional monetary calculation evidence.

        One metered invocation produces exactly one row; the dedicated
        dimension columns (tokens, latency_ms, request_count, ...) carry the
        measured facts, while unit/quantity only describe the billing basis.
        """
        run = self.db.get(Run, run_id)
        if not run or run.tenant_id != self.ctx.tenant_id or run.workspace_id != self.ctx.workspace_id:
            raise ValueError("Run scope mismatch")
        if step_id:
            step = self.db.get(RunStep, step_id)
            if not step or step.run_id != run_id or step.tenant_id != self.ctx.tenant_id or step.workspace_id != self.ctx.workspace_id:
                raise ValueError("Step scope mismatch")

        qty = Decimal(str(billed_quantity))
        if qty < 0:
            raise ValueError("billed_quantity must not be negative")
        raw_amount = Decimal(str(amount)) if amount is not None else None
        resolved_entry_type = entry_type or "usage"
        if resolved_entry_type != "usage":
            raise ValueError("New cost entries must combine usage and amount in one usage record")
        if raw_amount is not None and raw_amount < 0:
            raise ValueError("Cost amount must not be negative")
        if raw_amount is not None and not currency:
            raise ValueError("Priced usage entries require a currency")
        for dimension_name, dimension_value in (
            ("latency_ms", latency_ms),
            ("request_count", request_count),
            ("embedding_count", embedding_count),
            ("rerank_count", rerank_count),
            ("vector_count", vector_count),
            ("storage_bytes", storage_bytes),
        ):
            if dimension_value is not None and dimension_value < 0:
                raise ValueError(f"{dimension_name} must not be negative")
        resolved_amount = raw_amount
        resolved_currency = currency if raw_amount is not None else None
        resolved_pricing_snapshot = _build_pricing_snapshot(
            snapshot=pricing_snapshot_json,
            billing_basis=billing_basis,
            billed_quantity=qty,
            currency=resolved_currency,
            amount=resolved_amount,
            provider=provider,
            provider_id=provider_id,
            provider_slug=provider_slug,
            provider_kind=provider_kind,
            model_ref=model_ref,
            upstream_model=upstream_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
        )

        entry = RunCostEntry(
            run_id=run_id,
            step_id=step_id,
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            entry_type=resolved_entry_type,
            currency=resolved_currency,
            amount=resolved_amount,
            pricing_snapshot_json=resolved_pricing_snapshot,
            billing_basis=billing_basis,
            billed_quantity=qty,
            provider=provider,
            provider_id=provider_id,
            provider_slug=provider_slug,
            provider_kind=provider_kind,
            model_ref=model_ref,
            upstream_model=upstream_model,
            tool_ref=tool_ref,
            source_port=source_port,
            operation=operation,
            source_ref=source_ref,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            request_count=request_count,
            embedding_count=embedding_count,
            rerank_count=rerank_count,
            vector_count=vector_count,
            storage_bytes=storage_bytes,
        )
        self.db.add(entry)
        self.db.flush()

        cost_payload: dict[str, Any] = {
            "cost_entry_id": entry.id,
            "tenant_id": self.ctx.tenant_id,
            "run_id": entry.run_id,
            "step_id": entry.step_id,
            "entry_type": entry.entry_type,
            "billing_basis": entry.billing_basis,
            "billed_quantity": str(entry.billed_quantity),
            "currency": entry.currency,
            "amount": str(entry.amount),
            "pricing_snapshot_json": entry.pricing_snapshot_json,
            "provider": entry.provider,
            "provider_id": entry.provider_id,
            "provider_slug": entry.provider_slug,
            "provider_kind": entry.provider_kind,
            "model_ref": entry.model_ref,
            "upstream_model": entry.upstream_model,
            "tool_ref": entry.tool_ref,
            "source_port": entry.source_port,
            "operation": entry.operation,
            "source_ref": entry.source_ref,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "latency_ms": entry.latency_ms,
            "request_count": entry.request_count,
            "embedding_count": entry.embedding_count,
            "rerank_count": entry.rerank_count,
            "vector_count": entry.vector_count,
            "storage_bytes": entry.storage_bytes,
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
                "entry_type": entry.entry_type,
                "billing_basis": entry.billing_basis,
                "billed_quantity": str(entry.billed_quantity),
                "currency": entry.currency,
                "amount": str(entry.amount),
                "pricing_snapshot_json": entry.pricing_snapshot_json,
                "provider": entry.provider,
                "model_ref": entry.model_ref,
                "tool_ref": entry.tool_ref,
            },
            run_id=entry.run_id,
        )
        return entry

    def record_audit(
        self,
        *,
        run_id: str,
        step_id: str | None,
        gateway_type: str,
        outcome: str,
        payload: dict[str, Any],
        evidence_artifact_id: str | None = None,
    ) -> AuditEvent:
        """Persist an authoritative scoped gateway audit event."""

        run = self.db.get(Run, run_id)
        if not run or run.tenant_id != self.ctx.tenant_id or run.workspace_id != self.ctx.workspace_id:
            raise ValueError("Run scope mismatch")
        if step_id:
            step = self.db.get(RunStep, step_id)
            if not step or step.run_id != run_id or step.tenant_id != self.ctx.tenant_id or step.workspace_id != self.ctx.workspace_id:
                raise ValueError("Step scope mismatch")

        event = AuditEvent(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            event_type="gateway.request",
            resource_type=gateway_type,
            resource_id=step_id or run_id,
            run_id=run_id,
            step_id=step_id,
            trace_id=getattr(self.ctx, "trace_id", None),
            outcome=outcome,
            evidence_artifact_id=evidence_artifact_id,
            operation="invoke",
            actor_user_id=self.ctx.user_id,
            scope="workspace",
            payload_json=payload,
        )
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event
