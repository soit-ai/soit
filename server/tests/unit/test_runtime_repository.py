"""Unit tests for Runtime Core repositories."""

from sqlalchemy import select
from sqlmodel import Session

from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.tasks import Task, TaskCheckpoint, TaskEvent
from app.kernel.runtime.db.models.threads import Thread, ThreadMessage
from app.kernel.runtime.tasks.repository import TaskRepository
from app.kernel.runtime.threads.repository import ThreadRepository


def test_thread_repository_create_and_list_messages(db, tenant1_ctx):
    """ThreadRepository should manage new Thread and ThreadMessage tables."""

    repo = ThreadRepository(db, tenant1_ctx)
    thread = repo.create_thread(Thread(agent_id=None, title="support session"))
    message = repo.add_message(
        ThreadMessage(
            thread_id=thread.id,
            role="user",
            content="hello runtime",
        )
    )

    thread = repo.touch_thread(thread, latest_run_id="run_demo")
    messages = repo.list_messages(thread.id)

    assert thread.id.startswith("thr_")
    assert message.id.startswith("thmsg_")
    assert thread.latest_run_id == "run_demo"
    assert thread.message_count == 1
    assert thread.last_message_at is not None
    assert message.sequence_no == 1
    assert message.summary == "hello runtime"
    assert message.content_json["text"] == "hello runtime"
    assert [item.content for item in messages] == ["hello runtime"]


def test_task_repository_create_checkpoint_and_event(db, tenant1_ctx):
    """TaskRepository should persist tasks, checkpoints and task events."""

    repo = TaskRepository(db, tenant1_ctx)
    task = repo.create_task(
        Task(
            task_type="knowledge_ingestion",
            status="queued",
            input_json={"document_id": "doc_1"},
        )
    )
    checkpoint = repo.add_checkpoint(
        TaskCheckpoint(
            task_id=task.id,
            checkpoint_no=1,
            status="running",
            payload_json={"stage": "chunking"},
        )
    )
    event = repo.add_event(
        TaskEvent(
            task_id=task.id,
            event_type="task.progress",
            payload_json={"percent": 40},
        )
    )

    task.status = "running"
    task = repo.update_task(task)

    assert task.id.startswith("task_")
    assert checkpoint.id.startswith("tcp_")
    assert event.id.startswith("tevt_")
    assert repo.get_task(task.id).status == "running"
    assert repo.list_checkpoints(task.id)[0].payload_json["stage"] == "chunking"
    assert repo.list_events(task.id)[0].event_type == "task.progress"


def test_task_and_outbox_rollback_together(db, tenant1_ctx):
    repo = TaskRepository(db, tenant1_ctx)
    task = repo.create_task(Task(task_type="agent", status="queued"))

    db.rollback()

    check = Session(db.get_bind())
    try:
        assert check.get(Task, task.id) is None
        events = list(
            check.exec(
                select(EventOutbox).where(EventOutbox.task_id == task.id)
            ).all()
        )
        assert events == []
    finally:
        check.close()


def test_thread_and_message_rollback_together(db, tenant1_ctx):
    repo = ThreadRepository(db, tenant1_ctx)
    thread = repo.create_thread(Thread(title="atomic thread"))
    message = repo.add_message(
        ThreadMessage(thread_id=thread.id, role="user", content="atomic message")
    )

    db.rollback()

    check = Session(db.get_bind())
    try:
        assert check.get(Thread, thread.id) is None
        assert check.get(ThreadMessage, message.id) is None
    finally:
        check.close()
