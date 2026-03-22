"""Unit tests for RuntimeCoreService."""

from app.kernel.runtime.contracts.status import TaskStatus
from app.kernel.runtime.core.service import RuntimeCoreService


def test_runtime_core_service_creates_thread_and_messages(db, tenant1_ctx):
    """RuntimeCoreService should centralize thread creation and message appends."""

    service = RuntimeCoreService(db, tenant1_ctx)
    thread = service.create_thread(
        agent_id=None,
        title="agent support",
        default_model_ref="model:openai:gpt-5.1",
        system_prompt="be helpful",
    )
    message = service.append_message(
        thread_id=thread.id,
        role="user",
        content="hello core",
        metadata={"citations": [{"id": "c1"}]},
    )

    assert thread.id.startswith("thr_")
    assert thread.default_model_ref == "model:openai:gpt-5.1"
    assert thread.system_prompt == "be helpful"
    assert message.thread_id == thread.id
    assert message.content == "hello core"
    assert message.sequence_no == 1
    assert message.citations_json[0]["id"] == "c1"


def test_runtime_core_service_manages_task_lifecycle(db, tenant1_ctx):
    """RuntimeCoreService should manage task transitions, checkpoints, and events."""

    service = RuntimeCoreService(db, tenant1_ctx)
    task = service.create_task(task_type="agent_batch", input_payload={"batch_size": 2})
    service.transition_task(task_id=task.id, status=TaskStatus.RUNNING.value, progress={"percent": 50})
    service.add_checkpoint(task_id=task.id, checkpoint_no=1, status=TaskStatus.RUNNING.value)
    task = service.transition_task(
        task_id=task.id,
        status=TaskStatus.SUCCEEDED.value,
        output_payload={"result": "ok"},
    )

    assert task.status == TaskStatus.SUCCEEDED.value
    assert task.output_json["result"] == "ok"
