"""Schemas for the observe workspace dashboard."""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.kernel.runtime.runs.schemas import RunObserveSummaryResponse

DashboardTabId = Literal[
    "agent_health",
    "workflow_bottlenecks",
    "tool_reliability",
    "knowledge_quality",
]


class AgentSummaryResponse(BaseModel):
    agent_id: str
    run_count: int = 0
    failed_run_count: int = 0
    last_run_at: str | None = None


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


class RecentRunResponse(BaseModel):
    run_id: str
    mode: str | None = None
    kind: str | None = None
    subject_kind: str | None = None
    subject_id: str | None = None
    status: str
    cost_usd: float = 0.0
    failure_reason: str | None = None
    started_at: str | None = None
    duration_ms: int | None = None
    observe_summary: RunObserveSummaryResponse | None = None
    detail_url: str


class MetricCardResponse(BaseModel):
    id: str
    label: str
    value: str
    delta: str | None = None
    trend: list[float] = Field(default_factory=list[float])
    tone: str = "blue"
    run_id: str | None = None
    detail_url: str | None = None
    status: str | None = None
    cost_usd: float | None = None
    failure_reason: str | None = None


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


class DashboardChartModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DashboardTrendPointResponse(DashboardChartModel):
    bucket: str
    run_count: int
    failed_run_count: int
    success_rate: float
    tool_count: int
    tool_failed_count: int
    retrieval_count: int
    retrieval_failed_count: int


class HealthDistributionPointResponse(DashboardChartModel):
    status: str
    count: int


class AlertCompressionResponse(DashboardChartModel):
    raw_alerts: int
    compressed_alerts: int


class ErrorDistributionPointResponse(DashboardChartModel):
    type: str
    count: int


class DashboardChartRunFieldsResponse(DashboardChartModel):
    latest_run_id: str | None = None
    latest_run_status: str | None = None
    latest_run_cost_usd: float = 0.0
    latest_failure_reason: str | None = None
    detail_url: str | None = None


class WorkflowQueuePointResponse(DashboardChartRunFieldsResponse):
    id: str
    name: str
    description: str
    stage: str
    current_queue: int
    avg_wait_ms: int
    failure_rate: float
    affected_agents: list[str] = Field(default_factory=list[str])
    owner: str


class KnowledgeSourcePointResponse(DashboardChartRunFieldsResponse):
    id: str
    name: str
    description: str
    related_agents: list[str] = Field(default_factory=list[str])
    hit_rate: float
    missing_answer_rate: float
    expired_chunks: int
    last_updated: str | None = None
    status: str
    owner: str


class LatencyPercentilesResponse(DashboardChartModel):
    p50: int
    p95: int
    p99: int


class AgentHealthChartsResponse(DashboardChartModel):
    trend: list[DashboardTrendPointResponse]
    health_distribution: list[HealthDistributionPointResponse]
    alert_compression: AlertCompressionResponse


class WorkflowBottlenecksChartsResponse(DashboardChartModel):
    bottleneck_flow: list[WorkflowQueuePointResponse]
    queue_distribution: list[WorkflowQueuePointResponse]
    latency_percentiles: LatencyPercentilesResponse


class ToolReliabilityChartsResponse(DashboardChartModel):
    trend: list[DashboardTrendPointResponse]
    error_distribution: list[ErrorDistributionPointResponse]


class KnowledgeQualityChartsResponse(DashboardChartModel):
    trend: list[DashboardTrendPointResponse]
    quality_score: float
    low_quality_sources: list[KnowledgeSourcePointResponse]


class DashboardSectionBaseResponse(BaseModel):
    summary_cards: list[MetricCardResponse] = Field(default_factory=list[MetricCardResponse])
    rows: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])
    page: DashboardPageResponse
    empty_state: EmptyStateResponse


class AgentHealthDashboardSectionResponse(DashboardSectionBaseResponse):
    id: Literal["agent_health"]
    charts: AgentHealthChartsResponse


class WorkflowBottlenecksDashboardSectionResponse(DashboardSectionBaseResponse):
    id: Literal["workflow_bottlenecks"]
    charts: WorkflowBottlenecksChartsResponse


class ToolReliabilityDashboardSectionResponse(DashboardSectionBaseResponse):
    id: Literal["tool_reliability"]
    charts: ToolReliabilityChartsResponse


class KnowledgeQualityDashboardSectionResponse(DashboardSectionBaseResponse):
    id: Literal["knowledge_quality"]
    charts: KnowledgeQualityChartsResponse


DashboardSectionResponse: TypeAlias = Annotated[
    AgentHealthDashboardSectionResponse
    | WorkflowBottlenecksDashboardSectionResponse
    | ToolReliabilityDashboardSectionResponse
    | KnowledgeQualityDashboardSectionResponse,
    Field(discriminator="id"),
]

_DASHBOARD_SECTION_ADAPTER: TypeAdapter[DashboardSectionResponse] = TypeAdapter(
    DashboardSectionResponse
)


def validate_dashboard_section_response(data: dict[str, Any]) -> DashboardSectionResponse:
    return _DASHBOARD_SECTION_ADAPTER.validate_python(data)


class WorkspaceObserveDashboard(BaseModel):
    overview: DashboardOverviewResponse
    metric_cards: list[MetricCardResponse] = Field(default_factory=list[MetricCardResponse])
    priority_alert: PriorityAlertResponse | None = None
    tabs: list[DashboardTabResponse] = Field(default_factory=list[DashboardTabResponse])
    section: DashboardSectionResponse
    recent_runs: list[RecentRunResponse] = Field(default_factory=list[RecentRunResponse])
