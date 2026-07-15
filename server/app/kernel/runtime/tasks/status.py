"""Backward-compatible import surface for canonical runtime statuses."""

from app.kernel.runtime.status import (
    TASK_STATUS_TRANSITIONS,
    TERMINAL_EXECUTION_STATUSES,
    WAITING_EXECUTION_STATUSES,
    ApprovalStatus,
    ExecutionStatus,
    PublishStatus,
    ResourceStatus,
    RuntimeTransitionError,
    TaskStatus,
    validate_task_transition,
)

TaskTransitionError = RuntimeTransitionError

__all__ = [
    "ApprovalStatus",
    "ExecutionStatus",
    "PublishStatus",
    "ResourceStatus",
    "TASK_STATUS_TRANSITIONS",
    "TERMINAL_EXECUTION_STATUSES",
    "TaskStatus",
    "TaskTransitionError",
    "WAITING_EXECUTION_STATUSES",
    "validate_task_transition",
]
