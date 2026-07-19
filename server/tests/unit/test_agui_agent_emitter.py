"""Tests for mapping authoritative Agent runtime events into persisted AG-UI events."""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from app.adapters.agui.agent import PersistentAgUiAgentEmitter
from app.api.v1.agent import dependencies as agent_dependencies
from app.kernel.commons.errors import ConflictError, KernelError
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter


@pytest.mark.asyncio
async def test_detached_agent_executor_emits_terminal_before_worker_session_closes(
    db,
    ctx,
    monkeypatch,
):
    class StubAgentApplicationService:
        async def execute_agent_streaming(self, *args, **kwargs):
            return {"status": "succeeded", "run_id": "run_worker", "output": "done"}

    monkeypatch.setattr(
        agent_dependencies,
        "build_agent_service",
        lambda *, db, ctx: StubAgentApplicationService(),
    )
    emitted = []

    async def emit(event, data):
        emitted.append((event, data))

    executor = agent_dependencies.get_agent_stream_executor(ctx=ctx, db=db)
    result = await executor("agent_worker", {"input": "hello"}, emit)

    assert result["run_id"] == "run_worker"
    assert emitted[-1] == ("agent.interaction.finished", {"result": result})


@pytest.mark.asyncio
async def test_agent_emitter_commits_events_before_transport(tmp_path, ctx):
    engine = create_engine(f"sqlite:///{tmp_path / 'agent-events.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as writer_db:
        writer_service = ResponseService(
            db=writer_db,
            ctx=ctx,
            response_repo=ResponseRepository(writer_db, ctx),
            event_repo=ResponseEventRepository(writer_db, ctx),
            trace_writer=TraceWriter(writer_db, ctx),
        )
        run = writer_service.trace_writer.create_run("agent", kind="agent")
        response = writer_service.create_linked_response(
            run_id=run.id,
            thread_id="thread_durable_agent",
            agent_id="agent_durable",
            emit_initial_events=False,
        )
        response = writer_service.mark_running(response)
        writer_db.commit()

        emitter = PersistentAgUiAgentEmitter(
            response_service=writer_service,
            interaction_id="interaction_durable_agent",
            parent_interaction_id=None,
            thread_id="thread_durable_agent",
        )
        await emitter.bind_response(response)

        with Session(engine) as reader_db:
            reader_service = ResponseService(
                db=reader_db,
                ctx=ctx,
                response_repo=ResponseRepository(reader_db, ctx),
                event_repo=ResponseEventRepository(reader_db, ctx),
                trace_writer=TraceWriter(reader_db, ctx),
            )
            interaction = reader_service.get_interaction("interaction_durable_agent")
            assert interaction is not None
            assert [
                event.type
                for event in reader_service.list_response_events(
                    response.id,
                    limit=10,
                    offset=0,
                )
            ] == ["RUN_STARTED", "CUSTOM"]


@pytest.mark.asyncio
async def test_agent_emitter_persists_tools_sources_usage_and_governance(db, ctx):
    service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )
    response = service.create_linked_response(
        run_id="run_agent_agui",
        thread_id="thread_agent_agui",
        task_id="task_agent_agui",
        agent_id="agent_agui",
        model="model:openai:gpt-5.1",
        emit_initial_events=False,
    )
    response = service.mark_running(response)
    queue: asyncio.Queue = asyncio.Queue()
    emitter = PersistentAgUiAgentEmitter(
        response_service=service,
        interaction_id="interaction_agent_agui",
        parent_interaction_id=None,
        thread_id="thread_agent_agui",
        queue=queue,
    )

    await emitter.bind_response(response)
    await emitter("agent.plan.started", {"iteration": 1})
    await emitter(
        "agent.tool.started",
        {
            "tool_ref": "tool:function:time_now",
            "tool_call_id": "call_1",
            "arguments": {"timezone": "UTC"},
            "tool_type": "builtin",
        },
    )
    await emitter(
        "agent.tool.succeeded",
        {
            "tool_ref": "tool:function:time_now",
            "tool_call_id": "call_1",
            "result": {"result": "12:00"},
            "success": True,
            "tool_type": "builtin",
        },
    )
    await emitter("agent.response.succeeded", {"output": "It is 12:00."})
    await emitter.complete(
        {
            "run_id": "run_agent_agui",
            "response_id": response.id,
            "task_id": "task_agent_agui",
            "thread_id": "thread_agent_agui",
            "model": "model:openai:gpt-5.1",
            "tokens_prompt": 20,
            "tokens_completion": 6,
            "cost_total": 0.01,
            "budget_exceeded": False,
            "citations": [
                {
                    "chunk_id": "chunk_1",
                    "title": "Runbook",
                    "snippet": "Use UTC for operational timestamps.",
                }
            ],
            "artifacts": [
                {
                    "id": "art_report",
                    "type": "file",
                    "name": "report.csv",
                    "mime": "text/csv",
                    "size_bytes": 128,
                    "sha256": "abc123",
                    "download_url": "/api/v1/runs/run_agent_agui/artifacts/art_report/content",
                }
            ],
        }
    )

    events = service.list_response_events(response.id, limit=100, offset=0)
    event_types = [event.type for event in events]
    assert event_types[0] == "RUN_STARTED"
    assert "ACTIVITY_SNAPSHOT" in event_types
    assert "TOOL_CALL_START" in event_types
    assert "TOOL_CALL_ARGS" in event_types
    assert "TOOL_CALL_END" in event_types
    assert "TOOL_CALL_RESULT" in event_types
    assert "TEXT_MESSAGE_CONTENT" in event_types
    assert event_types[-1] == "RUN_FINISHED"
    custom_names = [
        event.payload_json["name"]
        for event in events
        if event.type == "CUSTOM"
    ]
    assert "soit.resources" in custom_names
    assert "soit.tool_status" in custom_names
    assert "soit.source" in custom_names
    assert "soit.artifact" in custom_names
    assert "soit.usage" in custom_names
    assert "soit.governance" in custom_names
    assert all(event.visibility == "user" for event in events)
    artifact_event = next(
        event
        for event in events
        if event.type == "CUSTOM" and event.payload_json.get("name") == "soit.artifact"
    )
    assert artifact_event.payload_json["value"]["download_url"].endswith(
        "/artifacts/art_report/content"
    )


@pytest.mark.asyncio
async def test_agent_emitter_maps_reasoning_before_answer_text(db, ctx):
    service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )
    response = service.create_linked_response(
        run_id="run_agent_reasoning",
        thread_id="thread_agent_reasoning",
        agent_id="agent_reasoning",
        emit_initial_events=False,
    )
    response = service.mark_running(response)
    emitter = PersistentAgUiAgentEmitter(
        response_service=service,
        interaction_id="interaction_agent_reasoning",
        parent_interaction_id=None,
        thread_id="thread_agent_reasoning",
    )

    await emitter.bind_response(response)
    await emitter(
        "agent.reasoning.completed",
        {"iteration": 1, "content": "Checked the evidence."},
    )
    await emitter("agent.response.succeeded", {"output": "Done."})
    await emitter.complete({"run_id": "run_agent_reasoning", "output": "Done."})

    events = service.list_response_events(response.id, limit=100, offset=0)
    event_types = [event.type for event in events]
    assert event_types.index("REASONING_START") < event_types.index("TEXT_MESSAGE_START")
    reasoning_content = next(
        event
        for event in events
        if event.type == "REASONING_MESSAGE_CONTENT"
    )
    assert reasoning_content.payload_json["delta"] == "Checked the evidence."


@pytest.mark.asyncio
async def test_agent_emitter_maps_explicit_cancellation_to_cancel_terminal(db, ctx):
    service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )
    run = service.trace_writer.create_run("agent", kind="agent")
    response = service.create_linked_response(
        run_id=run.id,
        thread_id="thread_agent_cancel",
        task_id="task_agent_cancel",
        agent_id="agent_cancel",
        emit_initial_events=False,
    )
    response = service.mark_running(response)
    emitter = PersistentAgUiAgentEmitter(
        response_service=service,
        interaction_id="interaction_agent_cancel",
        parent_interaction_id=None,
        thread_id="thread_agent_cancel",
    )
    await emitter.bind_response(response)
    await emitter("agent.response.succeeded", {"output": "Partial answer"})
    service.cancel_response(response.id, emit_event=False)

    await emitter.fail(
        KernelError("AGENT_RUN_CANCELED", "Agent execution was explicitly canceled")
    )

    events = service.list_response_events(response.id, limit=100, offset=0)
    assert [event.type for event in events][-1] == "RUN_FINISHED"
    assert [event.type for event in events][-2] == "TEXT_MESSAGE_END"
    assert events[-1].payload_json["result"]["status"] == "canceled"
    assert "RUN_ERROR" not in [event.type for event in events]
    assert service.get_interaction("interaction_agent_cancel").status == "canceled"


@pytest.mark.asyncio
async def test_agent_emitter_failure_emits_visible_message_before_single_terminal(db, ctx):
    service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )
    response = service.create_linked_response(
        run_id="run_agent_failure",
        thread_id="thread_agent_failure",
        agent_id="agent_failure",
        emit_initial_events=False,
    )
    response = service.mark_running(response)
    emitter = PersistentAgUiAgentEmitter(
        response_service=service,
        interaction_id="interaction_agent_failure",
        parent_interaction_id=None,
        thread_id="thread_agent_failure",
    )
    await emitter.bind_response(response)

    await emitter.fail(RuntimeError("provider leaked secret"))
    await emitter.fail(RuntimeError("duplicate failure"))

    events = service.list_response_events(response.id, limit=100, offset=0)
    event_types = [event.type for event in events]
    assert event_types[-4:] == [
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "RUN_ERROR",
    ]
    assert event_types.count("RUN_ERROR") == 1
    content_event = next(
        event for event in events if event.type == "TEXT_MESSAGE_CONTENT"
    )
    assert content_event.payload_json["delta"] == "Agent execution failed"
    assert "provider leaked secret" not in str(content_event.payload_json)
    assert service.get_interaction("interaction_agent_failure").status == "failed"


@pytest.mark.asyncio
async def test_agent_emitter_rejects_events_after_execution_lease_is_lost(db, ctx):
    service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )
    response = service.create_linked_response(
        run_id="run_agent_fenced",
        thread_id="thread_agent_fenced",
        agent_id="agent_fenced",
        emit_initial_events=False,
    )
    response = service.mark_running(response)
    lease_active = True

    def assert_lease() -> None:
        if not lease_active:
            raise ConflictError("Interaction execution lease was lost")

    emitter = PersistentAgUiAgentEmitter(
        response_service=service,
        interaction_id="interaction_agent_fenced",
        parent_interaction_id=None,
        thread_id="thread_agent_fenced",
        lease_guard=assert_lease,
    )
    await emitter.bind_response(response)
    lease_active = False

    with pytest.raises(ConflictError, match="lease was lost"):
        await emitter.complete({"output": "must not be persisted"})

    events = service.list_response_events(response.id, limit=100, offset=0)
    assert "RUN_FINISHED" not in [event.type for event in events]
    assert service.get_interaction("interaction_agent_fenced").status == "running"
