"""Unit tests for the response semantic-flow coordinator."""

import pytest

from app.kernel.ports.llm.interface import ChatResponse, LLMPort
from app.kernel.runtime.db.models.responses import Response, ResponseEvent
from app.kernel.runtime.db.models.runs import Run
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


class FakeResponseRepository:
    def __init__(self, ctx):
        self.ctx = ctx
        self.responses = {}

    def create(self, response):
        response.tenant_id = self.ctx.tenant_id
        response.workspace_id = self.ctx.workspace_id
        self.responses[response.id] = response
        return response

    def update(self, response):
        self.responses[response.id] = response
        return response

    def require(self, response_id):
        return self.responses[response_id]

    def list_for_run(self, run_id):
        return [response for response in self.responses.values() if response.run_id == run_id]


class FakeResponseEventRepository:
    def __init__(self, ctx):
        self.ctx = ctx
        self.events = []

    def create(self, event):
        event.tenant_id = self.ctx.tenant_id
        event.workspace_id = self.ctx.workspace_id
        self.events.append(event)
        return event

    def next_sequence(self, response_id):
        return len([event for event in self.events if event.response_id == response_id]) + 1

    def list_for_response(self, response_id, *, limit, offset):
        return [event for event in self.events if event.response_id == response_id][offset : offset + limit]

    def list_for_run(self, run_id):
        return [event for event in self.events if event.run_id == run_id]


def test_response_internal_components_expose_narrow_responsibilities():
    execution_service = ResponseExecutionService(StubLLMPort())
    thread_writer = ThreadProjectionWriter(thread_service=None)

    assert execution_service.build_usage(3, 5)["total_tokens"] == 8
    assert execution_service.build_completion_output("answer", "stop")["text"] == "answer"
    assert thread_writer.with_attachment_context("prompt", {"attachments": []}) == "prompt"


def test_response_service_accepts_repository_protocols(ctx):
    response_repo = FakeResponseRepository(ctx)
    event_repo = FakeResponseEventRepository(ctx)
    service = ResponseService(
        db=None,
        ctx=ctx,
        response_repo=response_repo,
        event_repo=event_repo,
        trace_writer=object(),
    )

    response = service.create_linked_response(
        run_id="run_protocol",
        thread_id="thr_protocol",
        model="model:openai:gpt-5.1",
        input_json={"message": "hello"},
    )
    response = service.mark_running(response)
    completed = service.complete_response(
        response=response,
        output_json={"text": "done"},
        usage_json={"total_tokens": 2},
    )

    assert isinstance(response, Response)
    assert isinstance(event_repo.events[0], ResponseEvent)
    assert response_repo.require(response.id) is completed
    assert completed.status == "succeeded"
    assert completed.provider == "openai"
    assert [event.type for event in event_repo.list_for_response(response.id, limit=10, offset=0)] == [
        "response.created",
        "response.input.added",
        "response.output_text.done",
        "response.succeeded",
    ]
    assert event_repo.list_for_run("run_protocol") == event_repo.events


@pytest.mark.asyncio
async def test_response_orchestrator_executes_and_records_events(db, ctx):
    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )
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

    events = response_service.list_response_events(response.id, limit=10, offset=0)
    assert [event.type for event in events] == [
        "response.created",
        "response.input.added",
        "response.output_text.done",
        "response.succeeded",
    ]

    run = db.get(Run, response.run_id)
    assert run is not None
    assert run.status == "succeeded"


@pytest.mark.asyncio
async def test_response_orchestrator_persists_thread_message_attachments(db, ctx):
    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )
    thread_service = ThreadService(db, ctx)
    thread = thread_service.create_thread(agent_id=None, title="Attachment chat")
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
                                    "content": [{"type": "text", "text": "refund policy"}],
                                }
                            ]
                        },
                    }
                ]
            },
        )
    )

    messages = thread_service.thread_repo.list_messages(thread.id)
    assert response.status == "succeeded"
    assert messages[0].role == "user"
    assert messages[0].attachments_json == [
        {
            "id": "att_1",
            "name": "support-notes.txt",
            "type": "document",
            "size": 42,
            "content": [{"type": "text", "text": "refund policy"}],
        }
    ]
    assert messages[0].metadata_json["attachments"] == messages[0].attachments_json
    assert "Attached context:" in llm_port.messages[0][0].content
    assert "[support-notes.txt]" in llm_port.messages[0][0].content
    assert "refund policy" in llm_port.messages[0][0].content


@pytest.mark.asyncio
async def test_response_orchestrator_persists_failed_thread_message(db, ctx):
    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )
    thread_service = ThreadService(db, ctx)
    thread = thread_service.create_thread(agent_id=None, title="Retryable chat")
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

    messages = thread_service.thread_repo.list_messages(thread.id)
    assert [(message.role, message.status) for message in messages] == [
        ("user", "completed"),
        ("assistant", "failed"),
    ]
    assert messages[1].parent_message_id == messages[0].id
    assert messages[1].message_type == "error"
    assert messages[1].error_code == "response_execution_failed"
    assert messages[1].error_message == "provider timeout"
