"""Outbox consumers for approval.*: resume or fail the task a decision unblocks.

An agent run that stopped for approval resumes through a child interaction
that carries the decisions. When the decisions arrive from the AG-UI client
that child is built by the transport; when they are taken anywhere else (the
approvals page, a task page, the API) this consumer builds it from the paused
interaction's snapshot and queues it for the durable interaction worker, so
the run continues with no client connected. It waits until every approval
the run is waiting on has been decided, and a rejection resumes the run too:
the agent records the refused tool call and finishes its turn.

Tasks without a paused agent interaction keep the direct transitions: an
approval marks the task running and a rejection fails it.
"""

from __future__ import annotations

import logging

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import ConflictError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.responses import (
    ResponseInteraction,
    generate_response_interaction_id,
)
from app.kernel.runtime.db.models.threads import generate_thread_message_id
from app.kernel.runtime.responses.approval_resume import (
    approval_resume_entry,
    build_resume_execution_json,
)
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.status import ApprovalStatus, TaskStatus
from app.kernel.runtime.tasks.service import TaskService
from app.modules.observe.domain.models import ApprovalRequest

logger = logging.getLogger(__name__)

WAITING_INTERACTION = "waiting_approval"


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


async def _pending_approval_count(db: AsyncSession, approval: ApprovalRequest) -> int:
    query = (
        select(func.count())
        .select_from(ApprovalRequest)
        .where(
            ApprovalRequest.tenant_id == approval.tenant_id,
            ApprovalRequest.workspace_id == approval.workspace_id,
            ApprovalRequest.run_id == approval.run_id,
            ApprovalRequest.task_id == approval.task_id,
            ApprovalRequest.status == ApprovalStatus.PENDING.value,
        )
    )
    row = (await db.exec(query)).one()
    return int(row if isinstance(row, int) else row[0])


async def _decided_approvals(db: AsyncSession, approval: ApprovalRequest) -> list[ApprovalRequest]:
    query = select(ApprovalRequest).where(
        ApprovalRequest.tenant_id == approval.tenant_id,
        ApprovalRequest.workspace_id == approval.workspace_id,
        ApprovalRequest.run_id == approval.run_id,
        ApprovalRequest.task_id == approval.task_id,
        ApprovalRequest.status != ApprovalStatus.PENDING.value,
    )
    rows = (await db.exec(query)).all()
    return [item if isinstance(item, ApprovalRequest) else item[0] for item in rows]


async def _latest_agent_interaction(
    db: AsyncSession, approval: ApprovalRequest
) -> ResponseInteraction | None:
    """The newest agent interaction of the approval's run, whatever its state."""

    if not approval.run_id:
        return None
    query = (
        select(ResponseInteraction)
        .where(
            ResponseInteraction.tenant_id == approval.tenant_id,
            ResponseInteraction.workspace_id == approval.workspace_id,
            ResponseInteraction.run_id == approval.run_id,
        )
        .order_by(ResponseInteraction.created_at.desc())
        .limit(1)
    )
    row = (await db.exec(query)).first()
    interaction = row if isinstance(row, ResponseInteraction) else row[0] if row else None
    if interaction is None:
        return None
    job = interaction.execution_json or {}
    if job.get("mode") != "agent" or not job.get("agent_id") or not interaction.response_id:
        return None
    return interaction


def _interaction_context(interaction: ResponseInteraction) -> RequestContext:
    stored = dict(interaction.request_context_json or {})
    if stored:
        return RequestContext(**stored)
    return RequestContext(
        tenant_id=interaction.tenant_id,
        workspace_id=interaction.workspace_id,
        user_id=interaction.created_by or "system",
        tenant_role="Owner",
        workspace_role="Owner",
    )


async def _queue_agent_resume(
    db: AsyncSession,
    approval: ApprovalRequest,
    parent: ResponseInteraction,
) -> None:
    """Queue the child interaction that continues ``parent`` with its decisions."""

    decided = await _decided_approvals(db, approval)
    entries = [
        approval_resume_entry(
            interrupt_id=str((item.details_json or {}).get("interrupt_id")),
            approval_id=item.id,
            approval_status=item.status,
        )
        for item in decided
        if (item.details_json or {}).get("interrupt_id")
    ]
    if not entries:
        logger.warning(
            "Approvals for run %s carry no interrupt ids; nothing can resume it",
            approval.run_id,
            extra={"run_id": approval.run_id, "task_id": approval.task_id},
        )
        return

    # The paused run executes again as the member who started it; the
    # decisions themselves are recorded against whoever took them.
    ctx = _interaction_context(parent)
    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )
    response = await response_service.get_response(str(parent.response_id))
    if response.status != "running" or response.task_id != approval.task_id:
        logger.warning(
            "Paused response %s is %s; not resuming",
            response.id,
            response.status,
            extra={"run_id": approval.run_id, "task_id": approval.task_id},
        )
        return

    child_id = generate_response_interaction_id()
    execution_json = build_resume_execution_json(
        dict(parent.execution_json or {}),
        entries=entries,
        resume_execution={
            "run_id": str(response.run_id or ""),
            "task_id": str(response.task_id or ""),
            "thread_id": str(response.thread_id or parent.thread_id or ""),
            "agent_id": str(response.agent_id or (parent.execution_json or {}).get("agent_id") or ""),
            "response_id": response.id,
        },
        assistant_message_id=generate_thread_message_id(),
    )
    try:
        # Compare-and-set on the parent: a client resuming the same checkpoint
        # through AG-UI and this consumer cannot both continue it.
        await response_service.claim_interaction_resume(
            parent_interaction_id=parent.interaction_id,
            resume_interaction_id=child_id,
        )
    except ConflictError:
        logger.info(
            "Approval checkpoint of interaction %s is already resuming",
            parent.interaction_id,
            extra={"run_id": approval.run_id},
        )
        return
    await response_service.claim_interaction(
        interaction_id=child_id,
        parent_interaction_id=parent.interaction_id,
        thread_id=parent.thread_id,
        request_hash=child_id,
        execution_json=execution_json,
        request_context_json=dict(parent.request_context_json or {}),
        kind=parent.kind or "run",
        # The dispatcher commits the claim with the event it is consuming.
        commit=False,
    )
    logger.info(
        "Queued interaction %s to resume run %s after approval",
        child_id,
        approval.run_id,
        extra={"run_id": approval.run_id, "task_id": approval.task_id},
    )


async def _on_decision(db: AsyncSession, row: EventOutbox, *, approved: bool) -> None:
    resolved = await _waiting_task_service(db, row)
    if resolved is None:
        return
    core, approval = resolved
    interaction = await _latest_agent_interaction(db, approval)
    if interaction is not None:
        # An agent run continues only through its paused interaction. Any
        # other state means a client resume already owns the checkpoint.
        if interaction.status != WAITING_INTERACTION:
            return
        if await _pending_approval_count(db, approval):
            return
        await _queue_agent_resume(db, approval, interaction)
        return
    if approved:
        await core.resume_task(task_id=approval.task_id)
        return
    note = (approval.resolution_note or "approval rejected").strip() or "approval rejected"
    await core.transition_task(
        task_id=approval.task_id,
        status=TaskStatus.FAILED.value,
        error_code="approval_rejected",
        error_message=note[:4096],
    )


async def handle_approval_approved_outbox(db: AsyncSession, row: EventOutbox) -> None:
    await _on_decision(db, row, approved=True)


async def handle_approval_rejected_outbox(db: AsyncSession, row: EventOutbox) -> None:
    await _on_decision(db, row, approved=False)
