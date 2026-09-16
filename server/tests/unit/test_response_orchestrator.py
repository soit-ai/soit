"""Unit tests for the response semantic-flow coordinator."""

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.agui.responses import AgUiInteractionProtocolAdapter
from app.adapters.storage.memory import InMemoryStoragePort
from app.kernel.ports.llm.interface import (
    ChatResponse,
    ChatStreamChunk,
    HostedArtifact,
    HostedToolCall,
    LLMPort,
)
from app.kernel.runtime.db.models.responses import Response, ResponseEvent
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunStepToolCall
from app.kernel.runtime.responses.orchestrator import (
    ResponseExecutionService,
    ResponseProjectionCoordinator,
    ThreadProjectionWriter,
)
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.schemas import ResponseCreateRequest
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.threads.service import ThreadService


class StubLLMPort(LLMPort):
    """Deterministic LLM stub."""

    def __init__(self):
        self.messages = []

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        self.messages.append(messages)
        return ChatResponse(
            text="orchestrated answer",
            tokens_prompt=3,
            tokens_completion=5,
            model=model,
            finish_reason="stop",
        )

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class FailingLLMPort(LLMPort):
    """LLM stub that fails after the user input has been stored."""

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        raise RuntimeError("provider timeout")

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class ChunkedLLMPort(StubLLMPort):
    """LLM stub that emits many tiny text chunks."""

    async def stream_chat(self, messages, model, **kwargs):
        self.messages.append(messages)
        for _ in range(300):
            yield ChatStreamChunk(delta="0123456789", model=model)
        yield ChatStreamChunk(done=True, tokens_prompt=3, tokens_completion=750, finish_reason="stop")


class CancelingLLMPort(StubLLMPort):
    """Cancel the authoritative response before returning the first chunk."""

    def __init__(self, cancel):
        super().__init__()
        self.cancel = cancel

    async def stream_chat(self, messages, model, **kwargs):
        await self.cancel()
        yield ChatStreamChunk(delta="must not be persisted", model=model)


class ReasoningLLMPort(StubLLMPort):
    """LLM stub that emits provider-visible reasoning before its answer."""

    def __init__(self):
        super().__init__()
        self.stream_kwargs = {}

    async def stream_chat(self, messages, model, **kwargs):
        self.messages.append(messages)
        self.stream_kwargs = kwargs
        yield ChatStreamChunk(reasoning_delta="Checking constraints. ", model=model)
        yield ChatStreamChunk(reasoning_delta="Evidence is sufficient.", model=model)
        yield ChatStreamChunk(delta="Final answer.", model=model)
        yield ChatStreamChunk(
            done=True,
            tokens_prompt=4,
            tokens_completion=6,
            finish_reason="stop",
        )


class HostedToolsLLMPort(StubLLMPort):
    """LLM stub that returns provider-executed hosted tools and files."""

    def __init__(self):
        super().__init__()
        self.stream_kwargs = {}

    async def stream_chat(self, messages, model, **kwargs):
        self.messages.append(messages)
        self.stream_kwargs = kwargs
        yield ChatStreamChunk(delta="Sourced answer.", model=model)
        yield ChatStreamChunk(
            done=True,
            model=model,
            tokens_prompt=8,
            tokens_completion=6,
            finish_reason="stop",
            hosted_tool_calls=[
                HostedToolCall(
                    id="ws_hosted_1",
                    name="openai.web_search",
                    status="completed",
                    arguments={"query": "SOIT"},
                    result={"sources": [{"url": "https://example.com/source"}]},
                ),
                HostedToolCall(
                    id="ci_hosted_1",
                    name="openai.code_interpreter",
                    status="completed",
                    arguments={"code": "print('SOIT')", "container_id": "container_1"},
                    result={"outputs": [{"type": "logs", "logs": "SOIT"}]},
                ),
            ],
            citations=[
                {
                    "type": "url",
                    "title": "Primary source",
                    "url": "https://example.com/source",
                    "source_uri": "https://example.com/source",
                }
            ],
            hosted_artifacts=[
                HostedArtifact(
                    container_id="container_1",
                    file_id="file_1",
                    filename="report.csv",
                    content=b"name,value\nSOIT,1\n",
                    mime="text/csv",
                )
            ],
        )


class FakeResponseRepository:
    def __init__(self, ctx):
        self.ctx = ctx
        self.responses = {}

    async def create(self, response):
        response.tenant_id = self.ctx.tenant_id
        response.workspace_id = self.ctx.workspace_id
        self.responses[response.id] = response
        return response

    async def update(self, response):
        self.responses[response.id] = response
        return response

    async def require(self, response_id):
        return self.responses[response_id]

    async def list_for_run(self, run_id):
        return [response for response in self.responses.values() if response.run_id == run_id]


class FakeResponseEventRepository:
    def __init__(self, ctx):
        self.ctx = ctx
        self.events = []

    async def create(self, event):
        event.tenant_id = self.ctx.tenant_id
        event.workspace_id = self.ctx.workspace_id
        self.events.append(event)
        return event

    async def next_sequence(self, response_id):
        return len([event for event in self.events if event.response_id == response_id]) + 1

    async def list_for_response(self, response_id, *, limit, offset, after_sequence=None):
        events = [event for event in self.events if event.response_id == response_id]
        if after_sequence is not None:
            events = [event for event in events if event.sequence > after_sequence]
        return events[offset : offset + limit]

    async def list_for_run(self, run_id):
        return [event for event in self.events if event.run_id == run_id]


def _service(db, ctx) -> ResponseService:
    return ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )


@pytest.mark.asyncio
async def test_response_event_sequence_locks_the_parent_response(ctx):
    class Result:
        def __init__(self, value):
            self.value = value

        def first(self):
            return self.value

    class RecordingDb:
        def __init__(self):
            self.statements = []

        async def exec(self, statement):
            self.statements.append(statement)
            sql = str(statement.compile(dialect=postgresql.dialect()))
            return Result("resp_locked" if "FOR UPDATE" in sql else 7)

    recording_db = RecordingDb()
    repository = ResponseEventRepository(recording_db, ctx)

    assert await repository.next_sequence("resp_locked") == 8
    assert any(
        "FOR UPDATE" in str(statement.compile(dialect=postgresql.dialect()))
        for statement in recording_db.statements
    )


@pytest.mark.asyncio
async def test_direct_interaction_commits_each_event_before_transport(tmp_path, ctx):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'direct-events.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    writer_db = AsyncSession(engine, expire_on_commit=False)
    try:
        coordinator = ResponseProjectionCoordinator(
            response_service=_service(writer_db, ctx),
            llm_port=StubLLMPort(),
            thread_service=None,
        )
        stream = coordinator.execute_interaction_stream(
            ResponseCreateRequest(
                model="model:openai:gpt-5.1",
                thread_id="thread_durable_direct",
                input={"messages": [{"id": "msg_direct", "role": "user", "content": "hello"}]},
                metadata={"request_hash": "hash_durable_direct"},
            ),
            interaction_id="interaction_durable_direct",
            parent_interaction_id=None,
            protocol=AgUiInteractionProtocolAdapter(),
        )

        first_item = await anext(stream)
        assert first_item["data"]["type"] == "RUN_STARTED"

        reader_db = AsyncSession(engine, expire_on_commit=False)
        try:
            reader_service = _service(reader_db, ctx)
            interaction = await reader_service.get_interaction("interaction_durable_direct")
            assert interaction is not None
            assert [
                event.type
                for event in await reader_service.list_response_events(
                    interaction.response_id,
                    limit=10,
                    offset=0,
                )
            ] == ["RUN_STARTED"]
        finally:
            await reader_db.close()

        await stream.aclose()
    finally:
        await writer_db.close()
        await engine.dispose()


def test_response_internal_components_expose_narrow_responsibilities():
    execution_service = ResponseExecutionService(StubLLMPort())
    thread_writer = ThreadProjectionWriter(thread_service=None)

    assert execution_service.build_usage(3, 5)["total_tokens"] == 8
    assert execution_service.build_completion_output("answer", "stop")["text"] == "answer"
    assert thread_writer.with_attachment_context("prompt", {"attachments": []}) == "prompt"


@pytest.mark.asyncio
async def test_response_service_accepts_repository_protocols(ctx):
    response_repo = FakeResponseRepository(ctx)
    event_repo = FakeResponseEventRepository(ctx)
    service = ResponseService(
        db=None,
        ctx=ctx,
        response_repo=response_repo,
        event_repo=event_repo,
        trace_writer=object(),
    )

    response = await service.create_linked_response(
        run_id="run_protocol",
        thread_id="thr_protocol",
        model="model:openai:gpt-5.1",
        input_json={"message": "hello"},
    )
    response = await service.mark_running(response)
    completed = await service.complete_response(
        response=response,
        output_json={"text": "done"},
        usage_json={"total_tokens": 2},
    )

    assert isinstance(response, Response)
    assert isinstance(event_repo.events[0], ResponseEvent)
    assert await response_repo.require(response.id) is completed
    assert completed.status == "succeeded"
    assert completed.provider == "openai"
    listed = await event_repo.list_for_response(response.id, limit=10, offset=0)
    assert [event.type for event in listed] == [
        "response.created",
        "response.input.added",
        "response.output_text.done",
        "response.succeeded",
    ]
    assert await event_repo.list_for_run("run_protocol") == event_repo.events


@pytest.mark.asyncio
async def test_response_public_readers_exclude_internal_events(async_db, ctx):
    service = _service(async_db, ctx)
    response = await service.create_response(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            input={"items": [{"type": "input_text", "text": "hello"}]},
        )
    )
    await service.append_event(
        response=response,
        event_type="response.internal.debug",
        payload={"secret": "operator-only"},
        visibility="internal",
    )

    assert [
        event.type
        for event in await service.list_response_events(response.id, limit=100, offset=0)
    ] == ["response.created", "response.input.added"]
    timeline = await service.get_run_timeline(response.run_id)
    assert [event.type for event in timeline["items"][0]["events"]] == [
        "response.created",
        "response.input.added",
    ]


@pytest.mark.asyncio
async def test_response_orchestrator_executes_and_records_events(async_db, ctx):
    response_service = _service(async_db, ctx)
    projection_coordinator = ResponseProjectionCoordinator(
        response_service=response_service,
        llm_port=StubLLMPort(),
        thread_service=None,
    )

    response = await projection_coordinator.execute(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            input={"items": [{"type": "input_text", "text": "hello"}]},
            metadata={"mode": "unit-test"},
        )
    )

    assert response.status == "succeeded"
    assert response.output_json["text"] == "orchestrated answer"
    assert response.usage_json["total_tokens"] == 8

    events = await response_service.list_response_events(response.id, limit=10, offset=0)
    assert [event.type for event in events] == [
        "response.created",
        "response.input.added",
        "response.output_text.done",
        "response.succeeded",
    ]

    run = await async_db.get(Run, response.run_id)
    assert run is not None
    assert run.status == "succeeded"


@pytest.mark.asyncio
async def test_response_orchestrator_persists_thread_message_attachments(async_db, ctx):
    response_service = _service(async_db, ctx)
    thread_service = ThreadService(async_db, ctx)
    thread = await thread_service.create_thread(agent_id=None, title="Attachment chat")
    llm_port = StubLLMPort()
    projection_coordinator = ResponseProjectionCoordinator(
        response_service=response_service,
        llm_port=llm_port,
        thread_service=thread_service,
    )

    response = await projection_coordinator.execute(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id=thread.id,
            input={
                "messages": [
                    {
                        "role": "user",
                        "content": "summarize this file",
                        "metadata": {
                            "attachments": [
                                {
                                    "id": "att_1",
                                    "name": "support-notes.txt",
                                    "type": "document",
                                    "size": 42,
                                }
                            ],
                            "_attachment_context": [
                                {
                                    "id": "att_1",
                                    "name": "support-notes.txt",
                                    "text": "refund policy",
                                }
                            ],
                        },
                    }
                ]
            },
        )
    )

    messages = await thread_service.thread_repo.list_messages(thread.id)
    assert response.status == "succeeded"
    assert messages[0].role == "user"
    assert messages[0].attachments_json == [
        {
            "id": "att_1",
            "name": "support-notes.txt",
            "type": "document",
            "size": 42,
        }
    ]
    assert messages[0].metadata_json["attachments"] == messages[0].attachments_json
    assert "_attachment_context" not in messages[0].metadata_json
    assert "refund policy" not in str(response.input_json)
    assert "Attached context:" in llm_port.messages[0][0].content
    assert "[support-notes.txt]" in llm_port.messages[0][0].content
    assert "refund policy" in llm_port.messages[0][0].content


@pytest.mark.asyncio
async def test_response_orchestrator_regenerates_from_existing_user_message_without_duplication(
    async_db,
    ctx,
):
    response_service = _service(async_db, ctx)
    thread_service = ThreadService(async_db, ctx)
    thread = await thread_service.create_thread(agent_id=None, title="Regenerate branch")
    user = await thread_service.append_message(
        thread_id=thread.id,
        role="user",
        content="Give me another answer",
    )
    first_assistant = await thread_service.append_message(
        thread_id=thread.id,
        role="assistant",
        content="First answer",
        parent_message_id=user.id,
    )
    llm_port = StubLLMPort()
    coordinator = ResponseProjectionCoordinator(
        response_service=response_service,
        llm_port=llm_port,
        thread_service=thread_service,
    )

    await coordinator.execute(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id=thread.id,
            input={
                "messages": [
                    {
                        "id": user.id,
                        "role": "user",
                        "content": user.content,
                        "metadata": {
                            "agui_message_id": user.id,
                            "parent_message_id": None,
                            "branch_id": "branch_regenerated",
                        },
                    }
                ]
            },
        )
    )

    messages = await thread_service.thread_repo.list_messages(thread.id)
    assert [message.id for message in messages if message.role == "user"] == [user.id]
    assert [message.content for message in llm_port.messages[0]] == [user.content]
    regenerated = messages[-1]
    assert regenerated.role == "assistant"
    assert regenerated.parent_message_id == user.id
    assert regenerated.id != first_assistant.id


@pytest.mark.asyncio
async def test_response_orchestrator_edits_a_user_turn_as_a_new_branch(async_db, ctx):
    response_service = _service(async_db, ctx)
    thread_service = ThreadService(async_db, ctx)
    thread = await thread_service.create_thread(agent_id=None, title="Edited branch")
    original_user = await thread_service.append_message(
        thread_id=thread.id,
        role="user",
        content="Original request",
    )
    await thread_service.append_message(
        thread_id=thread.id,
        role="assistant",
        content="Original answer",
        parent_message_id=original_user.id,
    )
    llm_port = StubLLMPort()
    coordinator = ResponseProjectionCoordinator(
        response_service=response_service,
        llm_port=llm_port,
        thread_service=thread_service,
    )

    await coordinator.execute(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id=thread.id,
            input={
                "messages": [
                    {
                        "id": "edited_client_message",
                        "role": "user",
                        "content": "Edited request",
                        "metadata": {
                            "agui_message_id": "edited_client_message",
                            "parent_message_id": None,
                            "branch_id": "branch_edited",
                        },
                    }
                ]
            },
        )
    )

    messages = await thread_service.thread_repo.list_messages(thread.id)
    edited_user = next(message for message in messages if message.content == "Edited request")
    edited_assistant = messages[-1]
    assert edited_user.parent_message_id is None
    assert edited_assistant.parent_message_id == edited_user.id
    assert [message.content for message in llm_port.messages[0]] == ["Edited request"]


@pytest.mark.asyncio
async def test_response_orchestrator_persists_failed_thread_message(async_db, ctx):
    response_service = _service(async_db, ctx)
    thread_service = ThreadService(async_db, ctx)
    thread = await thread_service.create_thread(agent_id=None, title="Retryable chat")
    projection_coordinator = ResponseProjectionCoordinator(
        response_service=response_service,
        llm_port=FailingLLMPort(),
        thread_service=thread_service,
    )

    with pytest.raises(RuntimeError, match="provider timeout"):
        await projection_coordinator.execute(
            ResponseCreateRequest(
                model="model:openai:gpt-5.1",
                thread_id=thread.id,
                input={"messages": [{"role": "user", "content": "please retry this"}]},
            )
        )

    messages = await thread_service.thread_repo.list_messages(thread.id)
    assert [(message.role, message.status) for message in messages] == [
        ("user", "completed"),
        ("assistant", "failed"),
    ]
    assert messages[1].parent_message_id == messages[0].id
    assert messages[1].message_type == "error"
    assert messages[1].error_code == "response_execution_failed"
    assert messages[1].error_message == "Response execution failed"
    assert "provider timeout" not in str(messages[1].metadata_json)


@pytest.mark.asyncio
async def test_response_service_terminalizes_bound_interaction_setup_failure(async_db, ctx):
    service = _service(async_db, ctx)
    response = await service.create_response(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id="thread_setup_failure",
            input={"messages": [{"role": "user", "content": "hello"}]},
        ),
        emit_initial_events=False,
    )
    response = await service.mark_running(response)
    await service.trace_writer.update_run_status(response.run_id, "running")
    await service.create_interaction(
        interaction_id="interaction_setup_failure",
        parent_interaction_id=None,
        response=response,
        request_hash="hash_setup_failure",
    )

    event = await service.fail_interaction_execution(
        "interaction_setup_failure",
        error_code="response_execution_failed",
        error_message="Response execution failed",
        terminal_event={
            "type": "RUN_ERROR",
            "code": "response_execution_failed",
            "message": "Response execution failed",
        },
        source="ag-ui",
        protocol_version="0.1.19",
    )

    assert event is not None and event.type == "RUN_ERROR"
    assert (await service.get_response(response.id)).status == "failed"
    assert (await service.get_interaction("interaction_setup_failure")).status == "failed"
    assert (await async_db.get(Run, response.run_id)).status == "failed"


async def _collect_stream(coordinator, request, *, interaction_id):
    return [
        item
        async for item in coordinator.execute_interaction_stream(
            request,
            interaction_id=interaction_id,
            parent_interaction_id=None,
            protocol=AgUiInteractionProtocolAdapter(),
        )
    ]


@pytest.mark.asyncio
async def test_interaction_stream_coalesces_tiny_text_chunks(async_db, ctx):
    response_service = _service(async_db, ctx)
    thread_service = ThreadService(async_db, ctx)
    thread = await thread_service.create_thread(agent_id=None, title="Chunk coalescing")
    coordinator = ResponseProjectionCoordinator(
        response_service=response_service,
        llm_port=ChunkedLLMPort(),
        thread_service=thread_service,
    )

    streamed = await _collect_stream(
        coordinator,
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id=thread.id,
            input={"messages": [{"role": "user", "content": "stream"}]},
            metadata={"interaction_id": "interaction_chunks", "request_hash": "hash_chunks"},
        ),
        interaction_id="interaction_chunks",
    )

    text_events = [item["data"] for item in streamed if item["data"]["type"] == "TEXT_MESSAGE_CONTENT"]
    assert "".join(event["delta"] for event in text_events) == "0123456789" * 300
    # Time-based latency flushing may add frames on a contended CI host. Require
    # at least a tenfold reduction so the test checks coalescing without relying
    # on wall-clock scheduling.
    assert len(text_events) <= 30


@pytest.mark.asyncio
async def test_interaction_stream_emits_and_persists_enabled_reasoning(async_db, ctx):
    response_service = _service(async_db, ctx)
    thread_service = ThreadService(async_db, ctx)
    thread = await thread_service.create_thread(agent_id=None, title="Reasoning stream")
    llm_port = ReasoningLLMPort()
    coordinator = ResponseProjectionCoordinator(
        response_service=response_service,
        llm_port=llm_port,
        thread_service=thread_service,
    )

    streamed = await _collect_stream(
        coordinator,
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id=thread.id,
            input={"messages": [{"role": "user", "content": "reason"}]},
            metadata={
                "interaction_id": "interaction_reasoning",
                "request_hash": "hash_reasoning",
                "show_reasoning": True,
                "reasoning_effort": "high",
            },
        ),
        interaction_id="interaction_reasoning",
    )

    event_types = [item["data"]["type"] for item in streamed]
    assert event_types.index("REASONING_START") < event_types.index("TEXT_MESSAGE_START")
    assert event_types.count("REASONING_MESSAGE_CONTENT") == 2
    assert llm_port.stream_kwargs["reasoning_effort"] == "high"
    messages = await thread_service.thread_repo.list_messages(thread.id)
    assert messages[-1].content == "Final answer."
    assert messages[-1].metadata_json["reasoning"] == (
        "Checking constraints. Evidence is sufficient."
    )
    interaction = await response_service.get_interaction("interaction_reasoning")
    assert interaction is not None
    response = await response_service.get_response(interaction.response_id)
    assert response.output_json["reasoning"] == (
        "Checking constraints. Evidence is sufficient."
    )


@pytest.mark.asyncio
async def test_interaction_stream_governs_hosted_tool_calls_sources_and_files(async_db, ctx):
    response_service = _service(async_db, ctx)
    thread_service = ThreadService(async_db, ctx)
    thread = await thread_service.create_thread(agent_id=None, title="Hosted tools")
    storage = InMemoryStoragePort()
    llm_port = HostedToolsLLMPort()
    coordinator = ResponseProjectionCoordinator(
        response_service=response_service,
        llm_port=llm_port,
        thread_service=thread_service,
        storage_port=storage,
    )
    requested_tools = [
        {"type": "web_search"},
        {
            "type": "code_interpreter",
            "container": {"type": "auto", "memory_limit": "4g"},
        },
    ]

    streamed = await _collect_stream(
        coordinator,
        ResponseCreateRequest(
            model="model:openai:gpt-5.5",
            thread_id=thread.id,
            input={"messages": [{"role": "user", "content": "Research and chart"}]},
            tools=requested_tools,
            metadata={
                "interaction_id": "interaction_hosted_tools",
                "request_hash": "hash_hosted_tools",
            },
        ),
        interaction_id="interaction_hosted_tools",
    )

    assert llm_port.stream_kwargs["hosted_tools"] == requested_tools
    custom_names = [
        item["data"].get("name")
        for item in streamed
        if item["data"]["type"] == "CUSTOM"
    ]
    assert "soit.source" in custom_names
    assert "soit.artifact" in custom_names
    assert "soit.tool_status" in custom_names
    assert [item["data"]["type"] for item in streamed].count("TOOL_CALL_START") == 2

    interaction = await response_service.get_interaction("interaction_hosted_tools")
    assert interaction is not None
    response = await response_service.get_response(interaction.response_id)
    records = (
        await async_db.exec(
            select(RunStepToolCall).where(RunStepToolCall.run_id == response.run_id)
        )
    ).all()
    assert [(record.tool_ref, record.status) for record in records] == [
        ("openai.web_search", "succeeded"),
        ("openai.code_interpreter", "succeeded"),
    ]
    artifact = (
        await async_db.exec(select(RunArtifact).where(RunArtifact.run_id == response.run_id))
    ).one()
    assert artifact.meta_json["name"] == "report.csv"
    assert await storage.get(artifact.storage_key) == b"name,value\nSOIT,1\n"
    artifact_event = next(
        item["data"]["value"]
        for item in streamed
        if item["data"].get("name") == "soit.artifact"
    )
    assert artifact_event["download_url"].endswith(
        f"/runs/{response.run_id}/artifacts/{artifact.id}/content"
    )
    message = (await thread_service.thread_repo.list_messages(thread.id))[-1]
    assert message.citations_json[0]["title"] == "Primary source"
    assert message.metadata_json["artifacts"][0]["id"] == artifact.id
    assert len(message.tool_calls_json) == 2


@pytest.mark.asyncio
async def test_interaction_stream_does_not_expose_reasoning_when_disabled(async_db, ctx):
    response_service = _service(async_db, ctx)
    thread_service = ThreadService(async_db, ctx)
    thread = await thread_service.create_thread(agent_id=None, title="Reasoning disabled")
    coordinator = ResponseProjectionCoordinator(
        response_service=response_service,
        llm_port=ReasoningLLMPort(),
        thread_service=thread_service,
    )

    streamed = await _collect_stream(
        coordinator,
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id=thread.id,
            input={"messages": [{"role": "user", "content": "answer only"}]},
            metadata={
                "interaction_id": "interaction_reasoning_disabled",
                "request_hash": "hash_reasoning_disabled",
                "show_reasoning": False,
            },
        ),
        interaction_id="interaction_reasoning_disabled",
    )

    assert not any(item["data"]["type"].startswith("REASONING") for item in streamed)
    message = (await thread_service.thread_repo.list_messages(thread.id))[-1]
    assert "reasoning" not in message.metadata_json
    interaction = await response_service.get_interaction("interaction_reasoning_disabled")
    assert interaction is not None
    response = await response_service.get_response(interaction.response_id)
    assert "reasoning" not in response.output_json


@pytest.mark.asyncio
async def test_interaction_stream_stops_without_success_after_explicit_cancellation(
    async_db, ctx
):
    response_service = _service(async_db, ctx)
    thread_service = ThreadService(async_db, ctx)
    thread = await thread_service.create_thread(agent_id=None, title="Canceled interaction")
    interaction_id = "interaction_cancel_during_stream"

    async def cancel_response() -> None:
        interaction = await response_service.get_interaction(interaction_id)
        assert interaction is not None
        await response_service.cancel_response(interaction.response_id, emit_event=False)

    coordinator = ResponseProjectionCoordinator(
        response_service=response_service,
        llm_port=CancelingLLMPort(cancel_response),
        thread_service=thread_service,
    )

    streamed = await _collect_stream(
        coordinator,
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id=thread.id,
            input={"messages": [{"role": "user", "content": "cancel"}]},
            metadata={"interaction_id": interaction_id, "request_hash": "hash_cancel"},
        ),
        interaction_id=interaction_id,
    )

    interaction = await response_service.get_interaction(interaction_id)
    assert interaction is not None
    response = await response_service.get_response(interaction.response_id)
    assert response.status == "canceled"
    assert interaction.status == "canceled"
    assert [item["data"]["type"] for item in streamed] == [
        "RUN_STARTED",
        "CUSTOM",
    ]
