"""Agent domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_agent_id() -> str:
    """Generate an Agent identifier."""

    return f"agt_{generate_ulid()}"


def generate_agent_version_id() -> str:
    """Generate an AgentVersion identifier."""

    return f"agtv_{generate_ulid()}"


def generate_agent_binding_id() -> str:
    """Generate an AgentBinding identifier."""

    return f"agtb_{generate_ulid()}"


def generate_agent_publish_id() -> str:
    """Generate an AgentPublish identifier."""

    return f"agtp_{generate_ulid()}"


class Agent(SQLModel, table=True):
    """Agent aggregate root."""

    __tablename__ = "agents"
    __table_args__ = (
        Index("ix_agents_tenant_workspace_status", "tenant_id", "workspace_id", "status"),
        Index("ix_agents_tenant_workspace_name", "tenant_id", "workspace_id", "name"),
        Index("ix_agents_tenant_workspace_category", "tenant_id", "workspace_id", "category"),
        Index("ix_agents_tenant_workspace_featured", "tenant_id", "workspace_id", "featured"),
    )

    id: str = Field(primary_key=True, default_factory=generate_agent_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    name: str = Field(index=True)
    description: str | None = Field(default=None, nullable=True)
    status: str = Field(default="active", index=True)
    visibility: str = Field(default="private", index=True)
    icon_url: str | None = Field(default=None, nullable=True)
    category: str | None = Field(default=None, nullable=True)
    is_public: bool = Field(default=False)
    featured: bool = Field(default=False)
    downloads_count: int = Field(default=0)
    rating: float | None = Field(default=None, nullable=True)
    reviews_count: int = Field(default=0)
    published_at: datetime | None = Field(default=None, nullable=True)
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON))
    profile_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    instructions_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    execution_policy_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    runtime_config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    default_model_ref: str | None = Field(default=None, nullable=True)
    current_version_id: str | None = Field(default=None, nullable=True, index=True)
    published_version_id: str | None = Field(default=None, nullable=True, index=True)
    created_by: str | None = Field(default=None, nullable=True)
    updated_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: datetime | None = Field(default=None, nullable=True)


class AgentVersion(SQLModel, table=True):
    """Immutable Agent configuration snapshot."""

    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_id_version"),
        Index("ix_agent_versions_agent_id_status", "agent_id", "status"),
        Index("ix_agent_versions_checksum", "checksum"),
    )

    id: str = Field(primary_key=True, default_factory=generate_agent_version_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    agent_id: str = Field(index=True)
    version: int = Field()
    status: str = Field(default="draft", index=True)
    spec_schema: str = Field()
    spec_json: dict[str, Any] = Field(sa_column=Column(JSON))
    checksum: str | None = Field(default=None, nullable=True)
    created_from_version_id: str | None = Field(default=None, nullable=True)
    changelog: str | None = Field(default=None, nullable=True)
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class AgentBinding(SQLModel, table=True):
    """Binding between an Agent(Version) and a capability/resource."""

    __tablename__ = "agent_bindings"
    __table_args__ = (
        UniqueConstraint(
            "agent_version_id",
            "binding_type",
            "target_id",
            "target_key",
            name="uq_agent_bindings_version_target",
        ),
        Index("ix_agent_bindings_agent_id", "agent_id"),
        Index("ix_agent_bindings_agent_version_id", "agent_version_id"),
        Index("ix_agent_bindings_binding_type", "binding_type"),
    )

    id: str = Field(primary_key=True, default_factory=generate_agent_binding_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    agent_id: str = Field()
    agent_version_id: str = Field()
    binding_type: str = Field()
    target_id: str | None = Field(default=None, nullable=True)
    target_key: str | None = Field(default=None, nullable=True)
    config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentPublish(SQLModel, table=True):
    """Agent publish ledger."""

    __tablename__ = "agent_publishes"
    __table_args__ = (
        Index("ix_agent_publishes_agent_id", "agent_id"),
        Index("ix_agent_publishes_version_id", "agent_version_id"),
        Index("ix_agent_publishes_scope_status", "scope", "status"),
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "agent_id",
            "sequence",
            name="uq_agent_publishes_scope_sequence",
        ),
    )

    id: str = Field(primary_key=True, default_factory=generate_agent_publish_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    agent_id: str = Field()
    agent_version_id: str = Field()
    sequence: int = Field(default=0)
    scope: str = Field(default="workspace")
    status: str = Field(default="published")
    notes: str | None = Field(default=None, nullable=True)
    rollback_of_publish_id: str | None = Field(default=None, nullable=True)
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
