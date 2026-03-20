"""Unit tests for Runtime Core repositories."""

from app.kernel.runtime.models import Task, TaskCheckpoint, TaskEvent, Thread, ThreadMessage
from app.kernel.runtime.repository import TaskRepository, ThreadRepository


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
