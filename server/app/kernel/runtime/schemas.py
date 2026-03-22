"""Runtime task API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class TaskResponse(BaseModel):
    """Serialized runtime task."""

    id: str
    tenant_id: str
    workspace_id: str
    agent_id: Optional[str] = None
    thread_id: Optional[str] = None
    run_id: Optional[str] = None
    task_type: str
    status: str
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    progress_json: dict[str, Any]
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskCheckpointResponse(BaseModel):
    """Serialized task checkpoint."""

    id: str
    tenant_id: str
    workspace_id: str
    task_id: str
    checkpoint_no: int
    status: str
    payload_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskEventResponse(BaseModel):
    """Serialized task event."""

    id: str
    tenant_id: str
    workspace_id: str
    task_id: str
    event_type: str
    payload_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskDetailResponse(BaseModel):
    """Task detail with events and checkpoints."""

    task: TaskResponse
    checkpoints: list[TaskCheckpointResponse]
    events: list[TaskEventResponse]


class TaskControlResponse(BaseModel):
    """Result of a task lifecycle control action."""

    task: TaskResponse
    action: str


class ThreadResponse(BaseModel):
    """Serialized runtime thread."""

    id: str
    tenant_id: str
    workspace_id: str
    agent_id: Optional[str] = None
    title: Optional[str] = None
    status: str
    thread_type: str
    source: Optional[str] = None
    owner_user_id: Optional[str] = None
    summary: Optional[str] = None
    system_prompt: Optional[str] = None
    default_model_ref: Optional[str] = None
    default_temperature: Optional[float] = None
    default_max_tokens: Optional[int] = None
    default_top_p: Optional[float] = None
    context_window: Optional[int] = None
    max_history_messages: Optional[int] = None
    max_history_chars: Optional[int] = None
    message_count: int
    last_message_at: Optional[datetime] = None
    last_user_message_at: Optional[datetime] = None
    last_assistant_message_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    pinned_at: Optional[datetime] = None
    knowledge_config_json: dict[str, Any]
    tool_config_json: dict[str, Any]
    metadata_json: dict[str, Any]
    latest_run_id: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ThreadMessageResponse(BaseModel):
    """Serialized runtime thread message."""

    id: str
    tenant_id: str
    workspace_id: str
    thread_id: str
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    response_id: Optional[str] = None
    parent_message_id: Optional[str] = None
    sequence_no: int
    role: str
    content: str
    message_type: str
    status: str
    content_json: dict[str, Any]
    summary: Optional[str] = None
    model_ref: Optional[str] = None
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    finish_reason: Optional[str] = None
    citations_json: list[dict[str, Any]]
    attachments_json: list[dict[str, Any]]
    tool_calls_json: list[dict[str, Any]]
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata_json: dict[str, Any]
    created_by: Optional[str] = None
    created_at: datetime
    edited_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ThreadDetailResponse(BaseModel):
    """Thread detail with flattened message ledger."""

    thread: ThreadResponse
    messages: list[ThreadMessageResponse]


class ThreadUpdateRequest(BaseModel):
    """Mutable fields for a runtime thread."""

    title: Optional[str] = None
    status: Optional[str] = None
    thread_type: Optional[str] = None
    source: Optional[str] = None
    summary: Optional[str] = None
    system_prompt: Optional[str] = None
    default_model_ref: Optional[str] = None
    default_temperature: Optional[float] = None
    default_max_tokens: Optional[int] = None
    default_top_p: Optional[float] = None
    context_window: Optional[int] = None
    max_history_messages: Optional[int] = None
    max_history_chars: Optional[int] = None
    knowledge_config_json: Optional[dict[str, Any]] = None
    tool_config_json: Optional[dict[str, Any]] = None
    pinned_at: Optional[datetime] = None
    metadata_json: Optional[dict[str, Any]] = None


class ThreadCreateRequest(BaseModel):
    """Input payload for creating a runtime thread."""

    agent_id: Optional[str] = None
    title: Optional[str] = None
    thread_type: str = "chat"
    source: Optional[str] = None
    summary: Optional[str] = None
    system_prompt: Optional[str] = None
    default_model_ref: Optional[str] = None
    default_temperature: Optional[float] = None
    default_max_tokens: Optional[int] = None
    default_top_p: Optional[float] = None
    context_window: Optional[int] = None
    max_history_messages: Optional[int] = None
    max_history_chars: Optional[int] = None
    knowledge_config_json: Optional[dict[str, Any]] = None
    tool_config_json: Optional[dict[str, Any]] = None
    owner_user_id: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
