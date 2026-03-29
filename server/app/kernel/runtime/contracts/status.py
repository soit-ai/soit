"""Unified runtime status contracts.

These enums provide the target status language for the refactor.
Existing legacy state machines may continue to coexist temporarily, but
new runtime code should adopt these enums from the start.
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
