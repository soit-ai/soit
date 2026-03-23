"""Governance repositories for observability domain."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.contracts.status import ApprovalStatus
from app.modules.observability.domain.models import ApprovalRequest, RunFeedback
from app.modules.observability.infra.approval_outbox_emit import (
    enqueue_approval_approved_outbox,
    enqueue_approval_rejected_outbox,
    enqueue_approval_requested_outbox,
)


class ApprovalRepository:
    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, approval: ApprovalRequest) -> ApprovalRequest:
        approval.tenant_id = self.ctx.tenant_id
        approval.workspace_id = self.ctx.workspace_id
        approval.requested_by = approval.requested_by or self.ctx.user_id
        self.db.add(approval)
        self.db.flush()
        enqueue_approval_requested_outbox(self.db, self.ctx, approval=approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def update(
        self,
        approval: ApprovalRequest,
        *,
        emit_resolution_event: Optional[str] = None,
    ) -> ApprovalRequest:
        approval.updated_at = utc_now()
        self.db.add(approval)
        self.db.flush()
        if emit_resolution_event == ApprovalStatus.APPROVED.value:
            enqueue_approval_approved_outbox(self.db, self.ctx, approval=approval)
        elif emit_resolution_event == ApprovalStatus.REJECTED.value:
            enqueue_approval_rejected_outbox(self.db, self.ctx, approval=approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def get_by_id(self, approval_id: str) -> Optional[ApprovalRequest]:
        query = select(ApprovalRequest).where(
            and_(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.tenant_id == self.ctx.tenant_id,
                ApprovalRequest.workspace_id == self.ctx.workspace_id,
            )
        )
        return self.db.execute(query).scalars().first()

    def list(
        self,
        *,
        limit: int,
        offset: int,
        status: Optional[str] = None,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
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
        return list(self.db.execute(query).scalars().all())


class FeedbackRepository:
    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, feedback: RunFeedback) -> RunFeedback:
        feedback.tenant_id = self.ctx.tenant_id
        feedback.workspace_id = self.ctx.workspace_id
        feedback.created_by = feedback.created_by or self.ctx.user_id
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        return feedback

    def list(
        self,
        *,
        limit: int,
        offset: int,
        run_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
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
        return list(self.db.execute(query).scalars().all())
