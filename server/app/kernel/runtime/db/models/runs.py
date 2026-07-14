"""models

Trace model DTOs (run/step/cost/artifact).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Index, Numeric, Text
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


class Run(SQLModel, table=True):
    """Run model - represents a single execution (chat/agent/workflow)."""

    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_scope_subject_started", "tenant_id", "workspace_id", "subject_kind", "subject_id", "started_at"),
    )

    id: str = Field(primary_key=True)
    """Run ID (e.g., "run_01H...")."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    user_id: str | None = Field(default=None, index=True)
    """User ID that initiated the run."""

    trace_id: str | None = Field(default=None, index=True)
    """Trace ID for request correlation."""

    mode: str = Field()
    """Execution mode (domain-specific): chat, workflow, agent, knowledge, memory, etc."""

    kind: str | None = Field(default=None, index=True)
    """Stable execution kind: chat, workflow, agent, tool, batch."""

    subject_kind: str | None = Field(default=None, index=True)
    """Primary execution subject kind (agent/workflow/chat/thread/knowledge/memory/etc.)."""

    subject_id: str | None = Field(default=None, index=True)
    """Primary execution subject ID."""

    subject_version_id: str | None = Field(default=None, index=True)
    """Primary execution subject version ID."""

    status: str = Field()
    """Status: queued, running, paused, succeeded, failed, canceled."""

    input_summary: str | None = Field(default=None, max_length=8192, sa_column=Column(Text))
    """Input summary (bounded to 8KB)."""

    output_summary: str | None = Field(default=None, max_length=8192, sa_column=Column(Text))
    """Output summary (bounded to 8KB)."""

    started_at: datetime = Field(default_factory=utc_now)
    """Start timestamp."""

    ended_at: datetime | None = Field(default=None, nullable=True)
    """End timestamp (null if still running)."""

    duration_ms: int | None = Field(default=None, nullable=True)
    """Duration in milliseconds (computed when ended)."""

    error_code: str | None = Field(default=None, nullable=True)
    """Error code if failed."""

    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error message if failed."""

    error_step_id: str | None = Field(default=None, nullable=True)
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

    trace_id: str | None = Field(default=None, index=True)
    """Trace ID for request correlation."""

    run_id: str = Field(index=True)
    """Run ID (foreign key)."""

    step_id: str | None = Field(default=None, nullable=True)
    """Step ID (e.g., "st_node1" for workflow nodes)."""

    step_type: str = Field()
    """Step type: llm, retrieval, rerank, tool, workflow_node, agent_plan, memory_write, io, other."""

    node_id: str | None = Field(default=None, nullable=True)
    """Optional node ID (for workflow nodes)."""

    status: str = Field()
    """Status: queued, running, succeeded, failed, skipped, canceled."""

    input_summary: str | None = Field(default=None, max_length=8192, sa_column=Column(Text))
    """Input summary (bounded to 8KB)."""

    output_summary: str | None = Field(default=None, max_length=8192, sa_column=Column(Text))
    """Output summary (bounded to 8KB)."""

    metrics_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Metrics (tokens, latency, http_status, vector_count, etc.)."""

    error_code: str | None = Field(default=None, nullable=True)
    """Error code if failed."""

    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error message if failed."""

    error_details: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Error details if failed."""

    started_at: datetime = Field(default_factory=utc_now)
    """Start timestamp."""

    ended_at: datetime | None = Field(default=None, nullable=True)
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

    run_id: str = Field(index=True)
    """Run ID (foreign key)."""

    step_id: str | None = Field(default=None, index=True)
    """Optional step ID (if artifact is tied to a step)."""

    type: str = Field()
    """Artifact kind: file, log, blob, json."""

    mime: str | None = Field(default=None, nullable=True)
    """MIME type."""

    size_bytes: int | None = Field(default=None, nullable=True)
    """Artifact size in bytes."""

    sha256: str | None = Field(default=None, nullable=True)
    """SHA256 checksum."""

    storage_key: str = Field()
    """Storage key (object storage path)."""

    meta_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Metadata (mime, size, hash, etc.)."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""


class RunCostEntry(SQLModel, table=True):
    """Normalized cost record for metered usage."""

    __tablename__ = "run_cost_entries"

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    """Cost entry ID."""

    run_id: str = Field(index=True)
    """Run ID (foreign key)."""

    step_id: str | None = Field(default=None, index=True)
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

    provider: str | None = Field(default=None)
    """Provider (e.g., openai, http)."""

    model_ref: str | None = Field(default=None)
    """Model reference if applicable."""

    tool_ref: str | None = Field(default=None)
    """Tool reference if applicable."""

    prompt_tokens: int | None = Field(default=None, nullable=True)
    """Prompt tokens for LLM usage."""

    completion_tokens: int | None = Field(default=None, nullable=True)
    """Completion tokens for LLM usage."""

    total_tokens: int | None = Field(default=None, nullable=True)
    """Total tokens for LLM usage."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
