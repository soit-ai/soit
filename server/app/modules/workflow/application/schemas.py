""" schemas

Workflow domain schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkflowCreate(BaseModel):
    """Schema for creating a workflow."""

    name: str = Field(..., min_length=1, max_length=255)
    """Workflow name."""

    description: str | None = Field(None, max_length=1000)
    """Workflow description."""

    summary: str | None = Field(None, max_length=1000)
    """Workflow summary for listings."""

    visibility: str = Field(default="private", pattern="^(private|workspace|tenant|public)$")
    """Workflow visibility."""

    icon_url: str | None = Field(None, max_length=2000)
    """Workflow icon URL."""

    category: str | None = Field(None, max_length=128)
    """Workflow category."""

    tags: list[str] | None = None
    """Workflow tags."""


class WorkflowTemplateCreate(BaseModel):
    """Schema for creating a workflow from a template."""

    name: str = Field(default="Ticket triage", min_length=1, max_length=255)
    """Workflow name."""


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow."""

    name: str | None = Field(None, min_length=1, max_length=255)
    """Workflow name."""

    description: str | None = Field(None, max_length=1000)
    """Workflow description."""

    summary: str | None = Field(None, max_length=1000)
    """Workflow summary for listings."""

    status: str | None = Field(None, pattern="^(active|archived|disabled)$")
    """Workflow status."""

    visibility: str | None = Field(None, pattern="^(private|workspace|tenant|public)$")
    """Workflow visibility."""

    icon_url: str | None = Field(None, max_length=2000)
    """Workflow icon URL."""

    category: str | None = Field(None, max_length=128)
    """Workflow category."""

    tags: list[str] | None = None
    """Workflow tags."""

    metadata_json: dict[str, Any] | None = None
    """Workflow metadata."""


class WorkflowVersionCreate(BaseModel):
    """Schema for creating a workflow version."""

    graph_json: dict[str, Any] = Field(...)
    """WorkflowSpec JSON."""

    created_by: str = Field(...)
    """User ID who creates this version."""

    preflight: bool = Field(default=False)
    """Whether to run preflight checks before publish."""


class WorkflowResponse(BaseModel):
    """Schema for workflow response."""

    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: str | None
    summary: str | None
    status: str
    visibility: str
    icon_url: str | None
    category: str | None
    tags: list[str] | None
    owner_user_id: str | None
    current_version_id: str | None
    published_version_id: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkflowVersionResponse(BaseModel):
    """Schema for workflow version response."""

    id: str
    tenant_id: str
    workspace_id: str
    workflow_id: str
    graph_json: dict[str, Any]
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowReleaseResponse(BaseModel):
    """Schema for workflow release history response."""

    id: str
    workflow_id: str
    version_id: str
    action: str
    scope: str
    status: str
    from_version_id: str | None
    to_version_id: str
    notes: str | None
    rollback_of_publish_id: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowWorkbenchSummary(BaseModel):
    """Workflow workbench aggregate metrics."""

    total_workflows: int
    published_workflows: int
    running_workflows: int
    today_runs: int
    avg_latency_ms: int | None
    success_rate: float | None
    recent_exceptions: int
    updated_at: datetime


class WorkflowWorkbenchTabs(BaseModel):
    """Counts for Workflow workbench filter tabs."""

    all: int
    high_volume: int
    publishing: int
    abnormal: int
    draft: int


class WorkflowWorkbenchRow(BaseModel):
    """Workflow row with runtime health for the workbench."""

    id: str
    name: str
    description: str | None
    summary: str | None
    status: str
    linked_agents: list[str] = Field(default_factory=list)
    linked_agent_count: int = 0
    today_runs: int
    avg_latency_ms: int | None
    success_rate: float | None
    recent_exception_count: int
    owner: str | None
    last_run_at: datetime | None
    action_enabled: bool
    updated_at: datetime


class WorkflowWorkbenchResponse(BaseModel):
    """Full Workflow workbench response."""

    summary: WorkflowWorkbenchSummary
    tabs: WorkflowWorkbenchTabs
    items: list[WorkflowWorkbenchRow]
    next_page_token: str | None = None
    page_size: int


class WorkflowWorkbenchItemsResponse(BaseModel):
    """Paginated Workflow workbench table rows."""

    items: list[WorkflowWorkbenchRow]
    next_page_token: str | None = None
    page_size: int


class WorkflowDSLImport(BaseModel):
    """Schema for importing workflow DSL."""

    dsl: dict[str, Any] | str = Field(...)
    """Workflow DSL payload."""

    created_by: str = Field(...)
    """User ID who creates this version."""

    format: str = Field(default="json", pattern="^(json|yaml)$")
    """DSL format."""


class WorkflowPublishRequest(BaseModel):
    """Schema for publishing a workflow version."""

    version_id: str
    """Version ID to publish."""

    preflight: bool = Field(default=False)
    """Whether to run preflight checks before publish."""

    notes: str | None = Field(default=None, max_length=2000)
    """Optional publish notes."""


class WorkflowRollbackRequest(BaseModel):
    """Schema for rolling back a workflow version."""

    version_id: str
    """Target version ID."""

    preflight: bool = Field(default=False)
    """Whether to run preflight checks before rollback."""

    notes: str | None = Field(default=None, max_length=2000)
    """Optional rollback notes."""


class WorkflowDSLExport(BaseModel):
    """Schema for exporting workflow DSL."""

    dsl: dict[str, Any] | str
    """Workflow DSL payload."""

    format: str = Field(default="json", pattern="^(json|yaml)$")
    """DSL format."""
