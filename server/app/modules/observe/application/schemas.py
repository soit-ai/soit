"""Observe governance schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.kernel.runtime.runs.schemas import (
    RunArtifactResponse,
    RunCostEntryResponse,
    RunResponse,
    RunStepResponse,
)


class ApprovalCreate(BaseModel):
    run_id: str | None = None
    task_id: str | None = None
    thread_id: str | None = None
    agent_id: str | None = None
    title: str = Field(..., min_length=1, max_length=255)
    policy_ref: str | None = None
    details_json: dict[str, Any] = Field(default_factory=dict)
    assignee_user_ids: list[str] = Field(default_factory=list, max_length=50)
    """Members or service principals who may decide; with no roles either, any writer may."""
    assignee_roles: list[str] = Field(default_factory=list, max_length=3)
    """Workspace roles whose holders may decide: Owner, Admin or Dev."""
    expires_at: datetime | None = None
    """When the request closes as expired if nobody decided it; counts as a rejection."""


class ApprovalResolve(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|canceled)$")
    resolution_note: str | None = Field(default=None, max_length=1000)


class ApprovalDelegate(BaseModel):
    """Hand a request to one member, who becomes its only approver."""

    user_id: str = Field(..., min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=1000)


class ApprovalDecisionResponse(BaseModel):
    id: str
    approval_id: str
    action: str
    actor_id: str | None
    actor_role: str | None
    note: str | None
    assignees_before_json: dict[str, Any]
    assignees_after_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("assignees_before_json", "assignees_after_json", mode="before")
    @classmethod
    def _empty_dict(cls, value: Any) -> Any:
        return value or {}


class ApprovalResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    run_id: str | None
    task_id: str | None
    thread_id: str | None
    agent_id: str | None
    title: str
    policy_ref: str | None
    status: str
    details_json: dict[str, Any]
    assignee_user_ids: list[str] = Field(default_factory=list)
    assignee_roles: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    requested_by: str | None
    resolved_by: str | None
    resolution_note: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("assignee_user_ids", "assignee_roles", mode="before")
    @classmethod
    def _empty_list(cls, value: Any) -> Any:
        # Requests written before assignment existed hold no list at all.
        return value or []


class FeedbackCreate(BaseModel):
    run_id: str | None = None
    task_id: str | None = None
    thread_id: str | None = None
    agent_id: str | None = None
    rating: int = Field(..., ge=1, le=5)
    category: str = Field(default="general", min_length=1, max_length=64)
    comment: str | None = Field(default=None, max_length=2000)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class FeedbackResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    run_id: str | None
    task_id: str | None
    thread_id: str | None
    agent_id: str | None
    rating: int
    category: str
    comment: str | None
    metadata_json: dict[str, Any]
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunReplayResponse(BaseModel):
    run: RunResponse
    steps: list[RunStepResponse]
    artifacts: list[RunArtifactResponse]
    costs: list[RunCostEntryResponse]
    approvals: list[ApprovalResponse]
    feedback: list[FeedbackResponse]
    trace_spec: dict[str, Any]
