"""Unit tests for centralized runtime status transitions."""

from __future__ import annotations

import pytest

from app.kernel.runtime.tasks.status import (
    TaskStatus,
    TaskTransitionError,
    validate_task_transition,
)


def test_task_transition_allows_same_status_idempotency():
    assert validate_task_transition(TaskStatus.SUCCEEDED.value, TaskStatus.SUCCEEDED.value) == TaskStatus.SUCCEEDED.value


def test_task_transition_allows_retry_from_terminal_statuses():
    assert validate_task_transition(TaskStatus.FAILED.value, TaskStatus.RETRYING.value) == TaskStatus.RETRYING.value
    assert validate_task_transition(TaskStatus.CANCELED.value, TaskStatus.RETRYING.value) == TaskStatus.RETRYING.value
    assert validate_task_transition(TaskStatus.EXPIRED.value, TaskStatus.RETRYING.value) == TaskStatus.RETRYING.value


def test_task_transition_rejects_terminal_status_to_running():
    with pytest.raises(TaskTransitionError, match="Invalid task transition"):
        validate_task_transition(TaskStatus.SUCCEEDED.value, TaskStatus.RUNNING.value)


def test_task_transition_rejects_queue_to_terminal_without_running():
    with pytest.raises(TaskTransitionError, match="Invalid task transition"):
        validate_task_transition(TaskStatus.QUEUED.value, TaskStatus.SUCCEEDED.value)
