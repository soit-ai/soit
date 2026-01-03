""" models

Trace model DTOs (run/step/cost/artifact).
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import Text

from app.kernel.commons.time import utc_now


class Run(SQLModel, table=True):
    """Run model - represents a single execution (chat/agent/workflow)."""
    
    __tablename__ = "runs"
    
    id: str = Field(primary_key=True)
    """Run ID (e.g., "run_01H...")."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    mode: str = Field()
    """Execution mode: chat, bot, workflow, agent."""
    
    app_version_id: Optional[str] = Field(default=None, nullable=True)
    """Optional app version ID."""
    
    status: str = Field()
    """Status: queued, running, succeeded, failed, canceled."""
    
    input_summary: Optional[str] = Field(default=None, max_length=8192, sa_column=Column(Text))
    """Input summary (bounded to 8KB)."""
    
    output_summary: Optional[str] = Field(default=None, max_length=8192, sa_column=Column(Text))
    """Output summary (bounded to 8KB)."""
    
    started_at: datetime = Field(default_factory=utc_now)
    """Start timestamp."""
    
    ended_at: Optional[datetime] = Field(default=None, nullable=True)
    """End timestamp (null if still running)."""
    
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
    
    run_id: str = Field(foreign_key="runs.id", index=True)
    """Run ID (foreign key)."""
    
    step_id: Optional[str] = Field(default=None, nullable=True)
    """Step ID (e.g., "st_node1" for workflow nodes)."""
    
    step_type: str = Field()
    """Step type: llm, retrieve, rerank, tool, node, plan."""
    
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
    
    error_message: Optional[str] = Field(default=None, nullable=True, sa_column=Column(Text))
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
    
    type: str = Field()
    """Artifact type: file, log, blob, json."""
    
    storage_key: str = Field()
    """Storage key (object storage path)."""
    
    meta_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Metadata (mime, size, hash, etc.)."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""


class RunCost(SQLModel, table=True):
    """RunCost model - represents cost tracking for a run."""
    
    __tablename__ = "run_costs"
    
    run_id: str = Field(primary_key=True, foreign_key="runs.id")
    """Run ID (foreign key, unique)."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    tokens_prompt: int = Field(default=0)
    """Prompt tokens used."""
    
    tokens_completion: int = Field(default=0)
    """Completion tokens used."""
    
    embedding_count: int = Field(default=0)
    """Number of embeddings generated."""
    
    rerank_count: int = Field(default=0)
    """Number of rerank operations."""
    
    ms_total: int = Field(default=0)
    """Total execution time in milliseconds."""
    
    storage_bytes: int = Field(default=0)
    """Storage bytes used."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""
