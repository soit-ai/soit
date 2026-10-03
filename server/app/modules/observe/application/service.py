"""Observe governance service."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import (
    ConflictError,
    ForbiddenError,
    KernelError,
    NotFoundError,
    ValidationError,
)
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import workspace_guard
from app.kernel.identity.workspace_access import WorkspaceAccessResolver
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.db.models.threads import Thread
from app.kernel.runtime.runs.exporter import to_runtrace_spec
from app.kernel.runtime.runs.knowledge_redaction import (
    KnowledgeRedactor,
    redacted_step_rows,
)
from app.kernel.runtime.status import ApprovalStatus
from app.modules.observe.application.approval_sweeper import close_as_expired
from app.modules.observe.application.dashboard_service import ObserveDashboardService
from app.modules.observe.application.schemas import (
    ApprovalCreate,
    ApprovalDelegate,
    ApprovalResolve,
    FeedbackCreate,
)
from app.modules.observe.domain.approval_policy import (
    APPROVER_ROLES,
    assignees,
    may_cancel,
    may_decide,
    normalize_roles,
    normalize_users,
)
from app.modules.observe.domain.models import (
    ApprovalDecision,
    ApprovalRequest,
    RunFeedback,
)
from app.modules.observe.infra.approval_outbox_emit import (
    enqueue_approval_delegated_outbox,
)
from app.modules.observe.infra.repository import ApprovalRepository, FeedbackRepository

DELEGATED = "delegated"


def aware_utc(value: datetime) -> datetime:
    """A time given without a zone is read as UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _overdue(approval: ApprovalRequest) -> bool:
    return approval.expires_at is not None and aware_utc(approval.expires_at) <= utc_now()


class ObserveService:
    """Approval and feedback management."""

    def __init__(
        self,
        db: AsyncSession,
        ctx: RequestContext,
        member_access: WorkspaceAccessResolver | None = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.member_access = member_access
        self.approval_repo = ApprovalRepository(db, ctx)
        self.feedback_repo = FeedbackRepository(db, ctx)

    async def _get_approval(self, approval_id: str) -> ApprovalRequest:
        approval = await self.approval_repo.get_by_id(approval_id)
        if not approval:
            raise NotFoundError(f"Approval not found: {approval_id}")
        return approval

    async def _get_run(self, run_id: str) -> Run:
        query = select(Run).where(
            and_(
                Run.id == run_id,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
            )
        )
        run = (await self.db.execute(query)).scalars().first()
        if not run:
            raise NotFoundError(f"Run not found: {run_id}")
        return run

    @workspace_guard("write")
    async def create_approval(self, data: ApprovalCreate) -> ApprovalRequest:
        try:
            roles = normalize_roles(data.assignee_roles)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        expires_at = aware_utc(data.expires_at) if data.expires_at else None
        if expires_at is not None and expires_at <= utc_now():
            raise ValidationError("expires_at must be in the future")
        return await self.approval_repo.create(
            ApprovalRequest(
                run_id=data.run_id,
                task_id=data.task_id,
                thread_id=data.thread_id,
                agent_id=data.agent_id,
                title=data.title,
                policy_ref=data.policy_ref,
                details_json=data.details_json,
                assignee_user_ids=normalize_users(data.assignee_user_ids),
                assignee_roles=roles,
                expires_at=expires_at,
            )
        )

    def _require_may_resolve(self, approval: ApprovalRequest, status: str) -> None:
        allowed = may_cancel(approval, self.ctx) if status == ApprovalStatus.CANCELED.value else may_decide(
            approval, self.ctx
        )
        if not allowed:
            raise ForbiddenError(f"You are not an approver of request {approval.id}")

    def _record(self, approval: ApprovalRequest, action: str, note: str | None) -> None:
        self.approval_repo.add_decision(
            approval,
            action=action,
            actor_id=self.ctx.user_id,
            actor_role=self.ctx.workspace_role,
            note=note,
            assignees_before=assignees(approval),
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
        return await self.approval_repo.list(limit=limit, offset=offset, status=status, run_id=run_id, task_id=task_id)

    @workspace_guard("read")
    async def get_approval(self, approval_id: str) -> ApprovalRequest:
        return await self._get_approval(approval_id)

    @workspace_guard("write")
    async def resolve_approval(self, approval_id: str, data: ApprovalResolve) -> ApprovalRequest:
        """Decide one request; of two concurrent decisions exactly one is taken.

        The row is locked before it is read, so the decision is checked and
        written in one step. The same decision again is answered with the
        request as it stands and changes nothing; a different one, once the
        request is closed, is a conflict.
        """

        locked = await self.approval_repo.lock_by_ids([approval_id])
        if not locked:
            raise NotFoundError(f"Approval not found: {approval_id}")
        approval = locked[0]
        try:
            self._require_may_resolve(approval, data.status)
        except ForbiddenError:
            await self.db.rollback()
            raise
        if approval.status == data.status:
            await self.db.commit()
            return approval
        if approval.status != ApprovalStatus.PENDING.value:
            message = f"Approval {approval.id} is already {approval.status}"
            await self.db.rollback()
            raise ConflictError(message)
        if _overdue(approval):
            # Past its deadline it was never approvable; close it the way the
            # sweeper would and tell the caller.
            message = f"Approval {approval.id} expired at {approval.expires_at}"
            close_as_expired(self.db, approval, now=utc_now())
            await self.db.commit()
            raise ConflictError(message)
        self._record(approval, data.status, data.resolution_note)
        approval.status = data.status
        approval.resolution_note = data.resolution_note
        approval.resolved_by = self.ctx.user_id
        approval.resolved_at = utc_now()
        return await self.approval_repo.update(approval, emit_resolution_event=data.status)

    @workspace_guard("write")
    async def delegate_approval(self, approval_id: str, data: ApprovalDelegate) -> ApprovalRequest:
        """Hand a pending request to one member, who becomes its only approver.

        Only someone who may decide the request delegates it, to a current
        member who can decide (an Owner, Admin or Dev). The delegation is
        recorded with the approvers before and after it.
        """

        locked = await self.approval_repo.lock_by_ids([approval_id])
        if not locked:
            raise NotFoundError(f"Approval not found: {approval_id}")
        approval = locked[0]
        failure: Exception | None = None
        target = data.user_id.strip()
        if not may_decide(approval, self.ctx):
            failure = ForbiddenError(f"You are not an approver of request {approval.id}")
        elif approval.status != ApprovalStatus.PENDING.value:
            failure = ConflictError(f"Approval {approval.id} is already {approval.status}")
        elif _overdue(approval):
            failure = ConflictError(f"Approval {approval.id} expired at {approval.expires_at}")
        elif target == self.ctx.user_id:
            failure = ValidationError("A request cannot be delegated to yourself")
        elif not await self._can_be_approver(target):
            failure = ValidationError(f"{target} is not a member of this workspace who can decide requests")
        if failure is not None:
            await self.db.rollback()
            raise failure
        before = assignees(approval)
        approval.assignee_user_ids = [target]
        approval.assignee_roles = []
        entry = self.approval_repo.add_decision(
            approval,
            action=DELEGATED,
            actor_id=self.ctx.user_id,
            actor_role=self.ctx.workspace_role,
            note=data.note,
            assignees_before=before,
            assignees_after=assignees(approval),
        )
        enqueue_approval_delegated_outbox(self.db, self.ctx, approval=approval, decision_id=entry.id, note=data.note)
        return await self.approval_repo.update(approval)

    async def _can_be_approver(self, user_id: str) -> bool:
        if self.member_access is None:
            return False
        try:
            access = await self.member_access.resolve(self.ctx.tenant_id, self.ctx.workspace_id, user_id)
        except KernelError:
            return False
        return access is not None and access.workspace_role in APPROVER_ROLES

    @workspace_guard("read")
    async def list_approval_decisions(self, approval_id: str) -> list[ApprovalDecision]:
        await self._get_approval(approval_id)
        return await self.approval_repo.list_decisions(approval_id)

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
        approvals = await self.approval_repo.lock_by_ids(approval_ids)
        approvals_by_id = {approval.id: approval for approval in approvals}
        if len(approvals_by_id) != len(approval_ids):
            raise NotFoundError("One or more approvals were not found")

        pending_updates: list[ApprovalRequest] = []
        for approval_id, data in resolutions:
            approval = approvals_by_id[approval_id]
            self._require_may_resolve(approval, data.status)
            if approval.status == data.status:
                continue
            if approval.status != ApprovalStatus.PENDING.value:
                raise ValidationError(
                    f"Approval {approval.id} is already resolved as {approval.status}"
                )
            if _overdue(approval):
                raise ConflictError(f"Approval {approval.id} expired at {approval.expires_at}")
            pending_updates.append(approval)

        resolved_at = utc_now()
        data_by_id = dict(resolutions)
        for approval in pending_updates:
            data = data_by_id[approval.id]
            self._record(approval, data.status, data.resolution_note)
            approval.status = data.status
            approval.resolution_note = data.resolution_note
            approval.resolved_by = self.ctx.user_id
            approval.resolved_at = resolved_at
        if pending_updates:
            await self.approval_repo.update_many(pending_updates, commit=commit)
        elif commit:
            await self.db.commit()
        return [approvals_by_id[approval_id] for approval_id in approval_ids]

    @workspace_guard("write")
    async def create_feedback(self, data: FeedbackCreate) -> RunFeedback:
        run = await self._get_run(data.run_id) if data.run_id else None
        task = None
        if data.task_id:
            task = (await self.db.execute(
                select(Task).where(
                    and_(
                        Task.id == data.task_id,
                        Task.tenant_id == self.ctx.tenant_id,
                        Task.workspace_id == self.ctx.workspace_id,
                    )
                )
            )).scalars().first()
            if task is None:
                raise NotFoundError(f"Task not found: {data.task_id}")
            if run is not None and task.run_id != run.id:
                raise ValidationError("Feedback task does not belong to the referenced Run")
        if data.thread_id:
            thread = (await self.db.execute(
                select(Thread).where(
                    and_(
                        Thread.id == data.thread_id,
                        Thread.tenant_id == self.ctx.tenant_id,
                        Thread.workspace_id == self.ctx.workspace_id,
                        Thread.deleted_at.is_(None),
                    )
                )
            )).scalars().first()
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
        return await self.feedback_repo.create(
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
        return await self.feedback_repo.list(
            limit=limit,
            offset=offset,
            run_id=run_id,
            agent_id=agent_id,
            thread_id=thread_id,
        )

    @workspace_guard("read")
    async def get_run_replay(self, run_id: str) -> dict:
        run = await self._get_run(run_id)
        steps = list(
            (await self.db.execute(
                select(RunStep).where(
                    and_(
                        RunStep.run_id == run.id,
                        RunStep.tenant_id == self.ctx.tenant_id,
                        RunStep.workspace_id == self.ctx.workspace_id,
                    )
                )
            ))
            .scalars()
            .all()
        )
        artifacts = list(
            (await self.db.execute(
                select(RunArtifact).where(
                    and_(
                        RunArtifact.run_id == run.id,
                        RunArtifact.tenant_id == self.ctx.tenant_id,
                        RunArtifact.workspace_id == self.ctx.workspace_id,
                    )
                )
            ))
            .scalars()
            .all()
        )
        costs = list(
            (await self.db.execute(
                select(RunCostEntry).where(
                    and_(
                        RunCostEntry.run_id == run.id,
                        RunCostEntry.tenant_id == self.ctx.tenant_id,
                        RunCostEntry.workspace_id == self.ctx.workspace_id,
                    )
                )
            ))
            .scalars()
            .all()
        )
        approvals = await self.approval_repo.list(limit=200, offset=0, run_id=run.id)
        feedback = await self.feedback_repo.list(limit=200, offset=0, run_id=run.id)
        # Knowledge text the reader may no longer read is withheld from the replay.
        steps = await redacted_step_rows(KnowledgeRedactor(self.db, self.ctx), steps)
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
