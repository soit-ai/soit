"""test_chat_service

Unit tests for ChatService.
"""

import pytest
from sqlmodel import SQLModel

from app.kernel.contracts.context import RequestContext
from app.kernel.trace.writer import TraceWriter
from app.kernel.ports.llm.interface import LLMPort, ChatResponse
from app.modules.chat.application.service import ChatService
from app.modules.chat.application.schemas import ChatCompletionRequest, ChatMessageInput
from app.modules.chat.infra.repository import ConversationRepository, MessageRepository


class StubLLMPort(LLMPort):
    """Stub LLM port for chat tests."""

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        return ChatResponse(
            text="Hello from stub",
            tokens_prompt=3,
            tokens_completion=5,
            model=model,
            finish_reason="stop",
        )

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError("embed not used in chat tests")

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError("rerank not used in chat tests")


@pytest.mark.asyncio
async def test_chat_completion_persists_messages_and_trace(db):
    """Chat completion writes messages and run trace."""
    from app.modules.chat.domain.models import Conversation, Message  # noqa: F401
    from app.kernel.trace.models import Run

    SQLModel.metadata.create_all(db.get_bind())

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )
    conversation_repo = ConversationRepository(db, ctx)
    message_repo = MessageRepository(db, ctx)
    trace_writer = TraceWriter(db, ctx)
    service = ChatService(
        db,
        ctx,
        conversation_repo,
        message_repo,
        llm_port=StubLLMPort(),
        trace_writer=trace_writer,
    )

    request = ChatCompletionRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
    )
    result = await service.create_completion(request)

    conversation_id = result["conversation"].id
    messages = service.get_messages(conversation_id, limit=10, offset=0)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"

    run = db.get(Run, result["run_id"])
    assert run is not None
    assert run.status == "succeeded"
