"""Observe governance domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_approval_id() -> str:
    return f"apr_{generate_ulid()}"


def generate_feedback_id() -> str:
    return f"fbk_{generate_ulid()}"


def generate_approval_decision_id() -> str:
    return f"apd_{generate_ulid()}"


class ApprovalRequest(SQLModel, table=True):
    """Approval request emitted by runtime governance hooks."""

    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_scope_status", "tenant_id", "workspace_id", "status"),
        Index("ix_approval_requests_run_task", "run_id", "task_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_approval_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    run_id: str | None = Field(default=None, nullable=True)
    task_id: str | None = Field(default=None, nullable=True)
    thread_id: str | None = Field(default=None, nullable=True)
    agent_id: str | None = Field(default=None, nullable=True)
    title: str = Field()
    policy_ref: str | None = Field(default=None, nullable=True)
    status: str = Field(default="pending", index=True)
    details_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    assignee_user_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Members or service principals who may decide. Empty with no roles: any writer."""
    assignee_roles: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Workspace roles whose holders may decide, read at decision time."""
    expires_at: datetime | None = Field(default=None, nullable=True, index=True)
    """When a request nobody decided closes as ``expired``, which counts as a rejection."""
    requested_by: str | None = Field(default=None, nullable=True)
    resolved_by: str | None = Field(default=None, nullable=True)
    resolution_note: str | None = Field(default=None, nullable=True)
    resolved_at: datetime | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ApprovalDecision(SQLModel, table=True):
    """One entry of an approval request's history: a decision, a closing or a delegation.

    Entries are only ever added. Together they say who could decide when, who
    did, and through which delegations the request reached them.
    """

    __tablename__ = "approval_decisions"
    __table_args__ = (Index("ix_approval_decisions_approval", "approval_id", "created_at"),)

    id: str = Field(primary_key=True, default_factory=generate_approval_decision_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    approval_id: str = Field()
    action: str = Field()
    """``approved``, ``rejected``, ``canceled``, ``expired`` or ``delegated``."""
    actor_id: str | None = Field(default=None, nullable=True)
    actor_role: str | None = Field(default=None, nullable=True)
    """The actor's workspace role when they acted; ``system`` for closings nobody took."""
    note: str | None = Field(default=None, nullable=True)
    assignees_before_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    assignees_after_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class RunFeedback(SQLModel, table=True):
    """Structured user/operator feedback for runs and threads."""

    __tablename__ = "run_feedbacks"
    __table_args__ = (
        Index("ix_run_feedbacks_scope_created", "tenant_id", "workspace_id", "created_at"),
        Index("ix_run_feedbacks_run_agent", "run_id", "agent_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_feedback_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    run_id: str | None = Field(default=None, nullable=True)
    task_id: str | None = Field(default=None, nullable=True)
    thread_id: str | None = Field(default=None, nullable=True)
    agent_id: str | None = Field(default=None, nullable=True)
    rating: int = Field(default=0)
    category: str = Field(default="general", index=True)
    comment: str | None = Field(default=None, nullable=True)
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
