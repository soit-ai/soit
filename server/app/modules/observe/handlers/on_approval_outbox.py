"""Outbox consumers for approval.* (B4: resume / fail waiting tasks)."""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks.service import TaskService
from app.modules.observe.domain.models import ApprovalRequest


async def handle_approval_requested_outbox(_db: AsyncSession, _row: EventOutbox) -> None:
    """No side effects in Phase 1; downstream analytics may subscribe later."""
    return None


async def _waiting_task_service(
    db: AsyncSession, row: EventOutbox
) -> tuple[TaskService, ApprovalRequest] | None:
    payload = row.payload_json or {}
    approval_id = payload.get("approval_id") or row.subject_id
    if not approval_id:
        return None
    approval = await db.get(ApprovalRequest, approval_id)
    if approval is None or not approval.task_id:
        return None
    ctx = RequestContext(
        tenant_id=approval.tenant_id,
        workspace_id=approval.workspace_id,
        user_id=approval.resolved_by or "system",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    core = TaskService(db, ctx)
    task = await core.task_repo.get_task(approval.task_id)
    if task is None or task.status != TaskStatus.WAITING_APPROVAL.value:
        return None
    return core, approval


async def handle_approval_approved_outbox(db: AsyncSession, row: EventOutbox) -> None:
    resolved = await _waiting_task_service(db, row)
    if resolved is None:
        return
    core, approval = resolved
    await core.resume_task(task_id=approval.task_id)


async def handle_approval_rejected_outbox(db: AsyncSession, row: EventOutbox) -> None:
    resolved = await _waiting_task_service(db, row)
    if resolved is None:
        return
    core, approval = resolved
    note = (approval.resolution_note or "approval rejected").strip() or "approval rejected"
    await core.transition_task(
        task_id=approval.task_id,
        status=TaskStatus.FAILED.value,
        error_code="approval_rejected",
        error_message=note[:4096],
    )
