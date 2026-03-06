""" models

Trace model DTOs (run/step/cost/artifact).
"""

from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import Text, Numeric, Index

from app.kernel.commons.time import utc_now
from app.kernel.commons.ids import generate_ulid


class Run(SQLModel, table=True):
    """Run model - represents a single execution (chat/agent/workflow)."""
    
    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_scope_app_started", "tenant_id", "workspace_id", "app_id", "started_at"),
    )
    
    id: str = Field(primary_key=True)
    """Run ID (e.g., "run_01H...")."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""

    user_id: Optional[str] = Field(default=None, index=True)
    """User ID that initiated the run."""

    trace_id: Optional[str] = Field(default=None, index=True)
    """Trace ID for request correlation."""
    
    mode: str = Field()
    """Execution mode (domain-specific): chat, bot, workflow, agent, dataset_*."""

    kind: Optional[str] = Field(default=None, index=True)
    """Stable execution kind: chat, workflow, agent, tool, batch."""

    app_id: str = Field(foreign_key="apps.id", index=True)
    """App ID (foreign key)."""

    app_version_id: str = Field(foreign_key="app_versions.id", index=True)
    """App version ID (foreign key)."""

    app_type: Optional[str] = Field(default=None, index=True)
    """App type (workflow/chat/bot/agent)."""
    
    status: str = Field()
    """Status: queued, running, paused, succeeded, failed, canceled."""
    
    input_summary: Optional[str] = Field(default=None, max_length=8192, sa_column=Column(Text))
    """Input summary (bounded to 8KB)."""
    
    output_summary: Optional[str] = Field(default=None, max_length=8192, sa_column=Column(Text))
    """Output summary (bounded to 8KB)."""
    
    started_at: datetime = Field(default_factory=utc_now)
    """Start timestamp."""
    
    ended_at: Optional[datetime] = Field(default=None, nullable=True)
    """End timestamp (null if still running)."""

    duration_ms: Optional[int] = Field(default=None, nullable=True)
    """Duration in milliseconds (computed when ended)."""

    error_code: Optional[str] = Field(default=None, nullable=True)
    """Error code if failed."""

    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error message if failed."""

    error_step_id: Optional[str] = Field(default=None, nullable=True)
    """Failed step ID if available."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class RunStep(SQLModel, table=True):
    """RunStep model - represents a single step in a run."""
    
    __tablename__ = "run_steps"
    
    id: str = Field(primary_key=True)
    """Step ID (e.g., "st_01H...")."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""

    trace_id: Optional[str] = Field(default=None, index=True)
    """Trace ID for request correlation."""
    
    run_id: str = Field(foreign_key="runs.id", index=True)
    """Run ID (foreign key)."""
    
    step_id: Optional[str] = Field(default=None, nullable=True)
    """Step ID (e.g., "st_node1" for workflow nodes)."""
    
    step_type: str = Field()
    """Step type: llm, retrieval, rerank, tool, workflow_node, agent_plan, memory_write, io, other."""
    
    node_id: Optional[str] = Field(default=None, nullable=True)
    """Optional node ID (for workflow nodes)."""
    
    status: str = Field()
    """Status: queued, running, succeeded, failed, skipped, canceled."""
    
    input_summary: Optional[str] = Field(default=None, max_length=8192, sa_column=Column(Text))
    """Input summary (bounded to 8KB)."""
    
    output_summary: Optional[str] = Field(default=None, max_length=8192, sa_column=Column(Text))
    """Output summary (bounded to 8KB)."""
    
    metrics_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Metrics (tokens, latency, http_status, vector_count, etc.)."""
    
    error_code: Optional[str] = Field(default=None, nullable=True)
    """Error code if failed."""
    
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error message if failed."""
    
    error_details: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Error details if failed."""
    
    started_at: datetime = Field(default_factory=utc_now)
    """Start timestamp."""
    
    ended_at: Optional[datetime] = Field(default=None, nullable=True)
    """End timestamp (null if still running)."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""


class RunArtifact(SQLModel, table=True):
    """RunArtifact model - represents an artifact produced by a run."""
    
    __tablename__ = "run_artifacts"
    
    id: str = Field(primary_key=True)
    """Artifact ID (e.g., "art_01H...")."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    run_id: str = Field(foreign_key="runs.id", index=True)
    """Run ID (foreign key)."""

    step_id: Optional[str] = Field(default=None, index=True)
    """Optional step ID (if artifact is tied to a step)."""
    
    type: str = Field()
    """Artifact kind: file, log, blob, json."""

    mime: Optional[str] = Field(default=None, nullable=True)
    """MIME type."""

    size_bytes: Optional[int] = Field(default=None, nullable=True)
    """Artifact size in bytes."""

    sha256: Optional[str] = Field(default=None, nullable=True)
    """SHA256 checksum."""
    
    storage_key: str = Field()
    """Storage key (object storage path)."""
    
    meta_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Metadata (mime, size, hash, etc.)."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""


class RunCostEntry(SQLModel, table=True):
    """Normalized cost record for metered usage."""

    __tablename__ = "run_cost_entries"

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    """Cost entry ID."""

    run_id: str = Field(foreign_key="runs.id", index=True)
    """Run ID (foreign key)."""

    step_id: Optional[str] = Field(default=None, index=True)
    """Optional step ID (foreign key)."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    currency: str = Field(default="USD")
    """Currency code (e.g., USD)."""

    amount: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(18, 6)))
    """Cost amount."""

    unit: str = Field()
    """Unit (tokens/requests/seconds/bytes)."""

    quantity: Decimal = Field(sa_column=Column(Numeric(18, 6)))
    """Quantity in unit."""

    provider: Optional[str] = Field(default=None)
    """Provider (e.g., openai, http)."""

    model_ref: Optional[str] = Field(default=None)
    """Model reference if applicable."""

    tool_ref: Optional[str] = Field(default=None)
    """Tool reference if applicable."""

    prompt_tokens: Optional[int] = Field(default=None, nullable=True)
    """Prompt tokens for LLM usage."""

    completion_tokens: Optional[int] = Field(default=None, nullable=True)
    """Completion tokens for LLM usage."""

    total_tokens: Optional[int] = Field(default=None, nullable=True)
    """Total tokens for LLM usage."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
