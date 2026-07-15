"""Workflow domain models.

These models define the dedicated workflow aggregate and version tables
used by the Agent-centered architecture.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_workflow_id() -> str:
    return f"wf_{generate_ulid()}"


def generate_workflow_version_id() -> str:
    return f"wfv_{generate_ulid()}"


def generate_workflow_publish_id() -> str:
    return f"wfp_{generate_ulid()}"


def generate_workflow_run_id() -> str:
    return f"wfr_{generate_ulid()}"


class Workflow(SQLModel, table=True):
    """Workflow aggregate root."""

    __tablename__ = "workflows"
    __table_args__ = (
        Index("ix_workflows_tenant_workspace_status", "tenant_id", "workspace_id", "status"),
        Index("ix_workflows_tenant_workspace_name", "tenant_id", "workspace_id", "name"),
        Index("ix_workflows_tenant_workspace_category", "tenant_id", "workspace_id", "category"),
        Index("ix_workflows_tenant_workspace_owner", "tenant_id", "workspace_id", "owner_user_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_workflow_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    name: str = Field(index=True)
    description: str | None = Field(default=None, nullable=True)
    summary: str | None = Field(default=None, nullable=True)
    status: str = Field(default="active", index=True)
    visibility: str = Field(default="private", index=True)
    icon_url: str | None = Field(default=None, nullable=True)
    category: str | None = Field(default=None, nullable=True)
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON))
    owner_user_id: str | None = Field(default=None, nullable=True)
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    current_version_id: str | None = Field(default=None, nullable=True, index=True)
    published_version_id: str | None = Field(default=None, nullable=True, index=True)
    created_by: str | None = Field(default=None, nullable=True)
    updated_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: datetime | None = Field(default=None, nullable=True)


class WorkflowVersion(SQLModel, table=True):
    """Immutable workflow graph snapshot."""

    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_workflow_versions_workflow_id_version"),
        Index("ix_workflow_versions_workflow_id_status", "workflow_id", "status"),
    )

    id: str = Field(primary_key=True, default_factory=generate_workflow_version_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    workflow_id: str = Field(index=True)
    version: int = Field()
    status: str = Field(default="draft", index=True)
    spec_schema: str = Field(default="workflow.v1")
    spec_json: dict[str, Any] = Field(sa_column=Column(JSON))
    created_from_version_id: str | None = Field(default=None, nullable=True)
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class WorkflowPublish(SQLModel, table=True):
    """Workflow publish ledger."""

    __tablename__ = "workflow_publishes"
    __table_args__ = (
        Index("ix_workflow_publishes_workflow_id", "workflow_id"),
        Index("ix_workflow_publishes_version_id", "workflow_version_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_workflow_publish_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    workflow_id: str = Field()
    workflow_version_id: str = Field()
    action: str = Field(default="publish")
    scope: str = Field(default="workspace")
    status: str = Field(default="published")
    from_version_id: str | None = Field(default=None, nullable=True)
    to_version_id: str | None = Field(default=None, nullable=True)
    notes: str | None = Field(default=None, nullable=True)
    rollback_of_publish_id: str | None = Field(default=None, nullable=True)
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class WorkflowRun(SQLModel, table=True):
    """In-flight workflow execution aggregate (monitoring counters, B5)."""

    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_scope_updated", "tenant_id", "workspace_id", "updated_at"),
        Index("ix_workflow_runs_run_id", "run_id"),
        Index("ix_workflow_runs_workflow_id", "workflow_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_workflow_run_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    run_id: str = Field()
    workflow_id: str = Field()
    status: str = Field(default="running", index=True)
    total_nodes: int = Field(default=0)
    completed_nodes: int = Field(default=0)
    failed_nodes: int = Field(default=0)
    waiting_nodes: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
