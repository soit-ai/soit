"""Runtime task API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ThreadResponse(BaseModel):
    """Serialized runtime thread."""

    id: str
    tenant_id: str
    workspace_id: str
    agent_id: str | None = None
    title: str | None = None
    status: str
    thread_type: str
    source: str | None = None
    owner_user_id: str | None = None
    summary: str | None = None
    system_prompt: str | None = None
    default_model_ref: str | None = None
    default_temperature: float | None = None
    default_max_tokens: int | None = None
    default_top_p: float | None = None
    context_window: int | None = None
    max_history_messages: int | None = None
    max_history_chars: int | None = None
    message_count: int
    last_message_at: datetime | None = None
    last_user_message_at: datetime | None = None
    last_assistant_message_at: datetime | None = None
    archived_at: datetime | None = None
    pinned_at: datetime | None = None
    knowledge_config_json: dict[str, Any]
    tool_config_json: dict[str, Any]
    metadata_json: dict[str, Any]
    latest_run_id: str | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ThreadMessageResponse(BaseModel):
    """Serialized runtime thread message."""

    id: str
    tenant_id: str
    workspace_id: str
    thread_id: str
    run_id: str | None = None
    task_id: str | None = None
    response_id: str | None = None
    parent_message_id: str | None = None
    sequence_no: int
    role: str
    content: str
    message_type: str
    status: str
    content_json: dict[str, Any]
    summary: str | None = None
    model_ref: str | None = None
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    finish_reason: str | None = None
    citations_json: list[dict[str, Any]]
    attachments_json: list[dict[str, Any]]
    tool_calls_json: list[dict[str, Any]]
    error_code: str | None = None
    error_message: str | None = None
    metadata_json: dict[str, Any]
    created_by: str | None = None
    created_at: datetime
    edited_at: datetime | None = None
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ThreadDetailResponse(BaseModel):
    """Thread detail with flattened message ledger."""

    thread: ThreadResponse
    messages: list[ThreadMessageResponse]


class ThreadUpdateRequest(BaseModel):
    """Mutable fields for a runtime thread."""

    title: str | None = None
    status: str | None = None
    thread_type: str | None = None
    source: str | None = None
    summary: str | None = None
    system_prompt: str | None = None
    default_model_ref: str | None = None
    default_temperature: float | None = None
    default_max_tokens: int | None = None
    default_top_p: float | None = None
    context_window: int | None = None
    max_history_messages: int | None = None
    max_history_chars: int | None = None
    knowledge_config_json: dict[str, Any] | None = None
    tool_config_json: dict[str, Any] | None = None
    pinned_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None


class ThreadCreateRequest(BaseModel):
    """Input payload for creating a runtime thread."""

    agent_id: str | None = None
    title: str | None = None
    thread_type: str = "chat"
    source: str | None = None
    summary: str | None = None
    system_prompt: str | None = None
    default_model_ref: str | None = None
    default_temperature: float | None = None
    default_max_tokens: int | None = None
    default_top_p: float | None = None
    context_window: int | None = None
    max_history_messages: int | None = None
    max_history_chars: int | None = None
    knowledge_config_json: dict[str, Any] | None = None
    tool_config_json: dict[str, Any] | None = None
    owner_user_id: str | None = None
    metadata_json: dict[str, Any] | None = None
