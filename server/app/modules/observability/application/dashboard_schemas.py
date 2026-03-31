"""Schemas for the observability workspace dashboard."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkspaceSummaryResponse(BaseModel):
    run_count: int = 0
    failed_run_count: int = 0
    active_run_count: int = 0
    pending_approvals: int = 0
    feedback_count: int = 0
    total_cost_usd: float = 0.0


class AgentSummaryResponse(BaseModel):
    agent_id: str
    run_count: int = 0
    failed_run_count: int = 0
    last_run_at: str | None = None


class ModelCostResponse(BaseModel):
    model_ref: str
    total_cost_usd: float = 0.0
    total_tokens: int = 0


class WorkflowBottleneckResponse(BaseModel):
    node_id: str
    step_count: int = 0
    failed_step_count: int = 0


class ToolHealthResponse(BaseModel):
    tool_ref: str
    call_count: int = 0
    failed_call_count: int = 0


class KnowledgeQualityResponse(BaseModel):
    step_type: str
    event_count: int = 0


class ApprovalsSummaryResponse(BaseModel):
    pending: int = 0
    approved: int = 0
    rejected: int = 0


class WorkspaceObservabilityDashboard(BaseModel):
    workspace_summary: WorkspaceSummaryResponse
    agent_summaries: list[AgentSummaryResponse] = Field(default_factory=list)
    model_costs: list[ModelCostResponse] = Field(default_factory=list)
    workflow_bottlenecks: list[WorkflowBottleneckResponse] = Field(default_factory=list)
    tool_health: list[ToolHealthResponse] = Field(default_factory=list)
    knowledge_quality: list[KnowledgeQualityResponse] = Field(default_factory=list)
    approvals_summary: ApprovalsSummaryResponse
