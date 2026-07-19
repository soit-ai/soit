"""Unit tests for centralized runtime status transitions."""

from __future__ import annotations

import pytest

from app.kernel.runtime.status import (
    ExecutionStatus,
    RuntimeTransitionError,
    TaskStatus,
    validate_response_transition,
    validate_run_transition,
    validate_step_transition,
    validate_task_transition,
)


def test_run_transition_supports_full_runtime_lifecycle():
    assert validate_run_transition("queued", "preparing") == "preparing"
    assert validate_run_transition("preparing", "running") == "running"
    assert validate_run_transition("running", "waiting_approval") == "waiting_approval"
    assert validate_run_transition("waiting_approval", "running") == "running"
    assert validate_run_transition("running", "succeeded") == "succeeded"


def test_run_transition_rejects_stale_terminal_overwrite():
    with pytest.raises(RuntimeTransitionError, match="Invalid run transition"):
        validate_run_transition("succeeded", "failed")


def test_run_transition_allows_retry_only_through_retrying():
    assert validate_run_transition("failed", "retrying") == "retrying"
    with pytest.raises(RuntimeTransitionError, match="Invalid run transition"):
        validate_run_transition("failed", "running")


def test_step_transition_supports_skipped_as_terminal():
    assert validate_step_transition("queued", "skipped") == "skipped"
    assert validate_step_transition("skipped", "skipped") == "skipped"
    with pytest.raises(RuntimeTransitionError, match="Invalid step transition"):
        validate_step_transition("skipped", "running")


def test_response_transition_uses_runtime_status_language():
    assert validate_response_transition("queued", "running") == "running"
    assert validate_response_transition("running", "succeeded") == "succeeded"
    with pytest.raises(RuntimeTransitionError, match="Unknown response status"):
        validate_response_transition("in_progress", "succeeded")


def test_execution_status_does_not_treat_skipped_as_a_run_status():
    assert ExecutionStatus.SUCCEEDED.value == "succeeded"
    with pytest.raises(ValueError):
        ExecutionStatus("skipped")


def test_task_transition_allows_same_status_idempotency():
    assert validate_task_transition(TaskStatus.SUCCEEDED.value, TaskStatus.SUCCEEDED.value) == TaskStatus.SUCCEEDED.value


def test_task_transition_allows_retry_from_terminal_statuses():
    assert validate_task_transition(TaskStatus.FAILED.value, TaskStatus.RETRYING.value) == TaskStatus.RETRYING.value
    assert validate_task_transition(TaskStatus.CANCELED.value, TaskStatus.RETRYING.value) == TaskStatus.RETRYING.value
    assert validate_task_transition(TaskStatus.EXPIRED.value, TaskStatus.RETRYING.value) == TaskStatus.RETRYING.value


def test_task_transition_rejects_terminal_status_to_running():
    with pytest.raises(RuntimeTransitionError, match="Invalid task transition"):
        validate_task_transition(TaskStatus.SUCCEEDED.value, TaskStatus.RUNNING.value)


def test_task_transition_rejects_queue_to_terminal_without_running():
    with pytest.raises(RuntimeTransitionError, match="Invalid task transition"):
        validate_task_transition(TaskStatus.QUEUED.value, TaskStatus.SUCCEEDED.value)
