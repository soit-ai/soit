"""Unit tests for the response semantic-flow coordinator."""

import pytest

from app.kernel.ports.llm.interface import ChatResponse, LLMPort
from app.kernel.responses.orchestrator import ResponseProjectionCoordinator
from app.kernel.responses.repository import ResponseEventRepository, ResponseRepository
from app.kernel.responses.schemas import ResponseCreateRequest
from app.kernel.responses.service import ResponseService
from app.kernel.trace.models import Run
from app.kernel.trace.writer import TraceWriter


class StubLLMPort(LLMPort):
    """Deterministic LLM stub."""

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
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
        runtime_core=None,
    )

    response = await projection_coordinator.execute(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            input={"items": [{"type": "input_text", "text": "hello"}]},
            metadata={"mode": "unit-test"},
        )
    )

    assert response.status == "completed"
    assert response.output_json["text"] == "orchestrated answer"
    assert response.usage_json["total_tokens"] == 8

    events = response_service.list_response_events(response.id, limit=10, offset=0)
    assert [event.type for event in events] == [
        "response.created",
        "response.input.added",
        "response.output_text.completed",
        "response.completed",
    ]

    run = db.get(Run, response.run_id)
    assert run is not None
    assert run.status == "succeeded"
