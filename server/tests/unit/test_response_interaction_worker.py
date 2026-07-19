"""Tests for durable response interaction lease recovery."""

import asyncio
from types import SimpleNamespace

import pytest
from sqlmodel import Session

from app.adapters.agui.responses import AgUiInteractionProtocolAdapter
from app.api.v1.responses.router import _DisconnectAwareQueue
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.schemas import ResponseCreateRequest
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.tasks.service import TaskService
from app.wiring.response_interaction_worker import GlobalResponseInteractionWorker


def _response_service(db, ctx) -> ResponseService:
    return ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )


def test_worker_claims_one_persisted_queued_interaction(db, ctx):
    service = _response_service(db, ctx)
    queued, owns_claim = service.claim_interaction(
        interaction_id="interaction_worker_queue",
        parent_interaction_id=None,
        thread_id="thread_worker_queue",
        request_hash="hash_worker_queue",
        execution_json={"mode": "direct", "payload": {}},
        request_context_json={
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "user_id": ctx.user_id,
        },
    )
    worker = GlobalResponseInteractionWorker(
        db_factory=lambda: db,
        worker_id="worker-test",
    )

    claimed = worker._claim_next(db)

    assert owns_claim is True
    assert claimed is not None and claimed.id == queued.id
    assert claimed.status == "running"
    assert claimed.lease_owner == "worker-test"
    assert claimed.lease_expires_at is not None
    assert claimed.attempt_count == 1


@pytest.mark.asyncio
async def test_inline_event_queue_releases_blocked_producer_after_disconnect():
    queue = _DisconnectAwareQueue(maxsize=1)
    await queue.put({"id": "first"})
    blocked = asyncio.create_task(queue.put({"id": "second"}))
    await asyncio.sleep(0)
    assert blocked.done() is False

    queue.close_consumer()

    await asyncio.wait_for(blocked, timeout=1)
    assert queue.qsize() == 1


@pytest.mark.asyncio
async def test_worker_terminalizes_response_when_setup_fails_after_binding(
    db,
    ctx,
    monkeypatch,
):
    service = _response_service(db, ctx)
    response = service.create_response(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id="thread_worker_setup_failure",
            input={"messages": [{"role": "user", "content": "hello"}]},
        ),
        emit_initial_events=False,
    )
    response = service.mark_running(response)
    service.trace_writer.update_run_status(response.run_id, "running")
    interaction, _ = service.claim_interaction(
        interaction_id="interaction_worker_setup_failure",
        parent_interaction_id=None,
        thread_id="thread_worker_setup_failure",
        request_hash="hash_worker_setup_failure",
        execution_json={"mode": "direct", "payload": {}},
        request_context_json={
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "user_id": ctx.user_id,
        },
    )
    response_id = response.id
    response_run_id = response.run_id
    interaction_id = interaction.interaction_id

    worker = GlobalResponseInteractionWorker(db_factory=lambda: db)

    async def fail_after_binding(session, claimed):
        claimed.response_id = response.id
        claimed.run_id = response.run_id
        session.add(claimed)
        session.commit()
        raise RuntimeError("setup failed after binding")

    worker._execute = fail_after_binding  # type: ignore[method-assign]
    monkeypatch.setattr(
        "app.wiring.response_interaction_worker.build_response_projection_coordinator",
        lambda **_: SimpleNamespace(response_service=service),
    )

    await worker.run_once()

    db.expire_all()
    assert service.get_response(response_id).status == "failed"
    assert db.get(Run, response_run_id).status == "failed"
    assert service.get_interaction(interaction_id).status == "failed"
    events = service.list_response_events(
        response_id,
        limit=100,
        offset=0,
        interaction_id=interaction_id,
    )
    assert [event.type for event in events] == ["RUN_ERROR"]


@pytest.mark.asyncio
async def test_worker_recovery_preserves_a_succeeded_response_terminal(
    db,
    ctx,
    monkeypatch,
):
    service = _response_service(db, ctx)
    response = service.create_response(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id="thread_recovery_success",
            input={"messages": [{"role": "user", "content": "hello"}]},
            metadata={"request_hash": "hash_recovery_success"},
        ),
        emit_initial_events=False,
    )
    interaction = service.create_interaction(
        interaction_id="interaction_recovery_success",
        parent_interaction_id=None,
        response=response,
        request_hash="hash_recovery_success",
    )
    response = service.mark_running(response)
    service.trace_writer.update_run_status(response.run_id, "running")
    response = service.complete_response(
        response=response,
        output_json={"text": "done"},
        output_event_type=None,
        completed_event_type=None,
    )
    service.trace_writer.update_run_status(response.run_id, "succeeded")
    interaction.status = "running"
    db.add(interaction)
    db.commit()

    monkeypatch.setattr(
        "app.wiring.response_interaction_worker.build_response_projection_coordinator",
        lambda **_: SimpleNamespace(response_service=service),
    )
    worker = GlobalResponseInteractionWorker(db_factory=lambda: db)

    await worker._terminalize_orphan(db, interaction, ctx)

    db.expire_all()
    recovered_response = service.get_response(response.id)
    recovered_interaction = service.get_interaction(interaction.interaction_id)
    run = db.get(Run, response.run_id)
    events = service.list_response_events(response.id, limit=100, offset=0)
    assert recovered_response.status == "succeeded"
    assert recovered_interaction is not None
    assert recovered_interaction.status == "succeeded"
    assert run is not None and run.status == "succeeded"
    assert [event.type for event in events] == ["RUN_FINISHED"]


@pytest.mark.asyncio
async def test_resume_orphan_checks_terminal_events_in_its_own_segment(
    db,
    ctx,
    monkeypatch,
):
    service = _response_service(db, ctx)
    response = service.create_response(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id="thread_segmented_orphan",
            input={"messages": [{"role": "user", "content": "hello"}]},
        ),
        emit_initial_events=False,
    )
    response = service.mark_running(response)
    response = service.complete_response(
        response=response,
        output_json={"text": "done"},
        output_event_type=None,
        completed_event_type=None,
    )
    service.create_interaction(
        interaction_id="interaction_orphan_parent",
        parent_interaction_id=None,
        response=response,
        request_hash="hash_orphan_parent",
    )
    parent_event = service.append_event(
        response=response,
        event_type="RUN_FINISHED",
        payload={"type": "RUN_FINISHED", "runId": "interaction_orphan_parent"},
        interaction_id="interaction_orphan_parent",
    )
    assert parent_event.interaction_id == "interaction_orphan_parent"
    child = service.create_interaction(
        interaction_id="interaction_orphan_child",
        parent_interaction_id="interaction_orphan_parent",
        response=response,
        request_hash="hash_orphan_child",
    )
    child.status = "running"
    db.add(child)
    db.commit()

    monkeypatch.setattr(
        "app.wiring.response_interaction_worker.build_response_projection_coordinator",
        lambda **_: SimpleNamespace(response_service=service),
    )
    worker = GlobalResponseInteractionWorker(db_factory=lambda: db)

    await worker._terminalize_orphan(db, child, ctx)

    child_events = service.list_response_events(
        response.id,
        limit=100,
        offset=0,
        interaction_id="interaction_orphan_child",
    )
    assert [event.type for event in child_events] == ["RUN_FINISHED"]


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_during_claim", [False, True])
async def test_worker_terminalizes_resume_failure_before_response_binding(
    db,
    ctx,
    monkeypatch,
    cancel_during_claim,
):
    service = _response_service(db, ctx)
    run = service.trace_writer.create_run("agent", kind="agent")
    service.trace_writer.update_run_status(run.id, "running")
    task_service = TaskService(db, ctx)
    task = task_service.create_task(
        task_type="agent.stream",
        status="running",
        agent_id="agent_resume_failure",
        thread_id="thread_resume_failure",
        run_id=run.id,
    )
    response = service.create_linked_response(
        run_id=run.id,
        thread_id="thread_resume_failure",
        task_id=task.id,
        agent_id="agent_resume_failure",
        emit_initial_events=False,
    )
    response = service.mark_running(response)
    parent = service.create_interaction(
        interaction_id="interaction_resume_failure_parent",
        parent_interaction_id=None,
        response=response,
        request_hash="hash_resume_failure_parent",
    )
    parent.status = "resuming"
    parent.resume_interaction_id = "interaction_resume_failure_child"
    db.add(parent)
    task_service.transition_task(task_id=task.id, status="waiting_approval")
    service.trace_writer.update_run_status(run.id, "waiting_approval")
    child, _ = service.claim_interaction(
        interaction_id="interaction_resume_failure_child",
        parent_interaction_id=parent.interaction_id,
        thread_id="thread_resume_failure",
        request_hash="hash_resume_failure_child",
        execution_json={
            "mode": "agent",
            "agent_id": "agent_resume_failure",
            "agent_inputs": {
                "_resume_execution": {
                    "run_id": run.id,
                    "task_id": task.id,
                    "thread_id": "thread_resume_failure",
                    "agent_id": "agent_resume_failure",
                    "response_id": response.id,
                }
            },
        },
        request_context_json={
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "user_id": ctx.user_id,
        },
    )

    class FailingAgentService:
        async def execute_agent_streaming(self, *args, **kwargs):
            raise RuntimeError("failure before response binding")

    monkeypatch.setattr(
        "app.wiring.response_interaction_worker.build_agent_service",
        lambda **_: FailingAgentService(),
    )
    worker = GlobalResponseInteractionWorker(db_factory=lambda: db)
    claimed = worker._claim_next(db)
    assert claimed is not None and claimed.id == child.id
    if cancel_during_claim:
        protocol = AgUiInteractionProtocolAdapter()
        started = protocol.text_started(message_id="msg_resume_failure")
        service.append_event(
            response=response,
            event_type=started.type,
            payload=started.payload,
            source=protocol.source,
            protocol_version=protocol.protocol_version,
            interaction_id=child.interaction_id,
        )
        service.cancel_response(response.id, emit_event=False)
        task_service.cancel_task(task_id=task.id)
        service.update_interaction_status(parent.interaction_id, "canceled")
        service.update_interaction_status(child.interaction_id, "canceled")
        db.commit()

    with pytest.raises(RuntimeError, match="before response binding"):
        await worker._execute(db, claimed)

    db.expire_all()
    terminal_status = "canceled" if cancel_during_claim else "failed"
    assert service.get_response(response.id).status == terminal_status
    assert task_service.get_task(task.id).status == terminal_status
    assert db.get(Run, run.id).status == terminal_status
    assert service.get_interaction(parent.interaction_id).status == terminal_status
    assert service.get_interaction(child.interaction_id).status == terminal_status
    child_events = service.list_response_events(
        response.id,
        limit=100,
        offset=0,
        interaction_id=child.interaction_id,
    )
    if cancel_during_claim:
        assert [event.type for event in child_events] == [
            "TEXT_MESSAGE_START",
            "TEXT_MESSAGE_END",
            "RUN_FINISHED",
        ]
        assert child_events[-1].payload_json["result"]["status"] == "canceled"
    else:
        assert [event.type for event in child_events] == ["RUN_ERROR"]


@pytest.mark.asyncio
async def test_worker_loop_recovers_after_a_transient_poll_failure(db):
    worker = GlobalResponseInteractionWorker(db_factory=lambda: db)
    recovered = asyncio.Event()
    attempts = 0

    async def run_once():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("database temporarily unavailable")
        recovered.set()
        return None

    worker.run_once = run_once  # type: ignore[method-assign]
    task = asyncio.create_task(worker.run_loop(poll_interval=0.01))
    await asyncio.wait_for(recovered.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert attempts >= 2


@pytest.mark.asyncio
async def test_worker_heartbeat_signals_when_the_lease_is_lost(db, ctx):
    service = _response_service(db, ctx)
    interaction, _ = service.claim_interaction(
        interaction_id="interaction_worker_lease_loss",
        parent_interaction_id=None,
        thread_id="thread_worker_lease_loss",
        request_hash="hash_worker_lease_loss",
        execution_json={"mode": "direct", "payload": {}},
        request_context_json={
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "user_id": ctx.user_id,
        },
    )
    bind = db.get_bind()
    worker = GlobalResponseInteractionWorker(
        db_factory=lambda: Session(bind=bind),
        worker_id="worker-original",
        heartbeat_interval_seconds=0.01,
    )
    claimed = worker._claim_next(db)
    assert claimed is not None
    claimed.lease_owner = "worker-replacement"
    db.add(claimed)
    db.commit()

    stop = asyncio.Event()
    lease_lost = asyncio.Event()
    await asyncio.wait_for(
        worker._heartbeat(
            interaction.id,
            interaction.interaction_id,
            claimed.attempt_count,
            stop,
            lease_lost,
        ),
        timeout=1,
    )

    assert lease_lost.is_set()
