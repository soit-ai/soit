"""Observability governance service."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import workspace_guard
from app.kernel.runtime.contracts.status import ApprovalStatus
from app.kernel.trace.exporter import to_runtrace_spec
from app.kernel.trace.models import Run, RunArtifact, RunCostEntry, RunStep
from app.modules.observability.application.schemas import ApprovalCreate, ApprovalResolve, FeedbackCreate
from app.modules.observability.domain.models import ApprovalRequest, RunFeedback
from app.modules.observability.infra.repository import ApprovalRepository, FeedbackRepository


class ObservabilityService:
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
        status: Optional[str] = None,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
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
    async def create_feedback(self, data: FeedbackCreate) -> RunFeedback:
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
        run_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
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
