"""Runtime task lifecycle writes outbox rows (Wave B2)."""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks.events import TaskEventType
from app.kernel.runtime.tasks.service import TaskService


@pytest.mark.asyncio
async def test_task_lifecycle_emits_outbox_event_types(async_db, tenant1_ctx) -> None:
    svc = TaskService(async_db, tenant1_ctx)
    task = await svc.create_task(task_type="agent_batch", input_payload={"batch_size": 1})

    types_after_create = {r.event_type for r in (await async_db.exec(select(EventOutbox).where(EventOutbox.task_id == task.id))).all()}
    assert TaskEventType.CREATED in types_after_create

    await svc.transition_task(task_id=task.id, status=TaskStatus.RUNNING.value)
    types = {r.event_type for r in (await async_db.exec(select(EventOutbox).where(EventOutbox.task_id == task.id))).all()}
    assert TaskEventType.STARTED in types

    await svc.add_checkpoint(task_id=task.id, checkpoint_no=1, status=TaskStatus.RUNNING.value)
    types = {r.event_type for r in (await async_db.exec(select(EventOutbox).where(EventOutbox.task_id == task.id))).all()}
    assert TaskEventType.CHECKPOINTED in types

    await svc.transition_task(task_id=task.id, status=TaskStatus.SUCCEEDED.value)
    types = {r.event_type for r in (await async_db.exec(select(EventOutbox).where(EventOutbox.task_id == task.id))).all()}
    assert TaskEventType.COMPLETED in types


@pytest.mark.asyncio
async def test_task_failed_emits_failed_outbox(async_db, tenant1_ctx) -> None:
    svc = TaskService(async_db, tenant1_ctx)
    task = await svc.create_task(task_type="x", input_payload={})
    await svc.transition_task(
        task_id=task.id,
        status=TaskStatus.FAILED.value,
        error_code="E1",
        error_message="boom",
    )
    rows = list((await async_db.exec(select(EventOutbox).where(EventOutbox.task_id == task.id))).all())
    failed = [r for r in rows if r.event_type == TaskEventType.FAILED]
    assert len(failed) == 1
    assert failed[0].payload_json.get("error_code") == "E1"
