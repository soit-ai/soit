"""Outbox consumer: workflow.node.completed — bump workflow_runs counters and chain next node (B6)."""

from __future__ import annotations

from sqlmodel import Session

from app.kernel.commons.time import utc_now
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.outbox_models import EventOutbox
from app.kernel.events.publisher import OutboxPublisher
from app.modules.workflow.domain.models import WorkflowRun
from app.modules.workflow.domain.workflow_events import WorkflowEventType


def handle_workflow_node_completed_outbox(db: Session, row: EventOutbox) -> None:
    """Increment workflow run counters; optionally enqueue completion for the next node."""
    payload = row.payload_json or {}
    wfr_id = payload.get("workflow_run_id") or row.workflow_run_id or row.subject_id
    if not wfr_id:
        return
    wfr = db.get(WorkflowRun, wfr_id)
    if wfr is None:
        return

    wfr.completed_nodes = int(wfr.completed_nodes or 0) + 1
    waiting = int(wfr.waiting_nodes or 0)
    if waiting > 0:
        wfr.waiting_nodes = waiting - 1
    wfr.updated_at = utc_now()
    db.add(wfr)

    next_node_id = payload.get("next_node_id")
    if not next_node_id:
        return

    correlation = row.correlation_id or wfr.run_id or wfr.id
    envelope = DomainEventEnvelope(
        event_id=f"evt_wf_node_completed_{wfr_id}_{next_node_id}",
        event_type=WorkflowEventType.NODE_COMPLETED,
        tenant_id=wfr.tenant_id,
        subject_type="workflow_run",
        subject_id=wfr_id,
        run_id=wfr.run_id,
        workflow_run_id=wfr_id,
        correlation_id=correlation,
        producer="modules.workflow.handlers.node_completed",
        occurred_at=utc_now(),
        payload={
            "workflow_run_id": wfr_id,
            "node_id": next_node_id,
        },
    )
    OutboxPublisher(OutboxRepository(db)).publish(envelope)
