"""Dead-letter sources for each execution kind.

Each source reads its own terminal failures and decides whether a safe redrive
exists. Where none does, it says so rather than pretending: an unsafe redrive is
worse than none, because the operator would believe the work was recovered.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import ConflictError, NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.responses import ResponseInteraction
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.deadletter.contracts import (
    DeadLetter,
    DeadLetterKind,
    RedriveOutcome,
    RedriveResult,
    register_dead_letter_source,
)
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks.drivers import is_drivable
from app.kernel.runtime.tasks.service import TaskService
from app.modules.knowledge.domain.models import KnowledgeIngestTask
from app.modules.workflow.domain.models import WorkflowRun
from app.modules.workflow.runtime.resume import (
    RESUME_BLOCKED_CHECKPOINT_MISSING,
    ResumeAssessment,
    assess_resume,
)

logger = logging.getLogger(__name__)


class OutboxDeadLetterSource:
    """Outbox rows that exhausted their dispatch attempts."""

    kind = DeadLetterKind.OUTBOX_EVENT
    redrivable = True

    def list_dead_letters(
        self, db: Session, ctx: RequestContext, *, limit: int, offset: int
    ) -> Sequence[DeadLetter]:
        rows = (
            db.execute(
                select(EventOutbox)
                .where(
                    EventOutbox.tenant_id == ctx.tenant_id,
                    EventOutbox.workspace_id == ctx.workspace_id,
                    EventOutbox.status == "failed",
                )
                .order_by(EventOutbox.processed_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return [
            DeadLetter(
                kind=self.kind,
                id=row.id,
                tenant_id=str(row.tenant_id),
                workspace_id=str(row.workspace_id),
                failed_at=row.processed_at,
                error_code=row.failed_consumer_name,
                error_message=row.last_error,
                attempt_count=int(row.attempt_count or 0),
                run_id=row.run_id,
                subject=row.event_type,
                redrivable=True,
            )
            for row in rows
        ]

    def redrive(
        self, db: Session, ctx: RequestContext, dead_letter_id: str
    ) -> RedriveResult:
        # Outbox delivery is idempotent by construction, so returning a row to
        # the queue is safe.
        replayed = OutboxRepository(db).replay_failed(dead_letter_id)
        db.commit()
        if not replayed:
            return RedriveResult(
                outcome=RedriveOutcome.NOT_DEAD,
                detail="Outbox row is not in a terminal failure state",
            )
        return RedriveResult(outcome=RedriveOutcome.REDRIVEN, redriven_as=dead_letter_id)


class TaskDeadLetterSource:
    """Tasks that ended in failure."""

    kind = DeadLetterKind.TASK
    redrivable = True

    def list_dead_letters(
        self, db: Session, ctx: RequestContext, *, limit: int, offset: int
    ) -> Sequence[DeadLetter]:
        rows = (
            db.execute(
                select(Task)
                .where(
                    Task.tenant_id == ctx.tenant_id,
                    Task.workspace_id == ctx.workspace_id,
                    Task.status == TaskStatus.FAILED.value,
                )
                .order_by(Task.finished_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return [
            DeadLetter(
                kind=self.kind,
                id=row.id,
                tenant_id=row.tenant_id,
                workspace_id=row.workspace_id,
                failed_at=row.finished_at,
                error_code=row.error_code,
                error_message=row.error_message,
                run_id=row.run_id,
                subject=row.task_type,
                # Only task types with a registered driver can be re-run.
                redrivable=is_drivable(row.task_type),
                details={"agent_id": row.agent_id, "thread_id": row.thread_id},
            )
            for row in rows
        ]

    def redrive(
        self, db: Session, ctx: RequestContext, dead_letter_id: str
    ) -> RedriveResult:
        service = TaskService(db, ctx)
        task = service.task_repo.get_task(dead_letter_id)
        if task is None:
            return RedriveResult(outcome=RedriveOutcome.NOT_FOUND)
        if task.status != TaskStatus.FAILED.value:
            return RedriveResult(
                outcome=RedriveOutcome.NOT_DEAD,
                detail=f"Task is {task.status}",
            )
        if not is_drivable(task.task_type):
            return RedriveResult(
                outcome=RedriveOutcome.UNSUPPORTED,
                detail=f"No driver re-executes task type {task.task_type!r}",
            )
        retried = service.retry_task(task_id=task.id)
        return RedriveResult(outcome=RedriveOutcome.REDRIVEN, redriven_as=retried.id)


class KnowledgeIngestDeadLetterSource:
    """Ingestion tasks that exhausted their retries."""

    kind = DeadLetterKind.KNOWLEDGE_INGEST
    redrivable = True

    def list_dead_letters(
        self, db: Session, ctx: RequestContext, *, limit: int, offset: int
    ) -> Sequence[DeadLetter]:
        rows = (
            db.execute(
                select(KnowledgeIngestTask)
                .where(
                    KnowledgeIngestTask.tenant_id == ctx.tenant_id,
                    KnowledgeIngestTask.workspace_id == ctx.workspace_id,
                    KnowledgeIngestTask.status == "failed",
                )
                .order_by(KnowledgeIngestTask.finished_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return [
            DeadLetter(
                kind=self.kind,
                id=row.id,
                tenant_id=row.tenant_id,
                workspace_id=row.workspace_id,
                failed_at=row.finished_at,
                error_code=row.error_code,
                error_message=row.error_message,
                attempt_count=int(row.retry_count or 0),
                run_id=row.run_id,
                subject=row.document_id or row.knowledge_id,
                redrivable=True,
            )
            for row in rows
        ]

    def redrive(
        self, db: Session, ctx: RequestContext, dead_letter_id: str
    ) -> RedriveResult:
        task = db.get(KnowledgeIngestTask, dead_letter_id)
        if task is None or task.tenant_id != ctx.tenant_id or task.workspace_id != ctx.workspace_id:
            return RedriveResult(outcome=RedriveOutcome.NOT_FOUND)
        if task.status != "failed":
            return RedriveResult(
                outcome=RedriveOutcome.NOT_DEAD, detail=f"Task is {task.status}"
            )
        # Re-ingesting rebuilds the document's chunks under the same key, so a
        # repeat is not additive.
        now = utc_now()
        task.status = "queued"
        task.error_code = None
        task.error_message = None
        task.started_at = None
        task.finished_at = None
        task.lease_owner = None
        task.lease_expires_at = None
        task.updated_at = now
        db.add(task)
        db.commit()
        return RedriveResult(outcome=RedriveOutcome.REDRIVEN, redriven_as=task.id)


class ResponseInteractionDeadLetterSource:
    """Agent and chat interactions that ended in failure."""

    kind = DeadLetterKind.RESPONSE_INTERACTION
    redrivable = False

    def list_dead_letters(
        self, db: Session, ctx: RequestContext, *, limit: int, offset: int
    ) -> Sequence[DeadLetter]:
        rows = (
            db.execute(
                select(ResponseInteraction)
                .where(
                    ResponseInteraction.tenant_id == ctx.tenant_id,
                    ResponseInteraction.workspace_id == ctx.workspace_id,
                    ResponseInteraction.status == "failed",
                )
                .order_by(ResponseInteraction.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return [
            DeadLetter(
                kind=self.kind,
                id=row.interaction_id,
                tenant_id=row.tenant_id,
                workspace_id=row.workspace_id,
                failed_at=row.updated_at,
                attempt_count=int(row.attempt_count or 0),
                run_id=row.run_id,
                subject=row.thread_id,
                # An interaction has already emitted events to a consumer and
                # may have called tools. Replaying it is a product decision
                # about the conversation, not an infrastructure retry.
                redrivable=False,
            )
            for row in rows
        ]

    def redrive(
        self, db: Session, ctx: RequestContext, dead_letter_id: str
    ) -> RedriveResult:
        return RedriveResult(
            outcome=RedriveOutcome.UNSUPPORTED,
            detail=(
                "A failed interaction is replayed by starting a new one; its "
                "emitted events and tool calls cannot be taken back"
            ),
        )


class WorkflowRunDeadLetterSource:
    """Workflow runs that failed, including those orphaned by a restart.

    A run is redrivable only when resuming it is provably safe: every
    unfinished node must be re-enterable without repeating an external side
    effect. That verdict comes from the node effect vocabulary and the crash
    checkpoint, never from an assumption.
    """

    kind = DeadLetterKind.WORKFLOW_RUN
    redrivable = True

    def _assess(
        self, db: Session, ctx: RequestContext, row: WorkflowRun
    ) -> ResumeAssessment:
        from app.wiring.services import build_workflow_service

        try:
            service = build_workflow_service(db=db, ctx=ctx)
            run = db.get(Run, row.run_id)
            if run is None or not run.subject_version_id:
                return ResumeAssessment(False, RESUME_BLOCKED_CHECKPOINT_MISSING)
            version = service.version_repo.get_by_id(run.subject_version_id)
            if version is None:
                return ResumeAssessment(False, RESUME_BLOCKED_CHECKPOINT_MISSING)
            checkpoint = dict(row.checkpoint_json or {})
            inputs = checkpoint.get("inputs")
            plan = service.compiler.compile(
                version.spec_json,
                inputs if isinstance(inputs, dict) else dict(row.inputs_json or {}),
                row.run_id,
            )
            return assess_resume(
                plan.plan_data.get("nodes") or {},
                plan.plan_data.get("semantics") or {},
                checkpoint,
            )
        except Exception:
            # A listing must never fail because one row cannot be planned;
            # report it as not resumable and keep the rest readable.
            logger.exception(
                "Workflow resume assessment failed",
                extra={"workflow_run_id": row.id},
            )
            return ResumeAssessment(False, RESUME_BLOCKED_CHECKPOINT_MISSING)

    def list_dead_letters(
        self, db: Session, ctx: RequestContext, *, limit: int, offset: int
    ) -> Sequence[DeadLetter]:
        rows = (
            db.execute(
                select(WorkflowRun)
                .where(
                    WorkflowRun.tenant_id == ctx.tenant_id,
                    WorkflowRun.workspace_id == ctx.workspace_id,
                    WorkflowRun.status == "failed",
                )
                .order_by(WorkflowRun.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        letters: list[DeadLetter] = []
        for row in rows:
            assessment = self._assess(db, ctx, row)
            details: dict[str, object] = {
                "completed_nodes": row.completed_nodes,
                "total_nodes": row.total_nodes,
            }
            if not assessment.resumable:
                details["resume_blocked_reason"] = assessment.reason_code
                details["resume_blocking_node_ids"] = assessment.blocking_node_ids
            letters.append(
                DeadLetter(
                    kind=self.kind,
                    id=row.id,
                    tenant_id=row.tenant_id,
                    workspace_id=row.workspace_id,
                    failed_at=row.updated_at,
                    attempt_count=int(row.attempt_count or 0),
                    run_id=row.run_id,
                    subject=row.workflow_id,
                    redrivable=assessment.resumable,
                    details=details,
                )
            )
        return letters

    def redrive(
        self, db: Session, ctx: RequestContext, dead_letter_id: str
    ) -> RedriveResult:
        from app.wiring.services import build_workflow_service
        from app.wiring.workflow_redrive import start_detached_redrive

        row = db.get(WorkflowRun, dead_letter_id)
        if row is None or row.tenant_id != ctx.tenant_id or row.workspace_id != ctx.workspace_id:
            return RedriveResult(outcome=RedriveOutcome.NOT_FOUND)
        if row.status != "failed":
            return RedriveResult(
                outcome=RedriveOutcome.NOT_DEAD,
                detail=f"Workflow run is {row.status}",
            )
        service = build_workflow_service(db=db, ctx=ctx)
        try:
            prepared = service.prepare_redrive(dead_letter_id)
        except ValidationError as exc:
            # Resuming would risk repeating a side effect, or the checkpoint
            # cannot carry the run forward. Say which, rather than pretending
            # the work was recovered.
            return RedriveResult(outcome=RedriveOutcome.UNSUPPORTED, detail=str(exc))
        except ConflictError as exc:
            return RedriveResult(outcome=RedriveOutcome.NOT_DEAD, detail=str(exc))
        except NotFoundError as exc:
            # The dead letter itself exists — it was listed above — so this is
            # a missing dependency (run record or pinned version), not a bad
            # id. Reporting NOT_FOUND here would tell the operator the wrong
            # thing about a row they can see.
            return RedriveResult(
                outcome=RedriveOutcome.UNSUPPORTED,
                detail=f"Workflow run cannot be resumed: {exc}",
            )

        start_detached_redrive(
            bind=db.get_bind(),
            ctx=ctx,
            plan=prepared.plan,
            workflow_run_id=prepared.workflow_run_id,
            checkpoint=prepared.checkpoint,
        )
        return RedriveResult(
            outcome=RedriveOutcome.REDRIVEN, redriven_as=prepared.workflow_run_id
        )


def register_dead_letter_sources() -> None:
    """Register every execution kind that can produce a dead letter."""
    for source in (
        OutboxDeadLetterSource(),
        TaskDeadLetterSource(),
        KnowledgeIngestDeadLetterSource(),
        ResponseInteractionDeadLetterSource(),
        WorkflowRunDeadLetterSource(),
    ):
        register_dead_letter_source(source)
