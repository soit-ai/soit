"""Emit runtime task facts into event_outbox in the same Session as task writes.

Only ``task.retried`` travels through the outbox: its consumer re-drives the
task and needs exactly-once delivery. Every other lifecycle fact is durable in
``task_events`` and observed in-process where it is written.
"""

from __future__ import annotations

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.tasks.events import TaskEventType


def task_fact_payload(task: Task, **extra: Any) -> dict[str, Any]:
    """The fact payload shared by the outbox row and the inline usage log."""
    data: dict[str, Any] = {
        "task_id": task.id,
        "task_type": task.task_type,
        "status": task.status,
    }
    if task.run_id:
        data["run_id"] = task.run_id
    if task.thread_id:
        data["thread_id"] = task.thread_id
    if task.agent_id:
        data["agent_id"] = task.agent_id
    if task.error_code:
        data["error_code"] = task.error_code
    if task.error_message:
        data["error_message"] = task.error_message
    data.update(extra)
    return data


def enqueue_task_outbox_event(
    db: AsyncSession,
    ctx: RequestContext,
    *,
    event_type: str,
    task: Task,
    payload_extra: dict[str, Any] | None = None,
) -> None:
    """Stage one outbox row (caller commits)."""
    slug = event_type.replace(".", "_")
    if event_type == TaskEventType.RETRIED:
        event_id = f"evt_task_retried_{task.id}_{generate_ulid()}"
    else:
        event_id = f"evt_{slug}_{task.id}"
    correlation = task.run_id or task.id
    payload = task_fact_payload(task, **(payload_extra or {}))
    envelope = DomainEventEnvelope(
        event_id=event_id,
        event_type=event_type,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        subject_type="task",
        subject_id=task.id,
        run_id=task.run_id,
        task_id=task.id,
        thread_id=task.thread_id,
        correlation_id=correlation,
        producer="kernel.runtime.task_repository",
        occurred_at=utc_now(),
        payload=payload,
    )
    OutboxPublisher(OutboxRepository(db)).publish(envelope)
