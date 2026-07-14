"""Unified runtime status contracts.

These enums provide the target status language for the refactor.
Runtime code should adopt these enums from the start when adding or changing
state transitions.
"""

from enum import Enum


class ExecutionStatus(str, Enum):
    """Shared lifecycle for run-like execution records."""

    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    EXPIRED = "expired"
    SKIPPED = "skipped"


class ResourceStatus(str, Enum):
    """Shared status language for manageable workspace resources."""

    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"
    ERROR = "error"


class PublishStatus(str, Enum):
    """Publication lifecycle for publishable resources."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class TaskStatus(str, Enum):
    """Task lifecycle aligned with the runtime execution language."""

    QUEUED = ExecutionStatus.QUEUED.value
    PREPARING = ExecutionStatus.PREPARING.value
    RUNNING = ExecutionStatus.RUNNING.value
    WAITING_INPUT = ExecutionStatus.WAITING_INPUT.value
    WAITING_APPROVAL = ExecutionStatus.WAITING_APPROVAL.value
    PAUSED = ExecutionStatus.PAUSED.value
    RETRYING = ExecutionStatus.RETRYING.value
    SUCCEEDED = ExecutionStatus.SUCCEEDED.value
    FAILED = ExecutionStatus.FAILED.value
    CANCELED = ExecutionStatus.CANCELED.value
    EXPIRED = ExecutionStatus.EXPIRED.value


class ApprovalStatus(str, Enum):
    """Approval lifecycle for runtime interception points."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELED = "canceled"


TERMINAL_EXECUTION_STATUSES = frozenset(
    {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELED,
        ExecutionStatus.EXPIRED,
    }
)

WAITING_EXECUTION_STATUSES = frozenset(
    {
        ExecutionStatus.WAITING_INPUT,
        ExecutionStatus.WAITING_APPROVAL,
    }
)


class TaskTransitionError(ValueError):
    """Raised when a task status transition is not allowed."""


TASK_STATUS_TRANSITIONS = {
    TaskStatus.QUEUED: frozenset(
        {
            TaskStatus.PREPARING,
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
            TaskStatus.CANCELED,
            TaskStatus.EXPIRED,
        }
    ),
    TaskStatus.PREPARING: frozenset(
        {
            TaskStatus.RUNNING,
            TaskStatus.WAITING_INPUT,
            TaskStatus.WAITING_APPROVAL,
            TaskStatus.PAUSED,
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELED,
            TaskStatus.EXPIRED,
        }
    ),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.WAITING_INPUT,
            TaskStatus.WAITING_APPROVAL,
            TaskStatus.PAUSED,
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELED,
            TaskStatus.EXPIRED,
        }
    ),
    TaskStatus.WAITING_INPUT: frozenset({TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELED, TaskStatus.EXPIRED}),
    TaskStatus.WAITING_APPROVAL: frozenset(
        {TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELED, TaskStatus.EXPIRED}
    ),
    TaskStatus.PAUSED: frozenset({TaskStatus.RUNNING, TaskStatus.CANCELED, TaskStatus.EXPIRED}),
    TaskStatus.RETRYING: frozenset({TaskStatus.QUEUED, TaskStatus.PREPARING, TaskStatus.RUNNING, TaskStatus.CANCELED}),
    TaskStatus.SUCCEEDED: frozenset(),
    TaskStatus.FAILED: frozenset({TaskStatus.RETRYING}),
    TaskStatus.CANCELED: frozenset({TaskStatus.RETRYING}),
    TaskStatus.EXPIRED: frozenset({TaskStatus.RETRYING}),
}


def normalize_task_status(status: str | TaskStatus) -> TaskStatus:
    """Normalize task status values to TaskStatus."""

    try:
        return status if isinstance(status, TaskStatus) else TaskStatus(str(status))
    except ValueError as exc:
        raise TaskTransitionError(f"Unknown task status: {status}") from exc


def validate_task_transition(current: str | TaskStatus, target: str | TaskStatus) -> str:
    """Validate a task transition and return the normalized target value."""

    current_status = normalize_task_status(current)
    target_status = normalize_task_status(target)
    if current_status == target_status:
        return target_status.value
    if target_status not in TASK_STATUS_TRANSITIONS.get(current_status, frozenset()):
        raise TaskTransitionError(f"Invalid task transition: {current_status.value} -> {target_status.value}")
    return target_status.value
