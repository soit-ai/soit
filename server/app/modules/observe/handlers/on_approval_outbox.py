"""Outbox consumers for approval.* (B4: resume / fail waiting tasks)."""

from __future__ import annotations

from sqlmodel import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.tasks.service import TaskService
from app.kernel.runtime.tasks.status import TaskStatus
from app.modules.observe.domain.models import ApprovalRequest


def handle_approval_requested_outbox(_db: Session, _row: EventOutbox) -> None:
    """No side effects in Phase 1; downstream analytics may subscribe later."""
    return None


def handle_approval_approved_outbox(db: Session, row: EventOutbox) -> None:
    payload = row.payload_json or {}
    approval_id = payload.get("approval_id") or row.subject_id
    if not approval_id:
        return
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None or not approval.task_id:
        return
    ctx = RequestContext(
        tenant_id=approval.tenant_id,
        workspace_id=approval.workspace_id,
        user_id=approval.resolved_by or "system",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    core = TaskService(db, ctx)
    task = core.task_repo.get_task(approval.task_id)
    if task is None or task.status != TaskStatus.WAITING_APPROVAL.value:
        return
    core.resume_task(task_id=approval.task_id)


def handle_approval_rejected_outbox(db: Session, row: EventOutbox) -> None:
    payload = row.payload_json or {}
    approval_id = payload.get("approval_id") or row.subject_id
    if not approval_id:
        return
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None or not approval.task_id:
        return
    ctx = RequestContext(
        tenant_id=approval.tenant_id,
        workspace_id=approval.workspace_id,
        user_id=approval.resolved_by or "system",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    core = TaskService(db, ctx)
    task = core.task_repo.get_task(approval.task_id)
    if task is None or task.status != TaskStatus.WAITING_APPROVAL.value:
        return
    note = (approval.resolution_note or "approval rejected").strip() or "approval rejected"
    core.transition_task(
        task_id=approval.task_id,
        status=TaskStatus.FAILED.value,
        error_code="approval_rejected",
        error_message=note[:4096],
    )
