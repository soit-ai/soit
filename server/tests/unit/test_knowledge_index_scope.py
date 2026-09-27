"""A query searches only indexes of the knowledge base it was allowed to run."""

from __future__ import annotations

from typing import Any

import pytest

from app.kernel.commons.errors import KernelError
from app.modules.knowledge.application.runtime_schemas import (
    KnowledgeCreate,
    QueryRequest,
)
from app.modules.knowledge.domain.models import KnowledgeIndex
from app.wiring.services import build_knowledge_runtime_service

pytestmark = pytest.mark.asyncio


class _Searches:
    """Retrieval that notes which index it was asked to search."""

    def __init__(self) -> None:
        self.indexes: list[str | None] = []

    async def query(self, **kwargs: Any) -> list[Any]:
        self.indexes.append(kwargs.get("index_id"))
        return []

    async def query_multiple_indexes(self, **kwargs: Any) -> list[Any]:
        self.indexes.extend(kwargs.get("index_ids") or [])
        return []


async def _two_bases(async_db, ctx):
    service = build_knowledge_runtime_service(db=async_db, ctx=ctx)
    mine = await service.create_knowledge(KnowledgeCreate(name="mine", type="document"))
    theirs = await service.create_knowledge(KnowledgeCreate(name="theirs", type="document", visibility="private"))
    their_index = KnowledgeIndex(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        knowledge_id=theirs.id,
        name="theirs-primary",
        is_primary=True,
        provider="memory",
        embedding_model_ref="model:test:embed",
        dimension=3,
        metric_type="cosine",
        status="ready",
    )
    async_db.add(their_index)
    await async_db.flush()
    return service, mine.id, their_index.id


@pytest.mark.parametrize(
    "request_fields",
    [
        lambda index: {"index_id": index},
        lambda index: {"strategy": "multi_index", "index_ids": [index]},
        lambda index: {"strategy": "hybrid", "index_id": index},
    ],
)
async def test_another_knowledge_bases_index_is_not_searched(async_db, ctx, request_fields) -> None:
    service, mine, their_index = await _two_bases(async_db, ctx)
    retrieval = _Searches()
    service.retrieval_service = retrieval

    with pytest.raises(KernelError) as refused:
        await service.query(mine, QueryRequest(query="salaries", **request_fields(their_index)))

    assert refused.value.code == "NOT_FOUND"
    assert retrieval.indexes == []


async def test_retrieval_itself_refuses_an_index_of_another_knowledge_base(async_db, ctx) -> None:
    service, mine, their_index = await _two_bases(async_db, ctx)

    assert service.retrieval_service is not None
    with pytest.raises(KernelError) as refused:
        await service.retrieval_service.query(
            knowledge_id=mine, query_text="salaries", top_k=3, index_id=their_index
        )

    assert refused.value.code == "NOT_FOUND"


async def test_an_index_that_no_longer_exists_is_left_to_retrieval(async_db, ctx) -> None:
    service, mine, _ = await _two_bases(async_db, ctx)
    retrieval = _Searches()
    service.retrieval_service = retrieval

    await service.query(mine, QueryRequest(query="refunds", index_id="idx_deleted"))

    # Not refused up front: retrieval meets it and the query falls back, as before.
    assert retrieval.indexes == ["idx_deleted"]
