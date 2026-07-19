"""Observe governance service."""

from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import workspace_guard
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.db.models.threads import Thread
from app.kernel.runtime.runs.exporter import to_runtrace_spec
from app.kernel.runtime.status import ApprovalStatus
from app.modules.observe.application.dashboard_service import ObserveDashboardService
from app.modules.observe.application.schemas import (
    ApprovalCreate,
    ApprovalResolve,
    FeedbackCreate,
)
from app.modules.observe.domain.models import ApprovalRequest, RunFeedback
from app.modules.observe.infra.repository import ApprovalRepository, FeedbackRepository


class ObserveService:
    """Approval and feedback management."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx
        self.approval_repo = ApprovalRepository(db, ctx)
        self.feedback_repo = FeedbackRepository(db, ctx)

    def _get_approval(self, approval_id: str) -> ApprovalRequest:
        approval = self.approval_repo.get_by_id(approval_id)
        if not approval:
            raise NotFoundError(f"Approval not found: {approval_id}")
        return approval

    def _get_run(self, run_id: str) -> Run:
        query = select(Run).where(
            and_(
                Run.id == run_id,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
            )
        )
        run = self.db.execute(query).scalars().first()
        if not run:
            raise NotFoundError(f"Run not found: {run_id}")
        return run

    @workspace_guard("write")
    async def create_approval(self, data: ApprovalCreate) -> ApprovalRequest:
        return self.approval_repo.create(
            ApprovalRequest(
                run_id=data.run_id,
                task_id=data.task_id,
                thread_id=data.thread_id,
                agent_id=data.agent_id,
                title=data.title,
                policy_ref=data.policy_ref,
                details_json=data.details_json,
            )
        )

    @workspace_guard("read")
    async def list_approvals(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
    ) -> list[ApprovalRequest]:
        return self.approval_repo.list(limit=limit, offset=offset, status=status, run_id=run_id, task_id=task_id)

    @workspace_guard("read")
    async def get_approval(self, approval_id: str) -> ApprovalRequest:
        return self._get_approval(approval_id)

    @workspace_guard("write")
    async def resolve_approval(self, approval_id: str, data: ApprovalResolve) -> ApprovalRequest:
        approval = self._get_approval(approval_id)
        if approval.status != ApprovalStatus.PENDING.value:
            raise ValidationError("Only pending approvals can be resolved")
        approval.status = data.status
        approval.resolution_note = data.resolution_note
        approval.resolved_by = self.ctx.user_id
        from app.kernel.commons.time import utc_now

        approval.resolved_at = utc_now()
        return self.approval_repo.update(approval, emit_resolution_event=data.status)

    @workspace_guard("write")
    async def resolve_approvals(
        self,
        resolutions: list[tuple[str, ApprovalResolve]],
        *,
        commit: bool = True,
    ) -> list[ApprovalRequest]:
        """Validate and resolve one execution's approvals atomically."""

        approval_ids = [approval_id for approval_id, _ in resolutions]
        if len(approval_ids) != len(set(approval_ids)):
            raise ValidationError("An approval can only be resolved once per request")
        approvals = self.approval_repo.lock_by_ids(approval_ids)
        approvals_by_id = {approval.id: approval for approval in approvals}
        if len(approvals_by_id) != len(approval_ids):
            raise NotFoundError("One or more approvals were not found")

        pending_updates: list[ApprovalRequest] = []
        for approval_id, data in resolutions:
            approval = approvals_by_id[approval_id]
            if approval.status == data.status:
                continue
            if approval.status != ApprovalStatus.PENDING.value:
                raise ValidationError(
                    f"Approval {approval.id} is already resolved as {approval.status}"
                )
            pending_updates.append(approval)

        resolved_at = utc_now()
        data_by_id = dict(resolutions)
        for approval in pending_updates:
            data = data_by_id[approval.id]
            approval.status = data.status
            approval.resolution_note = data.resolution_note
            approval.resolved_by = self.ctx.user_id
            approval.resolved_at = resolved_at
        if pending_updates:
            self.approval_repo.update_many(pending_updates, commit=commit)
        elif commit:
            self.db.commit()
        return [approvals_by_id[approval_id] for approval_id in approval_ids]

    @workspace_guard("write")
    async def create_feedback(self, data: FeedbackCreate) -> RunFeedback:
        run = self._get_run(data.run_id) if data.run_id else None
        task = None
        if data.task_id:
            task = self.db.execute(
                select(Task).where(
                    and_(
                        Task.id == data.task_id,
                        Task.tenant_id == self.ctx.tenant_id,
                        Task.workspace_id == self.ctx.workspace_id,
                    )
                )
            ).scalars().first()
            if task is None:
                raise NotFoundError(f"Task not found: {data.task_id}")
            if run is not None and task.run_id != run.id:
                raise ValidationError("Feedback task does not belong to the referenced Run")
        if data.thread_id:
            thread = self.db.execute(
                select(Thread).where(
                    and_(
                        Thread.id == data.thread_id,
                        Thread.tenant_id == self.ctx.tenant_id,
                        Thread.workspace_id == self.ctx.workspace_id,
                        Thread.deleted_at.is_(None),
                    )
                )
            ).scalars().first()
            if thread is None:
                raise NotFoundError(f"Thread not found: {data.thread_id}")
            if task is not None and task.thread_id != thread.id:
                raise ValidationError("Feedback thread does not belong to the referenced Task")
        if (
            run is not None
            and data.agent_id
            and run.subject_kind == "agent"
            and run.subject_id != data.agent_id
        ):
            raise ValidationError("Feedback Agent does not match the referenced Run")
        return self.feedback_repo.create(
            RunFeedback(
                run_id=data.run_id,
                task_id=data.task_id,
                thread_id=data.thread_id,
                agent_id=data.agent_id,
                rating=data.rating,
                category=data.category,
                comment=data.comment,
                metadata_json=data.metadata_json,
            )
        )

    @workspace_guard("read")
    async def list_feedback(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        run_id: str | None = None,
        agent_id: str | None = None,
        thread_id: str | None = None,
    ) -> list[RunFeedback]:
        return self.feedback_repo.list(
            limit=limit,
            offset=offset,
            run_id=run_id,
            agent_id=agent_id,
            thread_id=thread_id,
        )

    @workspace_guard("read")
    async def get_run_replay(self, run_id: str) -> dict:
        run = self._get_run(run_id)
        steps = list(
            self.db.execute(
                select(RunStep).where(
                    and_(
                        RunStep.run_id == run.id,
                        RunStep.tenant_id == self.ctx.tenant_id,
                        RunStep.workspace_id == self.ctx.workspace_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        artifacts = list(
            self.db.execute(
                select(RunArtifact).where(
                    and_(
                        RunArtifact.run_id == run.id,
                        RunArtifact.tenant_id == self.ctx.tenant_id,
                        RunArtifact.workspace_id == self.ctx.workspace_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        costs = list(
            self.db.execute(
                select(RunCostEntry).where(
                    and_(
                        RunCostEntry.run_id == run.id,
                        RunCostEntry.tenant_id == self.ctx.tenant_id,
                        RunCostEntry.workspace_id == self.ctx.workspace_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        approvals = self.approval_repo.list(limit=200, offset=0, run_id=run.id)
        feedback = self.feedback_repo.list(limit=200, offset=0, run_id=run.id)
        return {
            "run": run,
            "steps": steps,
            "artifacts": artifacts,
            "costs": costs,
            "approvals": approvals,
            "feedback": feedback,
            "trace_spec": to_runtrace_spec(run, steps, artifacts, costs),
        }

    @workspace_guard("read")
    async def get_dashboard(
        self,
        *,
        tab: str = "agent_health",
        range_label: str = "1h",
        bucket_label: str = "10m",
        q: str | None = None,
        workspace_scope: str = "all",
        page_token: str | None = None,
        page_size: int = 10,
    ):
        return await ObserveDashboardService(
            db=self.db,
            ctx=self.ctx,
            approval_repo=self.approval_repo,
        ).build_dashboard(
            tab=tab,
            range_label=range_label,
            bucket_label=bucket_label,
            q=q,
            workspace_scope=workspace_scope,
            page_token=page_token,
            page_size=page_size,
        )
