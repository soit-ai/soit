"""Skill domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_skill_id() -> str:
    return f"skl_{generate_ulid()}"


def generate_skill_version_id() -> str:
    return f"sklv_{generate_ulid()}"


def generate_skill_publish_id() -> str:
    return f"sklp_{generate_ulid()}"


class Skill(SQLModel, table=True):
    """Skill aggregate root."""

    __tablename__ = "skills"
    __table_args__ = (
        Index("ix_skills_tenant_workspace_status", "tenant_id", "workspace_id", "status"),
        Index("ix_skills_tenant_workspace_name", "tenant_id", "workspace_id", "name"),
    )

    id: str = Field(primary_key=True, default_factory=generate_skill_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None, nullable=True)
    category: str = Field(default="tool", index=True)
    status: str = Field(default="active", index=True)
    visibility: str = Field(default="private", index=True)
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    current_version_id: Optional[str] = Field(default=None, nullable=True, index=True)
    published_version_id: Optional[str] = Field(default=None, nullable=True, index=True)
    created_by: Optional[str] = Field(default=None, nullable=True)
    updated_by: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)


class SkillVersion(SQLModel, table=True):
    """Immutable skill specification snapshot."""

    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "version", name="uq_skill_versions_skill_id_version"),
        Index("ix_skill_versions_skill_id_status", "skill_id", "status"),
    )

    id: str = Field(primary_key=True, default_factory=generate_skill_version_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    skill_id: str = Field(foreign_key="skills.id", index=True)
    version: int = Field()
    status: str = Field(default="draft", index=True)
    spec_schema: str = Field(default="skill.v1")
    spec_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_by: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)


class SkillPublish(SQLModel, table=True):
    """Skill publish ledger."""

    __tablename__ = "skill_publishes"
    __table_args__ = (
        Index("ix_skill_publishes_skill_id", "skill_id"),
        Index("ix_skill_publishes_version_id", "skill_version_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_skill_publish_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    skill_id: str = Field(foreign_key="skills.id")
    skill_version_id: str = Field(foreign_key="skill_versions.id")
    scope: str = Field(default="workspace")
    status: str = Field(default="published")
    created_by: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
