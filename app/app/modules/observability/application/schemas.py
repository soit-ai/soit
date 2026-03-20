"""Observability governance schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.kernel.trace.schemas import (
    RunArtifactResponse,
    RunCostEntryResponse,
    RunResponse,
    RunStepResponse,
)


class ApprovalCreate(BaseModel):
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    thread_id: Optional[str] = None
    agent_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=255)
    policy_ref: Optional[str] = None
    details_json: dict[str, Any] = Field(default_factory=dict)


class ApprovalResolve(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|canceled)$")
    resolution_note: Optional[str] = Field(default=None, max_length=1000)


class ApprovalResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    run_id: Optional[str]
    task_id: Optional[str]
    thread_id: Optional[str]
    agent_id: Optional[str]
    title: str
    policy_ref: Optional[str]
    status: str
    details_json: dict[str, Any]
    requested_by: Optional[str]
    resolved_by: Optional[str]
    resolution_note: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackCreate(BaseModel):
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    thread_id: Optional[str] = None
    agent_id: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    category: str = Field(default="general", min_length=1, max_length=64)
    comment: Optional[str] = Field(default=None, max_length=2000)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class FeedbackResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    run_id: Optional[str]
    task_id: Optional[str]
    thread_id: Optional[str]
    agent_id: Optional[str]
    rating: int
    category: str
    comment: Optional[str]
    metadata_json: dict[str, Any]
    created_by: Optional[str]
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
