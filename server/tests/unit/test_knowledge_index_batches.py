"""Index builds and deletes must reach every chunk, not just the first page."""

import pytest

import app.modules.knowledge.infra.repository as repository_module
import app.modules.knowledge.runtime.index_builder as index_builder_module
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult
from app.modules.knowledge.domain.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIndex,
)
from app.modules.knowledge.infra.repository import ChunkRepository, DocumentRepository
from app.modules.knowledge.runtime.index_builder import IndexBuilder

BATCH = 3
CHUNKS = 8


class RecordingVectorPort(VectorPort):
    def __init__(self) -> None:
        self.inserted: list[str] = []
        self.deleted: list[str] = []

    async def ensure_collection(self, collection, dimension, metric_type, metadata_schema=None, **kwargs):
        return None

    async def query(self, collection, vector, top_k=10, filter=None, **kwargs):
        return VectorQueryResult(ids=[], scores=[])

    async def insert(self, collection, vectors, ids, metadata=None, **kwargs):
        assert len(ids) <= BATCH
        self.inserted.extend(ids)

    async def delete(self, collection, ids, **kwargs):
        assert len(ids) <= BATCH
        self.deleted.extend(ids)


class FixedEmbeddings:
    async def embed_batch(self, texts, model_ref, run_id=None, **kwargs):
        return [[0.1, 0.2, 0.3] for _ in texts]


@pytest.fixture
def small_batches(monkeypatch):
    monkeypatch.setattr(repository_module, "CHUNK_SCAN_BATCH_SIZE", BATCH)
    monkeypatch.setattr(index_builder_module, "CHUNK_SCAN_BATCH_SIZE", BATCH)


@pytest.fixture
def ctx() -> RequestContext:
    return RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
        tenant_role="Owner",
        workspace_role="Owner",
    )


async def _seed(async_db, ctx: RequestContext) -> KnowledgeIndex:
    for doc_no in range(2):
        for chunk_no in range(CHUNKS // 2):
            async_db.add(
                KnowledgeChunk(
                    tenant_id=ctx.tenant_id,
                    workspace_id=ctx.workspace_id,
                    knowledge_id="knowledge-1",
                    document_id=f"document-{doc_no}",
                    document_version=1,
                    chunk_no=chunk_no,
                    text_preview=f"chunk {doc_no}-{chunk_no}",
                )
            )
    # A chunk of another knowledge base must stay out of every scan.
    async_db.add(
        KnowledgeChunk(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            knowledge_id="knowledge-2",
            document_id="document-x",
            document_version=1,
            chunk_no=0,
            text_preview="other",
        )
    )
    index = KnowledgeIndex(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        knowledge_id="knowledge-1",
        name="primary",
        is_primary=True,
        provider="memory",
        embedding_model_ref="model:test:embedding",
        dimension=3,
        metric_type="cosine",
    )
    async_db.add(index)
    await async_db.commit()
    return index


@pytest.mark.asyncio
@pytest.mark.usefixtures("small_batches")
async def test_iter_batches_scans_every_chunk_while_rows_change(async_db, ctx):
    await _seed(async_db, ctx)
    repo = ChunkRepository(async_db, ctx)

    seen: list[str] = []
    async for batch in repo.iter_batches(knowledge_id="knowledge-1", index_status="pending"):
        assert len(batch) <= BATCH
        for chunk in batch:
            seen.append(chunk.id)
            chunk.index_status = "indexed"
        await async_db.commit()

    assert len(seen) == CHUNKS
    assert len(set(seen)) == CHUNKS
    assert len(await repo.list_all(document_id="document-0")) == CHUNKS // 2


@pytest.mark.asyncio
@pytest.mark.usefixtures("small_batches")
async def test_build_and_rebuild_index_cover_more_than_one_batch(async_db, ctx):
    index = await _seed(async_db, ctx)
    vectors = RecordingVectorPort()
    builder = IndexBuilder(
        db=async_db,
        ctx=ctx,
        vector_port=vectors,
        embedding_service=FixedEmbeddings(),  # type: ignore[arg-type]
    )

    await builder.build_index(index, incremental=True)

    assert len(vectors.inserted) == CHUNKS
    assert index.status == "ready"
    assert index.chunk_count == CHUNKS
    assert index.vector_count == CHUNKS
    assert index.doc_count == 2

    await builder.rebuild_index(index)

    assert len(vectors.deleted) == CHUNKS
    assert len(vectors.inserted) == 2 * CHUNKS
    assert index.chunk_count == CHUNKS
    assert index.build_version >= 1


@pytest.mark.asyncio
@pytest.mark.usefixtures("small_batches")
async def test_list_all_documents_reads_past_one_batch(async_db, ctx):
    for number in range(BATCH * 2 + 1):
        async_db.add(
            KnowledgeDocument(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                knowledge_id="knowledge-1",
                doc_key=f"doc-{number}",
                version=1,
                title=f"Doc {number}",
                source_kind="upload",
            )
        )
    await async_db.commit()

    documents = await DocumentRepository(async_db, ctx).list_all_by_knowledge("knowledge-1")

    assert len(documents) == BATCH * 2 + 1
