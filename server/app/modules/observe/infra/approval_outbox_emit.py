"""Enqueue approval.* facts into event_outbox in the same AsyncSession as approval writes."""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.modules.observe.domain.approval_events import ApprovalEventType
from app.modules.observe.domain.models import ApprovalRequest


def _approval_payload(approval: ApprovalRequest) -> dict:
    return {
        "approval_id": approval.id,
        "title": approval.title,
        "status": approval.status,
        "run_id": approval.run_id,
        "task_id": approval.task_id,
        "thread_id": approval.thread_id,
        "requested_by": approval.requested_by,
        # Who may decide, so consumers outside observe can address them.
        "assignee_user_ids": list(approval.assignee_user_ids or []),
        "assignee_roles": list(approval.assignee_roles or []),
        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
    }


def enqueue_approval_delegated_outbox(
    db: AsyncSession,
    ctx: RequestContext,
    *,
    approval: ApprovalRequest,
    decision_id: str,
    note: str | None,
) -> None:
    """A request handed to another approver; one event per delegation."""

    envelope = DomainEventEnvelope(
        event_id=f"evt_approval_delegated_{decision_id}",
        event_type=ApprovalEventType.DELEGATED,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        subject_type="approval",
        subject_id=approval.id,
        run_id=approval.run_id,
        task_id=approval.task_id,
        thread_id=approval.thread_id,
        correlation_id=approval.run_id or approval.id,
        producer="modules.observe.approval_repository",
        occurred_at=utc_now(),
        payload={**_approval_payload(approval), "delegated_by": ctx.user_id, "note": note},
    )
    OutboxPublisher(OutboxRepository(db)).publish(envelope)


def enqueue_approval_requested_outbox(
    db: AsyncSession,
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
        workspace_id=ctx.workspace_id,
        subject_type="approval",
        subject_id=approval.id,
        run_id=approval.run_id,
        task_id=approval.task_id,
        thread_id=approval.thread_id,
        correlation_id=correlation,
        producer="modules.observe.approval_repository",
        occurred_at=utc_now(),
        payload=_approval_payload(approval),
    )
    OutboxPublisher(OutboxRepository(db)).publish(envelope)


def enqueue_approval_approved_outbox(
    db: AsyncSession,
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
        workspace_id=ctx.workspace_id,
        subject_type="approval",
        subject_id=approval.id,
        run_id=approval.run_id,
        task_id=approval.task_id,
        thread_id=approval.thread_id,
        correlation_id=correlation,
        producer="modules.observe.approval_repository",
        occurred_at=utc_now(),
        payload=_approval_payload(approval),
    )
    OutboxPublisher(OutboxRepository(db)).publish(envelope)


def enqueue_approval_rejected_outbox(
    db: AsyncSession,
    ctx: RequestContext,
    *,
    approval: ApprovalRequest,
) -> None:
    _enqueue_closed(db, ctx, approval=approval, event_type=ApprovalEventType.REJECTED, label="rejected")


def enqueue_approval_canceled_outbox(
    db: AsyncSession,
    ctx: RequestContext,
    *,
    approval: ApprovalRequest,
) -> None:
    """A request closed without a decision: canceled by a member, or its run ended."""

    _enqueue_closed(db, ctx, approval=approval, event_type=ApprovalEventType.CANCELED, label="canceled")


def enqueue_approval_expired_outbox(
    db: AsyncSession,
    ctx: RequestContext,
    *,
    approval: ApprovalRequest,
) -> None:
    """A request nobody decided before its deadline; it counts as a rejection."""

    _enqueue_closed(db, ctx, approval=approval, event_type=ApprovalEventType.EXPIRED, label="expired")


def _enqueue_closed(
    db: AsyncSession,
    ctx: RequestContext,
    *,
    approval: ApprovalRequest,
    event_type: str,
    label: str,
) -> None:
    event_id = f"evt_approval_{label}_{approval.id}"
    correlation = approval.run_id or approval.id
    envelope = DomainEventEnvelope(
        event_id=event_id,
        event_type=event_type,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        subject_type="approval",
        subject_id=approval.id,
        run_id=approval.run_id,
        task_id=approval.task_id,
        thread_id=approval.thread_id,
        correlation_id=correlation,
        producer="modules.observe.approval_repository",
        occurred_at=utc_now(),
        payload={
            **_approval_payload(approval),
            "resolution_note": approval.resolution_note,
        },
    )
    OutboxPublisher(OutboxRepository(db)).publish(envelope)
