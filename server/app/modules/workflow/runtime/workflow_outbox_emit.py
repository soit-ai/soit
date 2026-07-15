"""Enqueue workflow node facts into event_outbox (same Session as trace writes; caller commits)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.modules.workflow.domain.workflow_events import WorkflowEventType


def enqueue_workflow_node_completed(
    db: Session,
    ctx: RequestContext,
    *,
    workflow_run_id: str,
    run_id: str,
    node_id: str,
    step_pk: str,
    next_node_id: str | None = None,
) -> None:
    """Stage workflow.node.completed (B3)."""
    event_id = f"evt_wf_node_completed_{workflow_run_id}_{step_pk}"
    payload: dict = {
        "workflow_run_id": workflow_run_id,
        "node_id": node_id,
        "run_step_id": step_pk,
    }
    if next_node_id:
        payload["next_node_id"] = next_node_id
    envelope = DomainEventEnvelope(
        event_id=event_id,
        event_type=WorkflowEventType.NODE_COMPLETED,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        subject_type="workflow_run",
        subject_id=workflow_run_id,
        run_id=run_id,
        workflow_run_id=workflow_run_id,
        correlation_id=run_id,
        producer="modules.workflow.runtime.executor",
        occurred_at=utc_now(),
        payload=payload,
    )
    OutboxPublisher(OutboxRepository(db)).publish(envelope)


def enqueue_workflow_node_failed(
    db: Session,
    ctx: RequestContext,
    *,
    workflow_run_id: str,
    run_id: str,
    node_id: str,
    step_pk: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Stage workflow.node.failed (B3)."""
    event_id = f"evt_wf_node_failed_{workflow_run_id}_{step_pk}"
    envelope = DomainEventEnvelope(
        event_id=event_id,
        event_type=WorkflowEventType.NODE_FAILED,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        subject_type="workflow_run",
        subject_id=workflow_run_id,
        run_id=run_id,
        workflow_run_id=workflow_run_id,
        correlation_id=run_id,
        producer="modules.workflow.runtime.executor",
        occurred_at=utc_now(),
        payload={
            "workflow_run_id": workflow_run_id,
            "node_id": node_id,
            "run_step_id": step_pk,
            "error_code": error_code,
            "error_message": (error_message or "")[:8192],
        },
    )
    OutboxPublisher(OutboxRepository(db)).publish(envelope)
