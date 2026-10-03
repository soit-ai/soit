"""Continue a workflow run when the approval it waits on is decided.

An agent run resumes on its own once its requests are decided; a workflow run
did not: someone had to resume it by hand. This consumer of
``approval.approved``, ``approval.rejected``, ``approval.canceled`` and
``approval.expired`` does it on the server. It claims the run through the same
compare-and-set a manual resume uses, so a member resuming the run at the same
moment, or the event being delivered twice, still continues it once, and then
continues it detached with a renewed lease, as the member who started the
run. Only an approved call runs; any other decision ends the waiting node as
``APPROVAL_REJECTED`` without calling the tool.

The starter is looked up again first: a run whose starter is no longer a
member of the workspace is left waiting for someone to resume it by hand.
"""

from __future__ import annotations

import dataclasses
import logging

from sqlalchemy import event, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import KernelError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run
from app.modules.observe.domain.models import ApprovalRequest
from app.modules.workflow.domain.models import WorkflowRun

logger = logging.getLogger(__name__)


async def _starter_context(run: Run, workflow_run: WorkflowRun) -> RequestContext | None:
    """The starter as of now: their stored context, with today's membership and role."""

    from app.modules.identity.infra.workspace_access import (
        DatabaseWorkspaceAccessResolver,
    )

    stored = dict(workflow_run.request_context_json or {})
    base = (
        RequestContext.from_json(stored)
        if stored
        else RequestContext(tenant_id=run.tenant_id, workspace_id=run.workspace_id, user_id=run.user_id)
    )
    if not base.user_id:
        return None
    try:
        access = await DatabaseWorkspaceAccessResolver().resolve(run.tenant_id, run.workspace_id, base.user_id)
    except KernelError:
        access = None
    if access is None:
        return None
    return dataclasses.replace(
        base,
        tenant_id=run.tenant_id,
        workspace_id=run.workspace_id,
        tenant_role=access.tenant_role,
        workspace_role=access.workspace_role,
        content_capture=access.content_capture,
    )


async def handle_workflow_approval_decision(db: AsyncSession, row: EventOutbox) -> None:
    from app.kernel.commons.errors import ConflictError, NotFoundError, ValidationError
    from app.wiring.services import build_workflow_service
    from app.wiring.workflow_redrive import start_detached_approval_resume

    payload = row.payload_json or {}
    approval_id = payload.get("approval_id") or row.subject_id
    approval = await db.get(ApprovalRequest, approval_id) if approval_id else None
    if approval is None or not approval.run_id:
        return
    run = await db.get(Run, approval.run_id)
    if (
        run is None
        or run.mode != "workflow"
        or run.status != "waiting_approval"
        or run.tenant_id != approval.tenant_id
        or run.workspace_id != approval.workspace_id
    ):
        return
    workflow_run = (
        await db.execute(
            select(WorkflowRun).where(
                WorkflowRun.tenant_id == run.tenant_id,
                WorkflowRun.workspace_id == run.workspace_id,
                WorkflowRun.run_id == run.id,
            )
        )
    ).scalars().first()
    waiting_call = ((workflow_run.checkpoint_json or {}) if workflow_run else {}).get("tool_call_id")
    if (
        workflow_run is None
        or workflow_run.status != "waiting_approval"
        or waiting_call != (approval.details_json or {}).get("tool_call_id")
    ):
        # Not the request this run is waiting on now.
        return
    ctx = await _starter_context(run, workflow_run)
    if ctx is None:
        logger.warning(
            "Not resuming workflow run %s: its starter is no longer a member",
            run.id,
            extra={"run_id": run.id, "approval_id": approval.id},
        )
        return

    # The claim joins the event's transaction: it commits with the consumer's
    # checkpoint, and the run continues only once it has.
    service = build_workflow_service(db=db, ctx=ctx)
    try:
        prepared = await service.prepare_approval_resume(run.id, leased=True, commit=False)
    except (ConflictError, NotFoundError, ValidationError) as exc:
        logger.info(
            "Not resuming workflow run %s: %s",
            run.id,
            exc,
            extra={"run_id": run.id, "approval_id": approval.id},
        )
        return
    bind = db.bind

    def _start(_session) -> None:
        start_detached_approval_resume(bind=bind, ctx=ctx, prepared=prepared)

    event.listen(db.sync_session, "after_commit", _start, once=True)
    logger.info(
        "Resuming workflow run %s on its %s approval",
        run.id,
        prepared.approval_status,
        extra={"run_id": run.id, "approval_id": approval.id},
    )
