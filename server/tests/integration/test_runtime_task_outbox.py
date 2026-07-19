"""Runtime task lifecycle writes outbox rows (Wave B2)."""

from __future__ import annotations

from sqlmodel import select

from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks.events import TaskEventType
from app.kernel.runtime.tasks.service import TaskService


def test_task_lifecycle_emits_outbox_event_types(db, tenant1_ctx) -> None:
    svc = TaskService(db, tenant1_ctx)
    task = svc.create_task(task_type="agent_batch", input_payload={"batch_size": 1})

    types_after_create = {r.event_type for r in db.exec(select(EventOutbox).where(EventOutbox.task_id == task.id)).all()}
    assert TaskEventType.CREATED in types_after_create

    svc.transition_task(task_id=task.id, status=TaskStatus.RUNNING.value)
    types = {r.event_type for r in db.exec(select(EventOutbox).where(EventOutbox.task_id == task.id)).all()}
    assert TaskEventType.STARTED in types

    svc.add_checkpoint(task_id=task.id, checkpoint_no=1, status=TaskStatus.RUNNING.value)
    types = {r.event_type for r in db.exec(select(EventOutbox).where(EventOutbox.task_id == task.id)).all()}
    assert TaskEventType.CHECKPOINTED in types

    svc.transition_task(task_id=task.id, status=TaskStatus.SUCCEEDED.value)
    types = {r.event_type for r in db.exec(select(EventOutbox).where(EventOutbox.task_id == task.id)).all()}
    assert TaskEventType.COMPLETED in types


def test_task_failed_emits_failed_outbox(db, tenant1_ctx) -> None:
    svc = TaskService(db, tenant1_ctx)
    task = svc.create_task(task_type="x", input_payload={})
    svc.transition_task(
        task_id=task.id,
        status=TaskStatus.FAILED.value,
        error_code="E1",
        error_message="boom",
    )
    rows = list(db.exec(select(EventOutbox).where(EventOutbox.task_id == task.id)).all())
    failed = [r for r in rows if r.event_type == TaskEventType.FAILED]
    assert len(failed) == 1
    assert failed[0].payload_json.get("error_code") == "E1"
