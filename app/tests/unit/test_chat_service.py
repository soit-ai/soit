"""test_chat_service

Unit tests for ChatService.
"""

import pytest
from sqlmodel import SQLModel

from app.kernel.contracts.context import RequestContext
from app.kernel.trace.writer import TraceWriter
from app.kernel.ports.llm.interface import LLMPort, ChatResponse
from app.modules.chat.application.service import ChatService
from app.modules.chat.application.config_provider import ChatConfigProvider
from app.modules.chat.application.schemas import ChatCompletionRequest, ChatMessageInput, ChatRagConfig
from app.modules.dataset.application.schemas import QueryResponse, QueryResult, QueryCitation, QueryRequest
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


class CountingLLMPort(LLMPort):
    """LLM port that tracks chat call count for idempotency tests."""

    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        self.calls += 1
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


class RecordingLLMPort(LLMPort):
    """LLM port that captures the last chat prompt."""

    def __init__(self) -> None:
        self.last_messages = []

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        self.last_messages = messages
        return ChatResponse(
            text="RAG answer",
            tokens_prompt=2,
            tokens_completion=4,
            model=model,
            finish_reason="stop",
        )

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError("embed not used in chat tests")

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError("rerank not used in chat tests")


class StubDatasetService:
    """Dataset service stub for RAG tests."""

    def __init__(self) -> None:
        self.last_query: QueryRequest | None = None

    async def query(self, dataset_id: str, query_request: QueryRequest) -> QueryResponse:
        self.last_query = query_request
        result = QueryResult(
            chunk_id="chunk_1",
            document_id="doc_1",
            score=0.9,
            text="Snippet text",
            snippets=["Snippet text"],
            metadata={
                "dataset_id": dataset_id,
                "doc_key": "doc_key",
                "title": "Doc Title",
                "source_uri": "https://example.com",
            },
        )
        citation = QueryCitation(
            chunk_id="chunk_1",
            document_id="doc_1",
            rank=1,
            score=0.9,
            dataset_id=dataset_id,
            doc_key="doc_key",
            title="Doc Title",
            source_uri="https://example.com",
            snippet="Snippet text",
        )
        return QueryResponse(results=[result], total=1, citations=[citation])


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
        tenant_role="Owner",
        workspace_role="Owner",
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
        config_provider=ChatConfigProvider(db, ctx),
    )

    request = ChatCompletionRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
    )
    result = await service.create_completion(request)

    conversation_id = result["conversation"].id
    messages = await service.get_messages(conversation_id, limit=10, offset=0)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"

    run = db.get(Run, result["run_id"])
    assert run is not None
    assert run.status == "succeeded"


@pytest.mark.asyncio
async def test_chat_completion_idempotency_reuses_response(db):
    """Idempotency key returns cached completion without re-calling LLM."""
    from app.modules.chat.domain.models import Conversation, Message  # noqa: F401

    SQLModel.metadata.create_all(db.get_bind())

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    conversation_repo = ConversationRepository(db, ctx)
    message_repo = MessageRepository(db, ctx)
    llm_port = CountingLLMPort()
    service = ChatService(
        db,
        ctx,
        conversation_repo,
        message_repo,
        llm_port=llm_port,
        config_provider=ChatConfigProvider(db, ctx),
    )

    request = ChatCompletionRequest(
        messages=[ChatMessageInput(role="user", content="Hello")],
    )

    first = await service.create_completion(request, idempotency_key="idem-1")
    second = await service.create_completion(request, idempotency_key="idem-1")

    assert first["conversation"].id == second["conversation"].id
    assert first["message"].id == second["message"].id
    assert first["run_id"] == second["run_id"]
    assert llm_port.calls == 1

    messages = await service.get_messages(first["conversation"].id, limit=10, offset=0)
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_chat_completion_injects_rag_context(db):
    """RAG config injects dataset context and persists citations."""
    from app.modules.chat.domain.models import Conversation, Message  # noqa: F401

    SQLModel.metadata.create_all(db.get_bind())

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    conversation_repo = ConversationRepository(db, ctx)
    message_repo = MessageRepository(db, ctx)
    llm_port = RecordingLLMPort()
    dataset_service = StubDatasetService()
    service = ChatService(
        db,
        ctx,
        conversation_repo,
        message_repo,
        llm_port=llm_port,
        dataset_service=dataset_service,
        config_provider=ChatConfigProvider(db, ctx),
    )

    request = ChatCompletionRequest(
        messages=[ChatMessageInput(role="user", content="What is in the dataset?")],
        rag=ChatRagConfig(dataset_ids=["ds_1"], top_k=1),
    )
    result = await service.create_completion(request)

    assert dataset_service.last_query is not None
    assert dataset_service.last_query.query == "What is in the dataset?"

    system_messages = [msg for msg in llm_port.last_messages if msg.role == "system"]
    assert any("dataset snippets" in msg.content for msg in system_messages)
    assert any("Snippet text" in msg.content for msg in system_messages)

    metadata = result["message"].metadata_json or {}
    assert metadata.get("rag_query") == "What is in the dataset?"
    assert metadata.get("rag_datasets") == ["ds_1"]
    assert metadata.get("citations")
