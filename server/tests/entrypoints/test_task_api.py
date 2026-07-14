"""Entrypoint tests for runtime task workbench APIs."""

from datetime import timedelta

from fastapi import status

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.tasks import Task, TaskCheckpoint, TaskEvent
from app.kernel.runtime.tasks.status import TaskStatus


def _headers() -> dict[str, str]:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def _task(
    *,
    task_id: str,
    task_type: str,
    task_status: str,
    minutes_old: int = 5,
    workspace_id: str = "test-workspace",
    error_message: str | None = None,
) -> Task:
    now = utc_now()
    timestamp = now - timedelta(minutes=minutes_old)
    return Task(
        id=task_id,
        tenant_id="test-tenant",
        workspace_id=workspace_id,
        task_type=task_type,
        status=task_status,
        input_json={"title": f"{task_type} title"},
        output_json={},
        progress_json={"stage": "seeded"},
        error_code="TASK_FAILED" if error_message else None,
        error_message=error_message,
        run_id=f"run_{task_id}",
        thread_id=f"thr_{task_id}",
        created_by="task-owner",
        updated_by="task-owner",
        created_at=timestamp,
        updated_at=timestamp,
        started_at=timestamp if task_status != TaskStatus.QUEUED.value else None,
        finished_at=now if task_status == TaskStatus.SUCCEEDED.value else None,
    )


def _seed_tasks(db) -> None:
    tasks = [
        _task(
            task_id="task_failed_contract",
            task_type="wf_step",
            task_status=TaskStatus.FAILED.value,
            error_message="contract_id is empty",
        ),
        _task(
            task_id="task_waiting_input_contract",
            task_type="agent.stream",
            task_status=TaskStatus.WAITING_INPUT.value,
        ),
        _task(
            task_id="task_waiting_approval_contract",
            task_type="approval_gate",
            task_status=TaskStatus.WAITING_APPROVAL.value,
        ),
        _task(
            task_id="task_running_contract",
            task_type="agent.execute",
            task_status=TaskStatus.RUNNING.value,
        ),
        _task(
            task_id="task_long_running_contract",
            task_type="agent.execute",
            task_status=TaskStatus.RUNNING.value,
            minutes_old=45,
        ),
        _task(
            task_id="task_succeeded_contract",
            task_type="data.sync",
            task_status=TaskStatus.SUCCEEDED.value,
        ),
        _task(
            task_id="task_other_workspace_contract",
            task_type="agent.execute",
            task_status=TaskStatus.FAILED.value,
            workspace_id="other-workspace",
            error_message="hidden",
        ),
    ]
    db.add_all(tasks)
    db.add(
        TaskEvent(
            tenant_id="test-tenant",
            workspace_id="test-workspace",
            task_id="task_failed_contract",
            event_type="task.failed",
            payload_json={"message": "contract_id is empty"},
        )
    )
    db.add(
        TaskCheckpoint(
            tenant_id="test-tenant",
            workspace_id="test-workspace",
            task_id="task_failed_contract",
            checkpoint_no=1,
            status=TaskStatus.FAILED.value,
            payload_json={"node": "contract review"},
        )
    )
    db.commit()


def test_task_workbench_returns_summary_tabs_and_rows(client, db):
    _seed_tasks(db)

    response = client.get("/api/v1/tasks/workbench?page_size=10", headers=_headers())

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["summary"]["total_tasks"] == 6
    assert payload["summary"]["failed"] == 1
    assert payload["summary"]["waiting_input"] == 1
    assert payload["summary"]["waiting_approval"] == 1
    assert payload["summary"]["running"] == 2
    assert payload["summary"]["long_running"] == 1
    assert payload["tabs"]["all"] == 6
    assert payload["tabs"]["failed"] == 1
    assert payload["total"] == 6
    assert {item["id"] for item in payload["items"]} >= {
        "task_failed_contract",
        "task_long_running_contract",
    }
    assert all(item["workspace_id"] == "test-workspace" for item in payload["items"])


def test_task_workbench_items_support_filters_total_and_static_route(client, db):
    _seed_tasks(db)
    failed_task = db.get(Task, "task_failed_contract")
    assert failed_task is not None
    today = failed_task.updated_at.date().isoformat()

    response = client.get(
        f"/api/v1/tasks/workbench/items?tab=failed&keyword=contract&page_size=1&date_from={today}&date_to={today}",
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["total"] == 1
    assert payload["page_size"] == 1
    assert payload["items"][0]["id"] == "task_failed_contract"
    assert payload["items"][0]["display_name"] == "wf_step title"
    assert payload["next_page_token"] is None


def test_task_handling_returns_available_actions_and_runtime_context(client, db):
    _seed_tasks(db)

    failed = client.get("/api/v1/tasks/task_failed_contract/handling", headers=_headers())
    waiting = client.get("/api/v1/tasks/task_waiting_input_contract/handling", headers=_headers())
    running = client.get("/api/v1/tasks/task_running_contract/handling", headers=_headers())
    succeeded = client.get("/api/v1/tasks/task_succeeded_contract/handling", headers=_headers())
    hidden = client.get("/api/v1/tasks/task_other_workspace_contract/handling", headers=_headers())

    assert failed.status_code == status.HTTP_200_OK
    failed_payload = failed.json()["data"]
    assert failed_payload["available_actions"] == ["retry"]
    assert failed_payload["summary"]["error_message"] == "contract_id is empty"
    assert failed_payload["runtime_context"]["run_id"] == "run_task_failed_contract"
    assert failed_payload["events"][0]["event_type"] == "task.failed"
    assert failed_payload["checkpoints"][0]["checkpoint_no"] == 1

    assert waiting.json()["data"]["available_actions"] == ["resume", "cancel"]
    assert running.json()["data"]["available_actions"] == ["cancel"]
    assert succeeded.json()["data"]["available_actions"] == []
    assert hidden.status_code == status.HTTP_404_NOT_FOUND
