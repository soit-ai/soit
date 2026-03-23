"""Subscribe to execution outbox facts: trace export, Prometheus, usage logs (Wave C)."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Optional

from sqlmodel import Session

from app.kernel.events.outbox_models import EventOutbox
from app.kernel.observability.metrics import active_runs, cost_total, run_count, tokens_total
from app.kernel.observability.projection_repo import try_claim_projection_slot
from app.kernel.observability.tracing import tracer
from app.kernel.runtime.events import RunEventType
from app.kernel.trace.exporter import OpenTelemetryExporter
from app.kernel.trace.models import Run

logger = logging.getLogger(__name__)


def _resolve_run_id(row: EventOutbox) -> Optional[str]:
    if row.run_id:
        return row.run_id
    payload = row.payload_json or {}
    return payload.get("run_id") or row.subject_id


def handle_run_created_observability(db: Session, row: EventOutbox) -> None:
    """Mirror former TraceWriter.create_run observability (tracer, exporter, run counters)."""
    if row.event_type != RunEventType.CREATED:
        return
    if not try_claim_projection_slot(
        db, consumer_name="observability.run_created.side_effects", event_id=row.event_id
    ):
        return

    rid = _resolve_run_id(row)
    if not rid:
        return
    run = db.get(Run, rid)
    if run is None:
        return

    exporter = OpenTelemetryExporter()
    tracer.trace_run(run, {"event": "created"})
    exporter.export_run(run)
    run_count.labels(mode=run.mode, status="queued", tenant_id=run.tenant_id).inc()
    active_runs.labels(mode=run.mode, tenant_id=run.tenant_id).inc()


def handle_task_lifecycle_observability(db: Session, row: EventOutbox) -> None:
    """Structured usage log hook; extend with usage_events table when needed."""
    consumer = f"observability.task.{row.event_type}"
    if not try_claim_projection_slot(db, consumer_name=consumer, event_id=row.event_id):
        return
    payload = row.payload_json or {}
    logger.info(
        "usage.task %s %s",
        row.event_type,
        json.dumps(payload, ensure_ascii=False, default=str)[:8192],
    )


def handle_workflow_node_observability(db: Session, row: EventOutbox) -> None:
    """Audit-style log for workflow node facts (DB counters stay on workflow handler)."""
    consumer = f"observability.workflow.{row.event_type}"
    if not try_claim_projection_slot(db, consumer_name=consumer, event_id=row.event_id):
        return
    payload = row.payload_json or {}
    logger.info(
        "usage.workflow_node %s %s",
        row.event_type,
        json.dumps(payload, ensure_ascii=False, default=str)[:8192],
    )


def handle_cost_recorded_observability(db: Session, row: EventOutbox) -> None:
    """Apply token/cost Prometheus counters idempotently per cost entry."""
    if not try_claim_projection_slot(
        db, consumer_name="observability.cost.metrics", event_id=row.event_id
    ):
        return
    payload = row.payload_json or {}
    tenant_id = payload.get("tenant_id") or row.tenant_id
    if not tenant_id:
        return

    prompt_tokens = payload.get("prompt_tokens")
    if prompt_tokens:
        tokens_total.labels(type="prompt", tenant_id=tenant_id).inc(int(prompt_tokens))
    completion_tokens = payload.get("completion_tokens")
    if completion_tokens:
        tokens_total.labels(type="completion", tenant_id=tenant_id).inc(int(completion_tokens))

    unit = payload.get("unit") or ""
    quantity = payload.get("quantity")
    if unit in ("embeddings", "embedding") and quantity is not None:
        try:
            tokens_total.labels(type="embedding", tenant_id=tenant_id).inc(float(Decimal(str(quantity))))
        except Exception:
            pass

    amount = payload.get("amount")
    if amount is not None:
        try:
            amt = float(Decimal(str(amount)))
            if amt > 0:
                cost_total.labels(resource_type=str(unit or "unknown"), tenant_id=tenant_id).inc(amt)
        except Exception:
            pass
