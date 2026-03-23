"""Enqueue approval.* facts into event_outbox in the same Session as approval writes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.modules.observability.domain.approval_events import ApprovalEventType
from app.modules.observability.domain.models import ApprovalRequest


def _approval_payload(approval: ApprovalRequest) -> dict:
    return {
        "approval_id": approval.id,
        "title": approval.title,
        "status": approval.status,
        "run_id": approval.run_id,
        "task_id": approval.task_id,
        "thread_id": approval.thread_id,
    }


def enqueue_approval_requested_outbox(
    db: Session,
    ctx: RequestContext,
    *,
    approval: ApprovalRequest,
) -> None:
    event_id = f"evt_approval_requested_{approval.id}"
    correlation = approval.run_id or approval.id
    envelope = DomainEventEnvelope(
        event_id=event_id,
        event_type=ApprovalEventType.REQUESTED,
        tenant_id=ctx.tenant_id,
        subject_type="approval",
        subject_id=approval.id,
        run_id=approval.run_id,
        task_id=approval.task_id,
        thread_id=approval.thread_id,
        correlation_id=correlation,
        producer="modules.observability.approval_repository",
        occurred_at=utc_now(),
        payload=_approval_payload(approval),
    )
    OutboxPublisher(OutboxRepository(db)).publish(envelope)


def enqueue_approval_approved_outbox(
    db: Session,
    ctx: RequestContext,
    *,
    approval: ApprovalRequest,
) -> None:
    event_id = f"evt_approval_approved_{approval.id}"
    correlation = approval.run_id or approval.id
    envelope = DomainEventEnvelope(
        event_id=event_id,
        event_type=ApprovalEventType.APPROVED,
        tenant_id=ctx.tenant_id,
        subject_type="approval",
        subject_id=approval.id,
        run_id=approval.run_id,
        task_id=approval.task_id,
        thread_id=approval.thread_id,
        correlation_id=correlation,
        producer="modules.observability.approval_repository",
        occurred_at=utc_now(),
        payload=_approval_payload(approval),
    )
    OutboxPublisher(OutboxRepository(db)).publish(envelope)


def enqueue_approval_rejected_outbox(
    db: Session,
    ctx: RequestContext,
    *,
    approval: ApprovalRequest,
) -> None:
    event_id = f"evt_approval_rejected_{approval.id}"
    correlation = approval.run_id or approval.id
    envelope = DomainEventEnvelope(
        event_id=event_id,
        event_type=ApprovalEventType.REJECTED,
        tenant_id=ctx.tenant_id,
        subject_type="approval",
        subject_id=approval.id,
        run_id=approval.run_id,
        task_id=approval.task_id,
        thread_id=approval.thread_id,
        correlation_id=correlation,
        producer="modules.observability.approval_repository",
        occurred_at=utc_now(),
        payload={
            **_approval_payload(approval),
            "resolution_note": approval.resolution_note,
        },
    )
    OutboxPublisher(OutboxRepository(db)).publish(envelope)
