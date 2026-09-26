"""An approval decided outside the chat resumes the paused agent run end to end.

The first AG-UI request stops for approval. The approver answers on the
approvals API with no chat client connected; the outbox consumer queues the
resume and the durable interaction worker finishes the run on the same
response, task and run.
"""

from __future__ import annotations

import pytest
from fastapi import status

from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers
from app.wiring.response_interaction_worker import GlobalResponseInteractionWorker
from tests.entrypoints.test_responses_api import (
    _agui_agent_run_input,
    _stream_agui_response,
)

INTERRUPT_ID = "server_resume_interrupt"
HEADERS = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


@pytest.mark.asyncio
async def test_an_approval_on_the_approvals_api_finishes_the_paused_run(
    async_client, async_db, ctx, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.v1.agent.dependencies import get_agent_stream_executor
    from app.kernel.runtime.tasks.service import TaskService
    from app.main import app
    from app.modules.observe.application.schemas import ApprovalCreate
    from app.modules.observe.application.service import ObserveService

    trace_writer = TraceWriter(async_db, ctx)
    task_service = TaskService(async_db, ctx)
    observe_service = ObserveService(async_db, ctx)
    ids: dict[str, str] = {}
    resumed_with: list[dict] = []

    def response_service() -> ResponseService:
        return ResponseService(
            db=async_db,
            ctx=ctx,
            response_repo=ResponseRepository(async_db, ctx),
            event_repo=ResponseEventRepository(async_db, ctx),
            trace_writer=trace_writer,
        )

    async def execute_agent(agent_id, inputs, event_emitter, on_response_started=None, response_metadata=None):
        service = response_service()
        assert on_response_started is not None
        if not inputs.get("_agui_resume"):
            run = await trace_writer.create_run(
                "agent",
                kind="agent",
                subject_kind="agent",
                subject_id=agent_id,
                subject_version_id="version_server_resume",
            )
            await trace_writer.update_run_status(run.id, "running")
            task = await task_service.create_task(
                task_type="agent.stream",
                status="running",
                agent_id=agent_id,
                thread_id=inputs["thread_id"],
                run_id=run.id,
            )
            response = await service.create_linked_response(
                run_id=run.id,
                thread_id=inputs["thread_id"],
                task_id=task.id,
                agent_id=agent_id,
                metadata_json=response_metadata,
                emit_initial_events=False,
            )
            response = await service.mark_running(response)
            await on_response_started(response, service)
            approval = await observe_service.create_approval(
                ApprovalCreate(
                    run_id=run.id,
                    task_id=task.id,
                    thread_id=inputs["thread_id"],
                    agent_id=agent_id,
                    title="Approve the deletion",
                    details_json={"interrupt_id": INTERRUPT_ID, "tool_ref": "tool:test:delete"},
                )
            )
            ids.update(run_id=run.id, task_id=task.id, response_id=response.id, approval_id=approval.id)
            await task_service.transition_task(task_id=task.id, status="waiting_approval")
            await trace_writer.update_run_status(run.id, "waiting_approval")
            interrupt = {"id": INTERRUPT_ID, "reason": "tool_call", "message": "Approve the deletion"}
            await event_emitter("agent.approval.required", {"run_id": run.id, "interrupt": interrupt})
            return {
                "status": "waiting_approval",
                "interrupt": interrupt,
                "run_id": run.id,
                "response_id": response.id,
                "task_id": task.id,
                "thread_id": inputs["thread_id"],
                "output": "",
            }

        resumed_with.append(inputs)
        response = await service.get_response(ids["response_id"])
        await task_service.resume_task(task_id=ids["task_id"])
        await trace_writer.update_run_status(ids["run_id"], "running")
        await on_response_started(response, service)
        await event_emitter("agent.response.succeeded", {"output": "Deleted after approval."})
        await service.complete_response(
            response=response,
            output_json={"text": "Deleted after approval."},
            output_event_type=None,
            completed_event_type=None,
        )
        await task_service.transition_task(task_id=ids["task_id"], status="succeeded")
        await trace_writer.update_run_status(ids["run_id"], "succeeded")
        return {
            "run_id": ids["run_id"],
            "response_id": response.id,
            "task_id": ids["task_id"],
            "thread_id": inputs["thread_id"],
            "output": "Deleted after approval.",
        }

    class WorkerAgentService:
        execute_agent_streaming = staticmethod(execute_agent)

    app.dependency_overrides[get_agent_stream_executor] = lambda: execute_agent
    monkeypatch.setattr(
        "app.wiring.response_interaction_worker.build_agent_service",
        lambda **_: WorkerAgentService(),
    )
    try:
        thread = await async_client.post("/api/v1/threads", json={"title": "server resume"}, headers=HEADERS)
        thread_id = thread.json()["data"]["id"]
        _, first_events = await _stream_agui_response(
            async_client,
            headers=HEADERS,
            payload=_agui_agent_run_input(
                thread_id=thread_id,
                run_id="interaction_server_resume_first",
                agent_id="agent_server_resume",
                content="delete the stale branch",
            ),
        )
        assert first_events[-1]["outcome"]["type"] == "interrupt"

        decided = await async_client.post(
            f"/api/v1/observe/approvals/{ids['approval_id']}/resolve",
            json={"status": "approved"},
            headers=HEADERS,
        )
        assert decided.status_code == status.HTTP_200_OK

        register_outbox_handlers()
        dispatcher = OutboxDispatcher(async_db, get_outbox_registry())
        while await dispatcher.run_once(batch_limit=50):
            pass
        await async_db.commit()

        executed = await GlobalResponseInteractionWorker(db_factory=lambda: async_db).run_once()
        assert executed is not None
    finally:
        app.dependency_overrides.pop(get_agent_stream_executor, None)

    assert len(resumed_with) == 1
    assert resumed_with[0]["_agui_resume"][0]["approval_status"] == "approved"
    assert resumed_with[0]["_resume_execution"]["response_id"] == ids["response_id"]

    service = response_service()
    assert (await task_service.get_task(ids["task_id"])).status == "succeeded"
    assert (await service.get_response(ids["response_id"])).status == "succeeded"
    parent = await service.get_interaction("interaction_server_resume_first")
    assert parent is not None and parent.resume_interaction_id
    child = await service.get_interaction(parent.resume_interaction_id)
    assert child is not None and child.status == "succeeded"
    assert child.response_id == ids["response_id"]
