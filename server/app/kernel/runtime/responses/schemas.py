"""Schemas for the Responses API resource and projection layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResponseCreateRequest(BaseModel):
    """Request payload for a northbound response resource."""

    model: str | None = None
    provider: str | None = None
    thread_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    input: Any = Field(default_factory=dict)
    instructions: str | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    mcp_servers: list[dict[str, Any]] = Field(default_factory=list)
    response_format: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    store: bool = True
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResponseRead(BaseModel):
    """Serialized response resource projection."""

    id: str
    tenant_id: str
    workspace_id: str
    thread_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    run_id: str | None = None
    request_id: str | None = None
    model: str | None = None
    provider: str | None = None
    status: str
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    usage_json: dict[str, Any]
    metadata_json: dict[str, Any]
    error_code: str | None = None
    error_message: str | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    canceled_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ResponseEventRead(BaseModel):
    """Serialized response semantic event projection."""

    id: str
    tenant_id: str
    workspace_id: str
    response_id: str
    run_id: str | None = None
    thread_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
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
    run_id: str | None = None
    step_id: str | None = None
    thread_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    tool_name: str
    tool_type: str
    status: str
    arguments_json: dict[str, Any]
    result_json: dict[str, Any]
    metadata_json: dict[str, Any]
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
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
