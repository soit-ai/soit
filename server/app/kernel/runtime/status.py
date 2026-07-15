"""Canonical runtime lifecycle statuses and transition validation."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum


class ExecutionStatus(str, Enum):
    """Lifecycle shared by run-like execution resources."""

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


class StepStatus(str, Enum):
    """Run-step lifecycle, including the step-only skipped terminal state."""

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
    SKIPPED = "skipped"


class ResponseStatus(str, Enum):
    """Public Response lifecycle."""

    QUEUED = ExecutionStatus.QUEUED.value
    RUNNING = ExecutionStatus.RUNNING.value
    SUCCEEDED = ExecutionStatus.SUCCEEDED.value
    FAILED = ExecutionStatus.FAILED.value
    CANCELED = ExecutionStatus.CANCELED.value


class ResourceStatus(str, Enum):
    """Lifecycle for manageable workspace resources."""

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
    """Task lifecycle aligned with ExecutionStatus."""

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


class RuntimeTransitionError(ValueError):
    """Raised when a runtime status or transition is invalid."""


_RUN_TRANSITIONS: Mapping[ExecutionStatus, frozenset[ExecutionStatus]] = {
    ExecutionStatus.QUEUED: frozenset(
        {
            ExecutionStatus.PREPARING,
            ExecutionStatus.RUNNING,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELED,
            ExecutionStatus.EXPIRED,
        }
    ),
    ExecutionStatus.PREPARING: frozenset(
        {
            ExecutionStatus.RUNNING,
            ExecutionStatus.WAITING_INPUT,
            ExecutionStatus.WAITING_APPROVAL,
            ExecutionStatus.PAUSED,
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELED,
            ExecutionStatus.EXPIRED,
        }
    ),
    ExecutionStatus.RUNNING: frozenset(
        {
            ExecutionStatus.WAITING_INPUT,
            ExecutionStatus.WAITING_APPROVAL,
            ExecutionStatus.PAUSED,
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELED,
            ExecutionStatus.EXPIRED,
        }
    ),
    ExecutionStatus.WAITING_INPUT: frozenset(
        {ExecutionStatus.RUNNING, ExecutionStatus.FAILED, ExecutionStatus.CANCELED, ExecutionStatus.EXPIRED}
    ),
    ExecutionStatus.WAITING_APPROVAL: frozenset(
        {ExecutionStatus.RUNNING, ExecutionStatus.FAILED, ExecutionStatus.CANCELED, ExecutionStatus.EXPIRED}
    ),
    ExecutionStatus.PAUSED: frozenset(
        {ExecutionStatus.RUNNING, ExecutionStatus.CANCELED, ExecutionStatus.EXPIRED}
    ),
    ExecutionStatus.RETRYING: frozenset(
        {
            ExecutionStatus.QUEUED,
            ExecutionStatus.PREPARING,
            ExecutionStatus.RUNNING,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELED,
            ExecutionStatus.EXPIRED,
        }
    ),
    ExecutionStatus.SUCCEEDED: frozenset(),
    ExecutionStatus.FAILED: frozenset({ExecutionStatus.RETRYING}),
    ExecutionStatus.CANCELED: frozenset({ExecutionStatus.RETRYING}),
    ExecutionStatus.EXPIRED: frozenset({ExecutionStatus.RETRYING}),
}

_STEP_TRANSITIONS: Mapping[StepStatus, frozenset[StepStatus]] = {
    StepStatus.QUEUED: frozenset(
        {
            StepStatus.PREPARING,
            StepStatus.RUNNING,
            StepStatus.SKIPPED,
            StepStatus.FAILED,
            StepStatus.CANCELED,
            StepStatus.EXPIRED,
        }
    ),
    StepStatus.PREPARING: frozenset(
        {
            StepStatus.RUNNING,
            StepStatus.WAITING_INPUT,
            StepStatus.WAITING_APPROVAL,
            StepStatus.PAUSED,
            StepStatus.SUCCEEDED,
            StepStatus.SKIPPED,
            StepStatus.FAILED,
            StepStatus.CANCELED,
            StepStatus.EXPIRED,
        }
    ),
    StepStatus.RUNNING: frozenset(
        {
            StepStatus.WAITING_INPUT,
            StepStatus.WAITING_APPROVAL,
            StepStatus.PAUSED,
            StepStatus.SUCCEEDED,
            StepStatus.FAILED,
            StepStatus.CANCELED,
            StepStatus.EXPIRED,
        }
    ),
    StepStatus.WAITING_INPUT: frozenset(
        {StepStatus.RUNNING, StepStatus.FAILED, StepStatus.CANCELED, StepStatus.EXPIRED}
    ),
    StepStatus.WAITING_APPROVAL: frozenset(
        {StepStatus.RUNNING, StepStatus.FAILED, StepStatus.CANCELED, StepStatus.EXPIRED}
    ),
    StepStatus.PAUSED: frozenset({StepStatus.RUNNING, StepStatus.CANCELED, StepStatus.EXPIRED}),
    StepStatus.RETRYING: frozenset(
        {
            StepStatus.QUEUED,
            StepStatus.PREPARING,
            StepStatus.RUNNING,
            StepStatus.FAILED,
            StepStatus.CANCELED,
            StepStatus.EXPIRED,
        }
    ),
    StepStatus.SUCCEEDED: frozenset(),
    StepStatus.FAILED: frozenset({StepStatus.RETRYING}),
    StepStatus.CANCELED: frozenset({StepStatus.RETRYING}),
    StepStatus.EXPIRED: frozenset({StepStatus.RETRYING}),
    StepStatus.SKIPPED: frozenset(),
}

_RESPONSE_TRANSITIONS: Mapping[ResponseStatus, frozenset[ResponseStatus]] = {
    ResponseStatus.QUEUED: frozenset(
        {ResponseStatus.RUNNING, ResponseStatus.FAILED, ResponseStatus.CANCELED}
    ),
    ResponseStatus.RUNNING: frozenset(
        {ResponseStatus.SUCCEEDED, ResponseStatus.FAILED, ResponseStatus.CANCELED}
    ),
    ResponseStatus.SUCCEEDED: frozenset(),
    ResponseStatus.FAILED: frozenset(),
    ResponseStatus.CANCELED: frozenset(),
}

TASK_STATUS_TRANSITIONS: Mapping[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus(status.value): frozenset(TaskStatus(target.value) for target in targets)
    for status, targets in _RUN_TRANSITIONS.items()
}


def _normalize_status(value: str | Enum, enum_type: type[Enum], resource: str) -> Enum:
    try:
        return value if isinstance(value, enum_type) else enum_type(str(value))
    except ValueError as exc:
        raise RuntimeTransitionError(f"Unknown {resource} status: {value}") from exc


def _validate_transition(
    current: str | Enum,
    target: str | Enum,
    *,
    enum_type: type[Enum],
    transitions: Mapping[Enum, frozenset[Enum]],
    resource: str,
) -> str:
    current_status = _normalize_status(current, enum_type, resource)
    target_status = _normalize_status(target, enum_type, resource)
    if current_status == target_status:
        return str(target_status.value)
    if target_status not in transitions.get(current_status, frozenset()):
        raise RuntimeTransitionError(
            f"Invalid {resource} transition: {current_status.value} -> {target_status.value}"
        )
    return str(target_status.value)


def validate_run_transition(current: str | ExecutionStatus, target: str | ExecutionStatus) -> str:
    """Validate a Run transition and return the normalized target value."""

    return _validate_transition(
        current,
        target,
        enum_type=ExecutionStatus,
        transitions=_RUN_TRANSITIONS,
        resource="run",
    )


def validate_step_transition(current: str | StepStatus, target: str | StepStatus) -> str:
    """Validate a RunStep transition and return the normalized target value."""

    return _validate_transition(
        current,
        target,
        enum_type=StepStatus,
        transitions=_STEP_TRANSITIONS,
        resource="step",
    )


def validate_response_transition(current: str | ResponseStatus, target: str | ResponseStatus) -> str:
    """Validate a Response transition and return the normalized target value."""

    return _validate_transition(
        current,
        target,
        enum_type=ResponseStatus,
        transitions=_RESPONSE_TRANSITIONS,
        resource="response",
    )


def validate_task_transition(current: str | TaskStatus, target: str | TaskStatus) -> str:
    """Validate a Task transition and return the normalized target value."""

    return _validate_transition(
        current,
        target,
        enum_type=TaskStatus,
        transitions=TASK_STATUS_TRANSITIONS,
        resource="task",
    )
