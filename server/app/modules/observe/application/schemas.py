"""Observe governance schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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


class ApprovalResolve(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|canceled)$")
    resolution_note: str | None = Field(default=None, max_length=1000)


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
    requested_by: str | None
    resolved_by: str | None
    resolution_note: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
