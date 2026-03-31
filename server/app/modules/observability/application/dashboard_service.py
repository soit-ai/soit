"""Workspace dashboard aggregation for observability."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.contracts.status import ApprovalStatus
from app.kernel.trace.models import Run, RunCostEntry, RunStep
from app.modules.observability.application.dashboard_schemas import (
    AgentSummaryResponse,
    ApprovalsSummaryResponse,
    KnowledgeQualityResponse,
    ModelCostResponse,
    ToolHealthResponse,
    WorkflowBottleneckResponse,
    WorkspaceObservabilityDashboard,
    WorkspaceSummaryResponse,
)
from app.modules.observability.infra.repository import ApprovalRepository, FeedbackRepository


class ObservabilityDashboardService:
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        approval_repo: ApprovalRepository,
        feedback_repo: FeedbackRepository,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.approval_repo = approval_repo
        self.feedback_repo = feedback_repo

    def _scoped_runs(self) -> list[Run]:
        return list(
            self.db.execute(
                select(Run).where(
                    and_(
                        Run.tenant_id == self.ctx.tenant_id,
                        Run.workspace_id == self.ctx.workspace_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    def _scoped_steps(self) -> list[RunStep]:
        return list(
            self.db.execute(
                select(RunStep).where(
                    and_(
                        RunStep.tenant_id == self.ctx.tenant_id,
                        RunStep.workspace_id == self.ctx.workspace_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    def _scoped_costs(self) -> list[RunCostEntry]:
        return list(
            self.db.execute(
                select(RunCostEntry).where(
                    and_(
                        RunCostEntry.tenant_id == self.ctx.tenant_id,
                        RunCostEntry.workspace_id == self.ctx.workspace_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    async def build_dashboard(self) -> WorkspaceObservabilityDashboard:
        runs = self._scoped_runs()
        steps = self._scoped_steps()
        costs = self._scoped_costs()
        approvals = self.approval_repo.list(limit=500, offset=0)
        feedback = self.feedback_repo.list(limit=500, offset=0)

        agent_summary_map: dict[str, dict[str, int | str | None]] = defaultdict(
            lambda: {"run_count": 0, "failed_run_count": 0, "last_run_at": None}
        )
        for run in runs:
            if run.subject_kind != "agent" or not run.subject_id:
                continue
            summary = agent_summary_map[run.subject_id]
            summary["run_count"] = int(summary["run_count"]) + 1
            if run.status == "failed":
                summary["failed_run_count"] = int(summary["failed_run_count"]) + 1
            started_at = run.started_at.isoformat() if run.started_at else None
            if started_at and (summary["last_run_at"] is None or started_at > str(summary["last_run_at"])):
                summary["last_run_at"] = started_at

        model_cost_map: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"total_cost_usd": 0.0, "total_tokens": 0}
        )
        tool_health_map: dict[str, dict[str, int]] = defaultdict(
            lambda: {"call_count": 0, "failed_call_count": 0}
        )
        for cost in costs:
            if cost.model_ref:
                bucket = model_cost_map[cost.model_ref]
                bucket["total_cost_usd"] = float(bucket["total_cost_usd"]) + float(cost.amount)
                bucket["total_tokens"] = int(bucket["total_tokens"]) + int(cost.total_tokens or 0)
            if cost.tool_ref:
                tool_health_map[cost.tool_ref]["call_count"] += 1

        run_by_id = {run.id: run for run in runs}
        workflow_map: dict[str, dict[str, int]] = defaultdict(
            lambda: {"step_count": 0, "failed_step_count": 0}
        )
        knowledge_map: dict[str, int] = defaultdict(int)
        for step in steps:
            if step.node_id:
                workflow_map[step.node_id]["step_count"] += 1
                if step.status == "failed":
                    workflow_map[step.node_id]["failed_step_count"] += 1
            if step.step_type == "tool":
                tool_ref = step.step_id or "tool"
                tool_health_map[tool_ref]["call_count"] += 1
                if step.status == "failed":
                    tool_health_map[tool_ref]["failed_call_count"] += 1
            if step.step_type in {"retrieval", "rerank"}:
                knowledge_map[step.step_type] += 1
            elif step.status == "failed" and (run := run_by_id.get(step.run_id)) and run.subject_kind == "knowledge":
                knowledge_map["knowledge_runs"] += 1

        approvals_summary = ApprovalsSummaryResponse(
            pending=sum(1 for item in approvals if item.status == ApprovalStatus.PENDING.value),
            approved=sum(1 for item in approvals if item.status == ApprovalStatus.APPROVED.value),
            rejected=sum(1 for item in approvals if item.status == ApprovalStatus.REJECTED.value),
        )

        return WorkspaceObservabilityDashboard(
            workspace_summary=WorkspaceSummaryResponse(
                run_count=len(runs),
                failed_run_count=sum(1 for run in runs if run.status == "failed"),
                active_run_count=sum(1 for run in runs if run.status in {"queued", "running", "paused"}),
                pending_approvals=approvals_summary.pending,
                feedback_count=len(feedback),
                total_cost_usd=sum(float(cost.amount) for cost in costs),
            ),
            agent_summaries=[
                AgentSummaryResponse(agent_id=agent_id, **summary)
                for agent_id, summary in sorted(agent_summary_map.items())
            ],
            model_costs=[
                ModelCostResponse(model_ref=model_ref, **summary)
                for model_ref, summary in sorted(model_cost_map.items())
            ],
            workflow_bottlenecks=[
                WorkflowBottleneckResponse(node_id=node_id, **summary)
                for node_id, summary in sorted(workflow_map.items())
            ],
            tool_health=[
                ToolHealthResponse(tool_ref=tool_ref, **summary)
                for tool_ref, summary in sorted(tool_health_map.items())
            ],
            knowledge_quality=[
                KnowledgeQualityResponse(step_type=step_type, event_count=count)
                for step_type, count in sorted(knowledge_map.items())
            ],
            approvals_summary=approvals_summary,
        )
