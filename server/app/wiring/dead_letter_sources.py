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

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.responses import ResponseInteraction
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
    """Workflow runs that failed, including those orphaned by a restart."""

    kind = DeadLetterKind.WORKFLOW_RUN
    redrivable = False

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
        return [
            DeadLetter(
                kind=self.kind,
                id=row.id,
                tenant_id=row.tenant_id,
                workspace_id=row.workspace_id,
                failed_at=row.updated_at,
                attempt_count=int(row.attempt_count or 0),
                run_id=row.run_id,
                subject=row.workflow_id,
                # Nodes cause external side effects and per-node idempotency
                # across attempts is undefined, so an automatic replay could
                # repeat them. Re-running is the operator's deliberate call.
                redrivable=False,
                details={"completed_nodes": row.completed_nodes, "total_nodes": row.total_nodes},
            )
            for row in rows
        ]

    def redrive(
        self, db: Session, ctx: RequestContext, dead_letter_id: str
    ) -> RedriveResult:
        return RedriveResult(
            outcome=RedriveOutcome.UNSUPPORTED,
            detail=(
                "Workflow nodes cause external side effects and have no "
                "cross-attempt idempotency, so a run must be restarted "
                "deliberately rather than replayed automatically"
            ),
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
