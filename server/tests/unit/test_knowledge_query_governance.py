"""A knowledge query passes governance refusals on instead of degrading."""

from __future__ import annotations

from typing import Any

import pytest

from app.kernel.commons.errors import (
    BudgetExhaustedError,
    KernelError,
    RateLimitExceededError,
)
from app.modules.knowledge.application.runtime_schemas import (
    KnowledgeCreate,
    QueryRequest,
)
from app.wiring.services import build_knowledge_runtime_service

pytestmark = pytest.mark.asyncio


class _Refusing:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def query(self, **kwargs: Any) -> list[Any]:
        del kwargs
        raise self.error


async def _service(async_db, ctx, error: Exception):
    service = build_knowledge_runtime_service(db=async_db, ctx=ctx)
    knowledge = await service.create_knowledge(KnowledgeCreate(name="governed-kb", type="document"))
    service.retrieval_service = _Refusing(error)
    fallback_calls: list[str] = []

    async def fallback(**kwargs: Any) -> list[Any]:
        fallback_calls.append(kwargs["query"])
        return []

    service._query_indexed_chunks_fallback = fallback  # type: ignore[method-assign]
    return service, knowledge.id, fallback_calls


@pytest.mark.parametrize(
    "refusal",
    [BudgetExhaustedError("Budget exhausted"), RateLimitExceededError("Rate limit exceeded", {"retry_after": 1})],
)
async def test_a_governance_refusal_reaches_the_caller(async_db, ctx, refusal: Exception) -> None:
    service, knowledge_id, fallback_calls = await _service(async_db, ctx, refusal)

    with pytest.raises(type(refusal)):
        await service.query(knowledge_id, QueryRequest(query="refund policy"))

    assert fallback_calls == []


async def test_a_failing_index_still_falls_back_to_keywords(async_db, ctx) -> None:
    service, knowledge_id, fallback_calls = await _service(
        async_db, ctx, KernelError("VECTOR_UNAVAILABLE", "The vector store is down")
    )

    with pytest.raises(KernelError, match="vector store is down"):
        # Nothing matched by keyword either, so the index's own error stands.
        await service.query(knowledge_id, QueryRequest(query="refund policy"))

    assert fallback_calls == ["refund policy"]
