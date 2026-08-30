"""Runtime task API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TaskResponse(BaseModel):
    """Serialized runtime task."""

    id: str
    tenant_id: str
    workspace_id: str
    agent_id: str | None = None
    thread_id: str | None = None
    run_id: str | None = None
    task_type: str
    status: str
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    progress_json: dict[str, Any]
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
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
    available_actions: list[str] = []
    """Controls the caller may invoke; the server is the only authority."""


class TaskControlResponse(BaseModel):
    """Result of a task lifecycle control action."""

    task: TaskResponse
    action: str


class TaskWorkbenchSummary(BaseModel):
    """Aggregate task metrics for the task workspace."""

    total_tasks: int
    waiting_approval: int
    failed: int
    waiting_input: int
    long_running: int
    running: int
    today_created: int
    today_completed: int
    queued: int = 0
    """Tasks waiting to be picked up. Queue depth, not lifetime volume."""

    oldest_queued_seconds: int | None = None
    """How long the oldest waiting task has been waiting; None when none are."""

    updated_at: datetime


class TaskWorkbenchTabs(BaseModel):
    """Task counts for task workbench tabs."""

    all: int
    waiting_approval: int
    failed: int
    waiting_input: int
    long_running: int
    running: int


class TaskWorkbenchRow(BaseModel):
    """Task row shaped for task center and handling lists."""

    id: str
    tenant_id: str
    workspace_id: str
    display_name: str
    task_type: str
    status: str
    agent_id: str | None = None
    thread_id: str | None = None
    run_id: str | None = None
    owner: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TaskWorkbenchResponse(BaseModel):
    """Task workbench response with accurate totals."""

    summary: TaskWorkbenchSummary
    tabs: TaskWorkbenchTabs
    items: list[TaskWorkbenchRow]
    total: int
    next_page_token: str | None = None
    page_size: int


class TaskWorkbenchItemsResponse(BaseModel):
    """Paginated task workbench rows with an accurate total."""

    items: list[TaskWorkbenchRow]
    total: int
    next_page_token: str | None = None
    page_size: int


class TaskHandlingSummary(BaseModel):
    """Product-oriented summary for the task handling drawer."""

    title: str
    status: str
    task_type: str
    error_code: str | None = None
    error_message: str | None = None
    updated_at: datetime


class TaskRuntimeContext(BaseModel):
    """Runtime identifiers shown in the handling drawer."""

    agent_id: str | None = None
    thread_id: str | None = None
    run_id: str | None = None


class TaskHandlingResponse(BaseModel):
    """Task handling drawer read model."""

    task: TaskResponse
    summary: TaskHandlingSummary
    runtime_context: TaskRuntimeContext
    available_actions: list[str]
    events: list[TaskEventResponse]
    checkpoints: list[TaskCheckpointResponse]
