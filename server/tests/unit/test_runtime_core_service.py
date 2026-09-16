"""Unit tests for runtime thread and task services."""

import pytest

from app.kernel.runtime.db.models.threads import Thread, ThreadMessage
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks.service import TaskService
from app.kernel.runtime.threads.service import ThreadService

pytestmark = pytest.mark.asyncio


class FakeTaskRepository:
    def __init__(self) -> None:
        self.tasks = []
        self.events = []

    async def create_task(self, task):
        self.tasks.append(task)
        return task

    async def add_event(self, event):
        self.events.append(event)
        return event


class FakeThreadRepository:
    def __init__(self) -> None:
        self.threads = {}
        self.messages = []

    async def create_thread(self, thread):
        thread.id = "thr_fake"
        self.threads[thread.id] = thread
        return thread

    async def get_thread(self, thread_id):
        return self.threads.get(thread_id)

    async def update_thread(self, thread_id, **kwargs):
        thread = self.threads.get(thread_id)
        if not thread:
            return None
        for key, value in kwargs.items():
            if value is not None and value is not ...:
                setattr(thread, f"{key}_json" if key == "metadata" else key, value)
        return thread

    async def soft_delete_thread(self, thread_id):
        thread = self.threads.get(thread_id)
        if thread:
            thread.deleted_at = object()
        return thread

    async def add_message(self, message):
        message.id = f"thmsg_fake_{len(self.messages) + 1}"
        message.sequence_no = len(self.messages) + 1
        self.messages.append(message)
        return message


async def test_task_service_accepts_repository_protocols(tenant1_ctx):
    task_repo = FakeTaskRepository()
    service = TaskService(None, tenant1_ctx, task_repo=task_repo)

    task = await service.create_task(task_type="fake_task")

    assert task.task_type == "fake_task"
    assert task_repo.tasks == [task]
    assert task_repo.events[0].event_type == "task.created"


async def test_thread_service_accepts_repository_protocols(tenant1_ctx):
    thread_repo = FakeThreadRepository()
    service = ThreadService(None, tenant1_ctx, thread_repo=thread_repo)

    thread = await service.create_thread(agent_id="agent_1", title="protocol thread")
    message = await service.append_message(
        thread_id=thread.id,
        role="user",
        content="hello protocol",
        metadata={"citations": [{"id": "c1"}]},
        citations_json=[{"id": "c1"}],
    )

    assert isinstance(thread, Thread)
    assert isinstance(message, ThreadMessage)
    assert thread_repo.threads[thread.id] is thread
    assert thread_repo.messages == [message]
    assert message.sequence_no == 1
    assert message.citations_json == [{"id": "c1"}]


async def test_thread_service_creates_thread_and_messages(async_db, tenant1_ctx):
    """ThreadService should centralize thread creation and message appends."""

    service = ThreadService(async_db, tenant1_ctx)
    thread = await service.create_thread(
        agent_id=None,
        title="agent support",
        default_model_ref="model:openai:gpt-5.1",
        system_prompt="be helpful",
    )
    message = await service.append_message(
        thread_id=thread.id,
        role="user",
        content="hello core",
        metadata={"citations": [{"id": "c1"}]},
        citations_json=[{"id": "c1"}],
    )

    assert thread.id.startswith("thr_")
    assert thread.default_model_ref == "model:openai:gpt-5.1"
    assert thread.system_prompt == "be helpful"
    assert message.thread_id == thread.id
    assert message.content == "hello core"
    assert message.sequence_no == 1
    assert message.citations_json[0]["id"] == "c1"


async def test_task_service_manages_task_lifecycle(async_db, tenant1_ctx):
    """TaskService should manage task transitions, checkpoints, and events."""

    service = TaskService(async_db, tenant1_ctx)
    task = await service.create_task(task_type="agent_batch", input_payload={"batch_size": 2})
    await service.transition_task(
        task_id=task.id, status=TaskStatus.RUNNING.value, progress={"percent": 50}
    )
    await service.add_checkpoint(task_id=task.id, checkpoint_no=1, status=TaskStatus.RUNNING.value)
    task = await service.transition_task(
        task_id=task.id,
        status=TaskStatus.SUCCEEDED.value,
        output_payload={"result": "ok"},
    )

    assert task.status == TaskStatus.SUCCEEDED.value
    assert task.output_json["result"] == "ok"
