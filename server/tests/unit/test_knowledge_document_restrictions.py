"""A restricted document is kept from members who may read its knowledge base but not it.

Readers of a restricted document are the workspace's Owners and Admins, the
base's creator and holders of a ``knowledge_document`` read grant. Everyone
else meets it nowhere: not in the document listing, not as a document, its
content, download, chunks or versions, and not in retrieval, by any strategy
or the keyword fallback. A restriction holds for every version of the
document and takes effect, or lifts, at once.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy import select

from app.kernel.commons.errors import ForbiddenError, KernelError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import (
    register_resource_grant_provider,
    reset_resource_grant_provider,
)
from app.kernel.runtime.db.models.runs import RunStep
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.knowledge.application.runtime_schemas import (
    DocumentUpload,
    KnowledgeCreate,
    QueryRequest,
)
from app.modules.knowledge.application.runtime_service import KnowledgeRuntimeService
from app.modules.knowledge.infra.repository import (
    ChunkRepository,
    DocumentRepository,
    IndexRepository,
    IngestTaskRepository,
    KnowledgeRepository,
)
from app.modules.knowledge.runtime.embedding import EmbeddingService
from app.modules.knowledge.runtime.index_builder import IndexBuilder
from app.modules.knowledge.runtime.pipeline import DocumentPipeline
from app.modules.knowledge.runtime.retrieval import RetrievalService
from tests.unit.test_knowledge_runtime_service import (
    EmptyRetrievalService,
    FailingRetrievalService,
    StubLLMPort,
    StubStoragePort,
    StubVectorPort,
)

OWNER = RequestContext(
    tenant_id="t_acl",
    workspace_id="w_acl",
    user_id="u_owner",
    tenant_role="Owner",
    workspace_role="Owner",
)
DEV = replace(OWNER, user_id="u_dev", tenant_role="Member", workspace_role="Dev")
ADMIN = replace(OWNER, user_id="u_admin", tenant_role="Member", workspace_role="Admin")


class _Stubs:
    def __init__(self) -> None:
        self.storage = StubStoragePort()
        self.vector = StubVectorPort()
        self.llm = StubLLMPort()


def _service(async_db, ctx: RequestContext, stubs: _Stubs) -> KnowledgeRuntimeService:
    embedding = EmbeddingService(stubs.llm)
    trace_writer = TraceWriter(async_db, ctx)
    index_builder = IndexBuilder(
        db=async_db, ctx=ctx, vector_port=stubs.vector, embedding_service=embedding, storage_port=stubs.storage
    )
    pipeline = DocumentPipeline(
        db=async_db,
        ctx=ctx,
        storage_port=stubs.storage,
        trace_writer=trace_writer,
        embedding_service=embedding,
        index_builder=index_builder,
    )
    retrieval = RetrievalService(
        db=async_db,
        ctx=ctx,
        vector_port=stubs.vector,
        llm_port=stubs.llm,
        embedding_service=embedding,
        storage_port=stubs.storage,
    )
    return KnowledgeRuntimeService(
        async_db,
        ctx,
        KnowledgeRepository(async_db, ctx),
        DocumentRepository(async_db, ctx),
        ChunkRepository(async_db, ctx),
        IndexRepository(async_db, ctx),
        IngestTaskRepository(async_db, ctx),
        pipeline,
        retrieval,
        index_builder=index_builder,
        storage_port=stubs.storage,
        vector_port=stubs.vector,
        trace_writer=trace_writer,
    )


class _Grants:
    """Read grants on knowledge documents, by (user, resource id)."""

    def __init__(self) -> None:
        self.granted: set[tuple[str, str]] = set()

    async def allows_resource_action(
        self, *, ctx: RequestContext, resource_type: str, resource_id: str, action: str, effective_action: str
    ) -> bool:
        del effective_action
        return resource_type == "knowledge_document" and action == "read" and (ctx.user_id, resource_id) in self.granted


@pytest.fixture
def grants():
    provider = _Grants()
    register_resource_grant_provider(provider)
    yield provider
    reset_resource_grant_provider()


async def _base(async_db, stubs: _Stubs) -> tuple[str, dict[str, Any]]:
    owner = _service(async_db, OWNER, stubs)
    knowledge = await owner.create_knowledge(
        KnowledgeCreate(name="handbook", type="document", default_embedding_model_ref="model:test:embedding")
    )
    docs = {}
    for doc_key, text in (
        ("travel", b"Refund policy for travel: claim within thirty days."),
        ("payroll", b"Refund policy for payroll: salary corrections are confidential."),
    ):
        docs[doc_key] = await owner.upload_document(
            knowledge.id, DocumentUpload(doc_key=doc_key, source_kind="upload", title=doc_key), file_content=text
        )
    await owner.set_document_restriction(knowledge.id, "payroll", True)
    return knowledge.id, docs


async def _cited(service: KnowledgeRuntimeService, knowledge_id: str, **request: Any) -> set[str]:
    response = await service.query(knowledge_id, QueryRequest(query="refund policy", top_k=5, **request))
    return {citation.doc_key for citation in response.citations}


@pytest.mark.asyncio
async def test_a_member_meets_the_restricted_document_nowhere(async_db, grants) -> None:
    del grants
    stubs = _Stubs()
    knowledge_id, docs = await _base(async_db, stubs)
    dev = _service(async_db, DEV, stubs)
    secret = docs["payroll"]

    assert await _cited(dev, knowledge_id) == {"travel"}
    assert {doc.doc_key for doc in await dev.list_documents(knowledge_id)} == {"travel"}
    for read in (
        lambda: dev.get_document(secret.id),
        lambda: dev.get_document_content(knowledge_id, secret.id),
        lambda: dev.download_document(knowledge_id, secret.id),
        lambda: dev.list_chunks(knowledge_id, secret.id),
        lambda: dev.list_document_versions(knowledge_id, "payroll"),
    ):
        with pytest.raises(KernelError) as missing:
            await read()
        assert missing.value.code == "NOT_FOUND"
    assert await dev.list_document_restrictions(knowledge_id) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", ["keyword", "hybrid"])
async def test_every_retrieval_strategy_leaves_it_out(async_db, grants, strategy) -> None:
    del grants
    stubs = _Stubs()
    knowledge_id, _ = await _base(async_db, stubs)
    dev = _service(async_db, DEV, stubs)
    knowledge = await dev.knowledge_repo.get_by_id(knowledge_id)
    knowledge.retrieval_json = {**(knowledge.retrieval_json or {}), "strategy": strategy}
    await async_db.commit()

    assert await _cited(dev, knowledge_id) == {"travel"}


@pytest.mark.asyncio
@pytest.mark.parametrize("stand_in", [FailingRetrievalService, EmptyRetrievalService])
async def test_the_keyword_fallback_leaves_it_out(async_db, grants, stand_in) -> None:
    del grants
    stubs = _Stubs()
    knowledge_id, _ = await _base(async_db, stubs)
    dev = _service(async_db, DEV, stubs)
    dev.retrieval_service = stand_in()

    assert await _cited(dev, knowledge_id) == {"travel"}


@pytest.mark.asyncio
async def test_the_retrieval_step_records_how_many_documents_were_left_out(async_db, grants) -> None:
    del grants
    stubs = _Stubs()
    knowledge_id, _ = await _base(async_db, stubs)
    dev = _service(async_db, DEV, stubs)

    await dev.query(knowledge_id, QueryRequest(query="refund policy", top_k=5))

    steps = list((await async_db.exec(select(RunStep).where(RunStep.step_type == "retrieval"))).scalars())
    assert steps[-1].metrics_json["restricted_documents_excluded"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("reader", [OWNER, ADMIN])
async def test_admins_and_the_creator_read_it(async_db, grants, reader) -> None:
    del grants
    stubs = _Stubs()
    knowledge_id, docs = await _base(async_db, stubs)
    service = _service(async_db, reader, stubs)

    assert await _cited(service, knowledge_id) == {"travel", "payroll"}
    assert (await service.get_document(docs["payroll"].id)).doc_key == "payroll"
    assert [row.doc_key for row in await service.list_document_restrictions(knowledge_id)] == ["payroll"]


@pytest.mark.asyncio
async def test_a_read_grant_opens_it_to_one_member(async_db, grants) -> None:
    stubs = _Stubs()
    knowledge_id, docs = await _base(async_db, stubs)
    grants.granted.add(("u_dev", f"{knowledge_id}:payroll"))
    dev = _service(async_db, DEV, stubs)

    assert await _cited(dev, knowledge_id) == {"travel", "payroll"}
    assert (await dev.get_document(docs["payroll"].id)).doc_key == "payroll"

    other = _service(async_db, replace(DEV, user_id="u_other"), stubs)
    assert await _cited(other, knowledge_id) == {"travel"}


@pytest.mark.asyncio
async def test_only_an_admin_or_the_creator_changes_a_restriction(async_db, grants) -> None:
    del grants
    stubs = _Stubs()
    knowledge_id, _ = await _base(async_db, stubs)
    dev = _service(async_db, DEV, stubs)

    with pytest.raises(ForbiddenError):
        await dev.set_document_restriction(knowledge_id, "payroll", False)
    with pytest.raises(ForbiddenError):
        await dev.set_document_restriction(knowledge_id, "travel", True)
    with pytest.raises(KernelError):
        await _service(async_db, OWNER, stubs).set_document_restriction(knowledge_id, "no-such-doc", True)


@pytest.mark.asyncio
async def test_lifting_and_restoring_a_restriction_take_effect_at_once(async_db, grants) -> None:
    del grants
    stubs = _Stubs()
    knowledge_id, _ = await _base(async_db, stubs)
    owner = _service(async_db, OWNER, stubs)
    dev = _service(async_db, DEV, stubs)

    await owner.set_document_restriction(knowledge_id, "payroll", False)
    assert await _cited(dev, knowledge_id) == {"travel", "payroll"}

    await owner.set_document_restriction(knowledge_id, "payroll", True)
    assert await _cited(dev, knowledge_id) == {"travel"}


@pytest.mark.asyncio
async def test_a_new_version_stays_restricted(async_db, grants) -> None:
    del grants
    stubs = _Stubs()
    knowledge_id, _ = await _base(async_db, stubs)
    owner = _service(async_db, OWNER, stubs)
    await owner.upload_document(
        knowledge_id,
        DocumentUpload(doc_key="payroll", source_kind="upload", title="payroll"),
        file_content=b"Refund policy for payroll, second edition.",
    )
    dev = _service(async_db, DEV, stubs)

    assert await _cited(dev, knowledge_id) == {"travel"}
    assert {doc.doc_key for doc in await dev.list_documents(knowledge_id)} == {"travel"}
