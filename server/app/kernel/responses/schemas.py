"""Schemas for the Responses API resource and projection layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ResponseCreateRequest(BaseModel):
    """Request payload for a northbound response resource."""

    model: Optional[str] = None
    provider: Optional[str] = None
    thread_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    input: Any = Field(default_factory=dict)
    instructions: Optional[str] = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    mcp_servers: list[dict[str, Any]] = Field(default_factory=list)
    response_format: Optional[dict[str, Any]] = None
    context: Optional[dict[str, Any]] = None
    store: bool = True
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResponseRead(BaseModel):
    """Serialized response resource projection."""

    id: str
    tenant_id: str
    workspace_id: str
    thread_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    status: str
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    usage_json: dict[str, Any]
    metadata_json: dict[str, Any]
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ResponseEventRead(BaseModel):
    """Serialized response semantic event projection."""

    id: str
    tenant_id: str
    workspace_id: str
    response_id: str
    run_id: Optional[str] = None
    thread_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    sequence: int
    type: str
    source: str
    payload_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ToolCallRead(BaseModel):
    """Serialized tool-call projection derived from run steps."""

    id: str
    tenant_id: str
    workspace_id: str
    response_id: str
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    thread_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    tool_name: str
    tool_type: str
    status: str
    arguments_json: dict[str, Any]
    result_json: dict[str, Any]
    metadata_json: dict[str, Any]
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResponseCancelResult(BaseModel):
    """Result of a cancellation request."""

    response: ResponseRead
    action: str


class ResponseDetailRead(BaseModel):
    """Response detail with semantic event and tool-call projections."""

    response: ResponseRead
    events: list[ResponseEventRead]
    tool_calls: list[ToolCallRead]


class ResponseTimelineItemRead(BaseModel):
    """Response projection item grouped for a run-scoped semantic timeline."""

    response: ResponseRead
    events: list[ResponseEventRead]
    tool_calls: list[ToolCallRead]


class RunResponseTimelineRead(BaseModel):
    """Semantic response timeline projected for a single run."""

    run_id: str
    items: list[ResponseTimelineItemRead]
