"""Governance repositories for observe domain."""

from __future__ import annotations

from sqlalchemy import and_, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.status import ApprovalStatus
from app.modules.observe.domain.approval_policy import reminder_time
from app.modules.observe.domain.models import (
    ApprovalDecision,
    ApprovalRequest,
    RunFeedback,
)
from app.modules.observe.infra.approval_outbox_emit import (
    enqueue_approval_approved_outbox,
    enqueue_approval_canceled_outbox,
    enqueue_approval_expired_outbox,
    enqueue_approval_rejected_outbox,
    enqueue_approval_requested_outbox,
)
from app.settings.settings import settings


class ApprovalRepository:
    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def create(self, approval: ApprovalRequest) -> ApprovalRequest:
        approval.tenant_id = self.ctx.tenant_id
        approval.workspace_id = self.ctx.workspace_id
        approval.requested_by = approval.requested_by or self.ctx.user_id
        if approval.expires_at is not None and approval.remind_at is None:
            approval.remind_at = reminder_time(
                approval.created_at, approval.expires_at, settings.approval_reminder_lead_seconds
            )
        self.db.add(approval)
        await self.db.flush()
        enqueue_approval_requested_outbox(self.db, self.ctx, approval=approval)
        await self.db.commit()
        return approval

    async def update(
        self,
        approval: ApprovalRequest,
        *,
        emit_resolution_event: str | None = None,
    ) -> ApprovalRequest:
        approval.updated_at = utc_now()
        self.db.add(approval)
        await self.db.flush()
        if emit_resolution_event == ApprovalStatus.APPROVED.value:
            enqueue_approval_approved_outbox(self.db, self.ctx, approval=approval)
        elif emit_resolution_event == ApprovalStatus.REJECTED.value:
            enqueue_approval_rejected_outbox(self.db, self.ctx, approval=approval)
        elif emit_resolution_event == ApprovalStatus.CANCELED.value:
            enqueue_approval_canceled_outbox(self.db, self.ctx, approval=approval)
        elif emit_resolution_event == ApprovalStatus.EXPIRED.value:
            enqueue_approval_expired_outbox(self.db, self.ctx, approval=approval)
        await self.db.commit()
        return approval

    def add_decision(
        self,
        approval: ApprovalRequest,
        *,
        action: str,
        actor_id: str | None,
        actor_role: str | None,
        note: str | None = None,
        assignees_before: dict | None = None,
        assignees_after: dict | None = None,
    ) -> ApprovalDecision:
        """Add one entry to the request's history; written with the caller's commit."""

        entry = ApprovalDecision(
            tenant_id=approval.tenant_id,
            workspace_id=approval.workspace_id,
            approval_id=approval.id,
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            note=note,
            assignees_before_json=dict(assignees_before or {}),
            assignees_after_json=dict(assignees_after or {}),
        )
        self.db.add(entry)
        return entry

    async def list_decisions(self, approval_id: str) -> list[ApprovalDecision]:
        query = (
            select(ApprovalDecision)
            .where(
                and_(
                    ApprovalDecision.tenant_id == self.ctx.tenant_id,
                    ApprovalDecision.workspace_id == self.ctx.workspace_id,
                    ApprovalDecision.approval_id == approval_id,
                )
            )
            .order_by(ApprovalDecision.created_at, ApprovalDecision.id)
        )
        return list((await self.db.execute(query)).scalars().all())

    async def lock_by_ids(self, approval_ids: list[str]) -> list[ApprovalRequest]:
        """Lock scoped approvals so a resume decision can be applied atomically."""

        if not approval_ids:
            return []
        query = (
            select(ApprovalRequest)
            .where(
                and_(
                    ApprovalRequest.tenant_id == self.ctx.tenant_id,
                    ApprovalRequest.workspace_id == self.ctx.workspace_id,
                    ApprovalRequest.id.in_(approval_ids),
                )
            )
            .with_for_update()
            # A row this session already holds is read again under the lock.
            .execution_options(populate_existing=True)
        )
        return list((await self.db.execute(query)).scalars().all())

    async def update_many(
        self,
        approvals: list[ApprovalRequest],
        *,
        commit: bool = True,
    ) -> list[ApprovalRequest]:
        """Persist validated approval decisions in one transaction."""

        for approval in approvals:
            approval.updated_at = utc_now()
            self.db.add(approval)
        await self.db.flush()
        for approval in approvals:
            if approval.status == ApprovalStatus.APPROVED.value:
                enqueue_approval_approved_outbox(self.db, self.ctx, approval=approval)
            elif approval.status == ApprovalStatus.REJECTED.value:
                enqueue_approval_rejected_outbox(self.db, self.ctx, approval=approval)
            elif approval.status == ApprovalStatus.CANCELED.value:
                enqueue_approval_canceled_outbox(self.db, self.ctx, approval=approval)
        if commit:
            await self.db.commit()
        return approvals

    async def get_by_id(self, approval_id: str) -> ApprovalRequest | None:
        query = select(ApprovalRequest).where(
            and_(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.tenant_id == self.ctx.tenant_id,
                ApprovalRequest.workspace_id == self.ctx.workspace_id,
            )
        )
        return (await self.db.execute(query)).scalars().first()

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
    ) -> list[ApprovalRequest]:
        filters = [
            ApprovalRequest.tenant_id == self.ctx.tenant_id,
            ApprovalRequest.workspace_id == self.ctx.workspace_id,
        ]
        if status:
            filters.append(ApprovalRequest.status == status)
        if run_id:
            filters.append(ApprovalRequest.run_id == run_id)
        if task_id:
            filters.append(ApprovalRequest.task_id == task_id)
        query = (
            select(ApprovalRequest)
            .where(and_(*filters))
            .order_by(desc(ApprovalRequest.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(query)).scalars().all())


class FeedbackRepository:
    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def create(self, feedback: RunFeedback) -> RunFeedback:
        feedback.tenant_id = self.ctx.tenant_id
        feedback.workspace_id = self.ctx.workspace_id
        feedback.created_by = feedback.created_by or self.ctx.user_id
        self.db.add(feedback)
        await self.db.commit()
        return feedback

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        run_id: str | None = None,
        agent_id: str | None = None,
        thread_id: str | None = None,
    ) -> list[RunFeedback]:
        filters = [
            RunFeedback.tenant_id == self.ctx.tenant_id,
            RunFeedback.workspace_id == self.ctx.workspace_id,
        ]
        if run_id:
            filters.append(RunFeedback.run_id == run_id)
        if agent_id:
            filters.append(RunFeedback.agent_id == agent_id)
        if thread_id:
            filters.append(RunFeedback.thread_id == thread_id)
        query = (
            select(RunFeedback)
            .where(and_(*filters))
            .order_by(desc(RunFeedback.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(query)).scalars().all())
