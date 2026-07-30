"""Drivers that re-execute tasks from their persisted execution snapshot.

A task records one execution attempt. Retrying therefore cannot resume the
original attempt: replaying its snapshot produces a new run and a new task.
The driver closes out the attempt being retried and points it at the new one,
so nothing is left sitting in a state that never completes.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.responses import (
    ResponseInteraction,
    generate_response_interaction_id,
)
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.db.models.threads import generate_thread_message_id
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks.drivers import register_task_driver
from app.kernel.runtime.tasks.service import TaskService

logger = logging.getLogger(__name__)

RETRYABLE_TASK_TYPES = ("agent.stream",)
"""Task types whose execution is captured in a replayable interaction."""

SNAPSHOT_MISSING_ERROR_CODE = "TASK_RETRY_SNAPSHOT_MISSING"


def _latest_snapshot(db: Session, task: Task) -> ResponseInteraction | None:
    """Return the interaction that drove this task's run, if one was persisted."""
    if not task.run_id:
        return None
    query = (
        select(ResponseInteraction)
        .where(
            ResponseInteraction.tenant_id == task.tenant_id,
            ResponseInteraction.workspace_id == task.workspace_id,
            ResponseInteraction.run_id == task.run_id,
        )
        .order_by(ResponseInteraction.created_at.desc())
        .limit(1)
    )
    return db.execute(query).scalars().first()


def _context(task: Task, snapshot: ResponseInteraction) -> RequestContext:
    stored = dict(snapshot.request_context_json or {})
    if stored:
        return RequestContext(**stored)
    return RequestContext(
        tenant_id=task.tenant_id,
        workspace_id=task.workspace_id,
        user_id=task.created_by or "system",
        tenant_role="Owner",
        workspace_role="Owner",
    )


def _fail(db: Session, task: Task, *, error_code: str, message: str) -> None:
    now = utc_now()
    task.status = TaskStatus.FAILED.value
    task.error_code = error_code
    task.error_message = message
    task.finished_at = now
    task.updated_at = now
    db.add(task)
    db.commit()


def drive_agent_task_retry(db: Session, task: Task) -> None:
    """Re-enqueue the interaction snapshot behind an agent task."""
    snapshot = _latest_snapshot(db, task)
    if snapshot is None or not snapshot.execution_json:
        logger.warning(
            "No interaction snapshot to replay for task %s",
            task.id,
            extra={"task_id": task.id, "run_id": task.run_id},
        )
        _fail(
            db,
            task,
            error_code=SNAPSHOT_MISSING_ERROR_CODE,
            message="No persisted execution snapshot is available to replay",
        )
        return

    interaction_id = generate_response_interaction_id()
    execution_json = dict(snapshot.execution_json)
    # The stored id addresses the previous attempt's assistant message; reusing
    # it would append this attempt's output onto the old message.
    execution_json["assistant_message_id"] = generate_thread_message_id()
    payload = dict(execution_json.get("payload") or {})
    if payload:
        # Drop identifiers that belong to the attempt being replaced so the
        # replay creates its own response, run and task.
        payload.pop("task_id", None)
        payload.pop("run_id", None)
        execution_json["payload"] = payload

    replay = ResponseInteraction(
        tenant_id=snapshot.tenant_id,
        workspace_id=snapshot.workspace_id,
        interaction_id=interaction_id,
        parent_interaction_id=None,
        response_id=None,
        run_id=None,
        thread_id=snapshot.thread_id,
        request_hash=interaction_id,
        execution_json=execution_json,
        request_context_json=dict(snapshot.request_context_json or {}),
        kind=snapshot.kind,
        status="queued",
        created_by=task.created_by,
    )
    db.add(replay)
    db.commit()

    # This attempt is over: the durable worker now owns the replacement. Leaving
    # it queued would report work that this task will never perform.
    TaskService(db, _context(task, snapshot)).transition_task(
        task_id=task.id,
        status=TaskStatus.CANCELED.value,
        progress={
            **(task.progress_json or {}),
            "action": "retried",
            "retried_as_interaction_id": interaction_id,
        },
    )


def register_task_drivers() -> None:
    """Register every task type that can actually be re-executed."""
    for task_type in RETRYABLE_TASK_TYPES:
        register_task_driver(task_type, drive_agent_task_retry)
