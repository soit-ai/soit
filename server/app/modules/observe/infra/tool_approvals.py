"""Approval requests for direct tool calls, kept on the caller's session.

The invocation service commits the run and the waiting tool call before it
opens a request, so the session holds nothing half-done when the approval row
is written; the agent ledger's separate session exists for the opposite case.
"""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.approvals.interface import (
    ApprovalDecision,
    ApprovalRecord,
    ToolApprovalPort,
)
from app.modules.observe.domain.models import ApprovalRequest
from app.modules.observe.infra.repository import ApprovalRepository


class SessionToolApprovals(ToolApprovalPort):
    """Open and read the approval requests of direct tool calls."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def open(self, ctx: RequestContext, record: ApprovalRecord) -> str:
        approval = await ApprovalRepository(self.db, ctx).create(
            ApprovalRequest(
                run_id=record.run_id,
                task_id=record.task_id,
                thread_id=record.thread_id,
                agent_id=record.agent_id,
                title=record.title,
                policy_ref=record.policy_ref,
                details_json={**record.details, "tool_call_id": record.tool_call_id},
            )
        )
        return approval.id

    async def decision_for(
        self,
        ctx: RequestContext,
        *,
        run_id: str,
        tool_call_id: str,
    ) -> ApprovalDecision | None:
        approvals = await ApprovalRepository(self.db, ctx).list(limit=50, offset=0, run_id=run_id)
        for approval in approvals:
            if (approval.details_json or {}).get("tool_call_id") != tool_call_id:
                continue
            return ApprovalDecision(
                approval_id=approval.id,
                status=approval.status,
                resolved_by=approval.resolved_by,
                resolution_note=approval.resolution_note,
            )
        return None
