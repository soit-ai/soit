"""Schemas for the observe workspace dashboard."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


DashboardTabId = Literal[
    "agent_health",
    "workflow_bottlenecks",
    "tool_reliability",
    "knowledge_quality",
]


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
    failure_rate: float = 0.0
    health_status: str = "unknown"


class KnowledgeQualityResponse(BaseModel):
    knowledge_id: str
    query_count: int = 0
    failed_query_count: int = 0
    result_count: int = 0
    citation_count: int = 0
    avg_score: float | None = None
    failure_rate: float = 0.0
    avg_results_per_query: float = 0.0
    citation_rate: float = 0.0
    quality_status: str = "unknown"


class ApprovalsSummaryResponse(BaseModel):
    pending: int = 0
    approved: int = 0
    rejected: int = 0


class DashboardOverviewResponse(BaseModel):
    workspace_health_score: float = 100.0
    workspace_health_status: str = "healthy"
    active_alert_count: int = 0
    sampling_rate: float = 0.0
    sampling_status: str = "no_data"
    refreshed_at: str


class MetricCardResponse(BaseModel):
    id: str
    label: str
    value: str
    delta: str | None = None
    trend: list[float] = Field(default_factory=list)
    tone: str = "blue"


class PriorityAlertResponse(BaseModel):
    priority: str = "P1"
    title: str
    started_at: str | None = None
    scope: str
    affected_agents: int = 0
    duration_label: str
    detail_url: str = "/observe/runs"


class DashboardTabResponse(BaseModel):
    id: DashboardTabId
    label: str
    count: int = 0


class DashboardPageResponse(BaseModel):
    page_size: int = 0
    next_page_token: str | None = None
    total_count: int = 0


class EmptyStateResponse(BaseModel):
    title: str
    description: str


class DashboardSectionResponse(BaseModel):
    id: DashboardTabId
    summary_cards: list[MetricCardResponse] = Field(default_factory=list)
    charts: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    page: DashboardPageResponse
    empty_state: EmptyStateResponse


class WorkspaceObserveDashboard(BaseModel):
    overview: DashboardOverviewResponse
    metric_cards: list[MetricCardResponse] = Field(default_factory=list)
    priority_alert: PriorityAlertResponse | None = None
    tabs: list[DashboardTabResponse] = Field(default_factory=list)
    section: DashboardSectionResponse

    workspace_summary: WorkspaceSummaryResponse
    agent_summaries: list[AgentSummaryResponse] = Field(default_factory=list)
    model_costs: list[ModelCostResponse] = Field(default_factory=list)
    workflow_bottlenecks: list[WorkflowBottleneckResponse] = Field(default_factory=list)
    tool_health: list[ToolHealthResponse] = Field(default_factory=list)
    knowledge_quality: list[KnowledgeQualityResponse] = Field(default_factory=list)
    approvals_summary: ApprovalsSummaryResponse
