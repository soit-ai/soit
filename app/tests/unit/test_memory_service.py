"""test_memory_service

Unit tests for MemoryService.
"""

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import LLMPort, EmbeddingResponse
from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult
from app.modules.memory.application.service import MemoryService
from app.modules.memory.application.schemas import MemoryCreate, MemoryQuery
from app.modules.memory.domain.models import MemoryItem
from app.modules.memory.infra.repository import MemoryRepository


class StubLLMPort(LLMPort):
    """Stub LLM port for memory tests."""

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        raise NotImplementedError("chat not used in memory tests")

    async def embed(self, texts, model, **kwargs):
        return EmbeddingResponse(embeddings=[[0.1, 0.2, 0.3]], tokens_used=3, model=model)

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError("rerank not used in memory tests")


class StubVectorPort(VectorPort):
    """Stub vector port for memory tests."""

    def __init__(self, ids, scores):
        self._ids = ids
        self._scores = scores

    async def query(self, collection, vector, top_k=10, filter=None, **kwargs):
        return VectorQueryResult(ids=self._ids, scores=self._scores)

    async def insert(self, collection, vectors, ids, metadata=None, **kwargs):
        return None

    async def delete(self, collection, ids, **kwargs):
        return None


@pytest.mark.asyncio
async def test_memory_create_and_list(db, ctx):
    """Memory creation persists and lists items."""
    repo = MemoryRepository(db, ctx)
    service = MemoryService(db, ctx, repo)

    created = await service.create_memory(
        MemoryCreate(content={"text": "hello"}, memory_type="long")
    )
    assert created.id

    items = await service.list_memories(limit=10, offset=0)
    assert len(items) == 1
    assert items[0].id == created.id


@pytest.mark.asyncio
async def test_memory_query_requires_ports(db, ctx):
    """Memory query needs LLM and vector ports."""
    repo = MemoryRepository(db, ctx)
    service = MemoryService(db, ctx, repo)

    with pytest.raises(ValidationError):
        await service.query_memory(MemoryQuery(query="hello"))


@pytest.mark.asyncio
async def test_memory_query_filters(db, ctx):
    """Memory query filters by user and type."""
    repo = MemoryRepository(db, ctx)
    item1 = repo.create(
        MemoryItem(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            memory_type="long",
            content={"text": "alpha"},
        )
    )
    item2 = repo.create(
        MemoryItem(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id="other-user",
            memory_type="short",
            content={"text": "beta"},
        )
    )

    service = MemoryService(
        db,
        ctx,
        repo,
        llm_port=StubLLMPort(),
        vector_port=StubVectorPort(ids=[item1.id, item2.id], scores=[0.9, 0.1]),
    )

    results = await service.query_memory(
        MemoryQuery(query="alpha", user_id=ctx.user_id, memory_type="long", top_k=5)
    )
    assert len(results) == 1
    assert results[0].memory.id == item1.id
