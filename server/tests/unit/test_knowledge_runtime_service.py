"""test_knowledge_runtime_service

Unit tests for KnowledgeRuntimeService.
"""

import pytest
from sqlalchemy import select
from sqlmodel import SQLModel

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import EmbeddingResponse, LLMPort, RerankResponse
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult
from app.kernel.runtime.db.models.runs import Run, RunStep
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.knowledge.application.runtime_schemas import (
    DocumentUpload,
    KnowledgeCreate,
    QueryRequest,
)
from app.modules.knowledge.application.runtime_service import KnowledgeRuntimeService
from app.modules.knowledge.application.service import KnowledgeService
from app.modules.knowledge.infra.repository import (
    ChunkRepository,
    DocumentRepository,
    IndexRepository,
    IngestTaskRepository,
    KnowledgeRepository,
)
from app.modules.knowledge.runtime.embedding import EmbeddingService
from app.modules.knowledge.runtime.index_builder import IndexBuilder
from app.modules.knowledge.runtime.ingest_worker import KnowledgeIngestWorker
from app.modules.knowledge.runtime.pipeline import DocumentPipeline
from app.modules.knowledge.runtime.retrieval import RetrievalService


class StubStoragePort(StoragePort):
    """In-memory storage stub."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.streamed_keys: list[str] = []

    async def put(self, key, data, content_type=None, metadata=None, **kwargs):
        self.objects[key] = data
        return key

    async def get(self, key, **kwargs):
        return self.objects[key]

    async def delete(self, key, **kwargs):
        self.objects.pop(key, None)

    async def exists(self, key, **kwargs):
        return key in self.objects

    async def open_writer(self, key, content_type=None, metadata=None, **kwargs):
        self.streamed_keys.append(key)
        return StubStorageWriter(self, key)


class StubHttpFetchPort:
    """Governed fetch stub used by crawler tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[RequestContext, str, int]] = []

    async def fetch(self, ctx, url, *, max_bytes):
        self.calls.append((ctx, url, max_bytes))
        return type(
            "FetchedResource",
            (),
            {
                "content": b"<html>ok</html>",
                "content_type": "text/html",
                "final_url": url,
            },
        )()


@pytest.mark.asyncio
async def test_crawler_fetch_uses_governed_http_port(ctx) -> None:
    fetch_port = StubHttpFetchPort()
    service = KnowledgeRuntimeService(
        db=None,
        ctx=ctx,
        knowledge_repo=None,
        document_repo=None,
        chunk_repo=None,
        index_repo=None,
        http_fetch_port=fetch_port,
    )

    content, content_type, filename = await service._fetch_source_content(
        "https://docs.example.com/guide.html"
    )

    assert content == b"<html>ok</html>"
    assert content_type == "text/html"
    assert filename == "guide.html"
    assert fetch_port.calls == [
        (ctx, "https://docs.example.com/guide.html", 5 * 1024 * 1024)
    ]


def test_knowledge_service_forwards_governed_http_port(ctx) -> None:
    fetch_port = StubHttpFetchPort()

    service = KnowledgeService(
        db=None,
        ctx=ctx,
        knowledge_repo=None,
        document_repo=None,
        chunk_repo=None,
        index_repo=None,
        http_fetch_port=fetch_port,
    )

    assert service.runtime_service.http_fetch_port is fetch_port


class FailingGetStoragePort(StubStoragePort):
    """Storage stub that fails reads until disabled."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_reads = True

    async def get(self, key, **kwargs):
        if self.fail_reads:
            raise RuntimeError("storage read unavailable")
        return await super().get(key, **kwargs)


class StubStorageWriter:
    """In-memory streaming storage writer."""

    def __init__(self, storage: StubStoragePort, key: str) -> None:
        self.storage = storage
        self.key = key
        self.chunks: list[bytes] = []

    async def write(self, data: bytes) -> int:
        self.chunks.append(data)
        return len(data)

    async def close(self) -> None:
        self.storage.objects[self.key] = b"".join(self.chunks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()


class AsyncBytesStream:
    """Async byte stream used to verify upload streaming."""

    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.index = 0

    async def read(self, size: int = -1) -> bytes:
        if self.index >= len(self.chunks):
            return b""
        chunk = self.chunks[self.index]
        self.index += 1
        return chunk


class StubVectorPort(VectorPort):
    """In-memory vector store stub."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, object]]] = {}

    async def ensure_collection(
        self,
        collection,
        dimension,
        metric_type,
        metadata_schema=None,
        *,
        index_ref=None,
        run_id=None,
    ):
        self.collections.setdefault(collection, {})

    async def query(self, collection, vector, top_k=10, filter=None, **kwargs):
        records = self.collections.get(collection, {})
        scores = []
        for chunk_id, payload in records.items():
            stored_vector = payload["vector"]
            score = sum((q * v) for q, v in zip(vector, stored_vector, strict=False))
            scores.append((chunk_id, score))

        scores.sort(key=lambda item: item[1], reverse=True)
        ids = [item[0] for item in scores[:top_k]]
        values = [item[1] for item in scores[:top_k]]
        return VectorQueryResult(ids=ids, scores=values)

    async def insert(self, collection, vectors, ids, metadata=None, **kwargs):
        store = self.collections.setdefault(collection, {})
        meta_list = metadata or [{} for _ in ids]
        for idx, vector, meta in zip(ids, vectors, meta_list, strict=False):
            store[idx] = {
                "vector": vector,
                "metadata": meta,
            }

    async def delete(self, collection, ids, **kwargs):
        store = self.collections.get(collection, {})
        for idx in ids:
            store.pop(idx, None)


class StubLLMPort(LLMPort):
    """Stub LLM port for embeddings and rerank."""

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        raise NotImplementedError("chat not used in knowledge tests")

    async def embed(self, texts, model, **kwargs):
        embeddings = [self._embed_text(text) for text in texts]
        return EmbeddingResponse(embeddings=embeddings, tokens_used=0, model=model)

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        results = [
            {"index": idx, "document": doc, "score": float(len(doc))}
            for idx, doc in enumerate(documents)
        ]
        results.sort(key=lambda item: item["score"], reverse=True)
        if top_n:
            results = results[:top_n]
        return RerankResponse(results=results, tokens_used=0, model=model)

    def _embed_text(self, text: str) -> list[float]:
        return [
            float(len(text)),
            float(sum(bytearray(text.encode("utf-8"))) % 997),
            float(text.count(" ")),
        ]


class FailingRetrievalService:
    """Retrieval stub that simulates an unavailable vector backend."""

    async def query(self, **kwargs):
        raise RuntimeError("vector backend unavailable")

    async def query_multiple_indexes(self, **kwargs):
        raise RuntimeError("vector backend unavailable")

    async def query_keyword(self, **kwargs):
        raise RuntimeError("vector backend unavailable")

    async def query_hybrid(self, **kwargs):
        raise RuntimeError("vector backend unavailable")


class EmptyRetrievalService:
    """Retrieval stub that returns no vector matches."""

    async def query(self, **kwargs):
        return []

    async def query_multiple_indexes(self, **kwargs):
        return []

    async def query_keyword(self, **kwargs):
        return []

    async def query_hybrid(self, **kwargs):
        return []


def build_knowledge_test_service(db, ctx, storage_port=None):
    """Build a fully wired KnowledgeRuntimeService for tests."""
    knowledge_repo = KnowledgeRepository(db, ctx)
    document_repo = DocumentRepository(db, ctx)
    chunk_repo = ChunkRepository(db, ctx)
    index_repo = IndexRepository(db, ctx)
    ingest_task_repo = IngestTaskRepository(db, ctx)

    storage = storage_port or StubStoragePort()
    vector_port = StubVectorPort()
    llm_port = StubLLMPort()
    embedding_service = EmbeddingService(llm_port)
    trace_writer = TraceWriter(db, ctx)

    index_builder = IndexBuilder(
        db=db,
        ctx=ctx,
        vector_port=vector_port,
        embedding_service=embedding_service,
        storage_port=storage,
    )

    pipeline = DocumentPipeline(
        db=db,
        ctx=ctx,
        storage_port=storage,
        trace_writer=trace_writer,
        embedding_service=embedding_service,
        index_builder=index_builder,
    )

    retrieval = RetrievalService(
        db=db,
        ctx=ctx,
        vector_port=vector_port,
        llm_port=llm_port,
        embedding_service=embedding_service,
        storage_port=storage,
    )

    service = KnowledgeRuntimeService(
        db,
        ctx,
        knowledge_repo,
        document_repo,
        chunk_repo,
        index_repo,
        ingest_task_repo,
        pipeline,
        retrieval,
        index_builder=index_builder,
        storage_port=storage,
        vector_port=vector_port,
        trace_writer=trace_writer,
    )
    return service, storage, vector_port


def build_request_context() -> RequestContext:
    return RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
        tenant_role="Owner",
        workspace_role="Owner",
    )


@pytest.mark.asyncio
async def test_knowledge_pipeline_query_and_versioning(db):
    """Knowledge pipeline indexes content and supports version rollback."""
    import app.kernel.runtime.db.models  # noqa: F401
    from app.modules.knowledge.domain import models as _knowledge_models  # noqa: F401

    SQLModel.metadata.create_all(db.get_bind())

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
        tenant_role="Owner",
        workspace_role="Owner",
    )

    knowledge_repo = KnowledgeRepository(db, ctx)
    document_repo = DocumentRepository(db, ctx)
    chunk_repo = ChunkRepository(db, ctx)
    index_repo = IndexRepository(db, ctx)
    ingest_task_repo = IngestTaskRepository(db, ctx)

    storage_port = StubStoragePort()
    vector_port = StubVectorPort()
    llm_port = StubLLMPort()
    embedding_service = EmbeddingService(llm_port)
    trace_writer = TraceWriter(db, ctx)

    index_builder = IndexBuilder(
        db=db,
        ctx=ctx,
        vector_port=vector_port,
        embedding_service=embedding_service,
        storage_port=storage_port,
    )

    pipeline = DocumentPipeline(
        db=db,
        ctx=ctx,
        storage_port=storage_port,
        trace_writer=trace_writer,
        embedding_service=embedding_service,
        index_builder=index_builder,
    )

    retrieval = RetrievalService(
        db=db,
        ctx=ctx,
        vector_port=vector_port,
        llm_port=llm_port,
        embedding_service=embedding_service,
        storage_port=storage_port,
    )

    service = KnowledgeRuntimeService(
        db,
        ctx,
        knowledge_repo,
        document_repo,
        chunk_repo,
        index_repo,
        ingest_task_repo,
        pipeline,
        retrieval,
        index_builder=index_builder,
        storage_port=storage_port,
        vector_port=vector_port,
        trace_writer=trace_writer,
    )

    knowledge = await service.create_knowledge(
        KnowledgeCreate(
            name="kb_docs",
            type="document",
            description="Test knowledge",
            default_embedding_model_ref="model:test:embedding",
        )
    )

    doc_v1 = await service.upload_document(
        knowledge.id,
        DocumentUpload(
            doc_key="doc_1",
            source_kind="upload",
            title="Refund Policy",
            source_uri="s3://kb/refund-policy.txt",
        ),
        file_content=AsyncBytesStream([b"Hello ", b"world"]),
    )
    assert doc_v1.status == "indexed"
    assert doc_v1.size_bytes == 11
    assert doc_v1.checksum
    assert doc_v1.file_id in storage_port.streamed_keys

    results = await service.query(
        knowledge.id,
        QueryRequest(query="Hello", top_k=3),
    )
    assert results.total >= 1
    assert results.citations
    first_result = results.results[0]
    first_citation = results.citations[0]
    assert first_citation.document_id == doc_v1.id
    assert first_citation.chunk_id == first_result.chunk_id
    assert first_citation.knowledge_id == knowledge.id
    assert first_citation.doc_key == "doc_1"
    assert first_citation.title == "Refund Policy"
    assert first_citation.source_uri == "s3://kb/refund-policy.txt"
    assert first_citation.chunk_no == first_result.metadata["chunk_no"]
    assert first_citation.snippet
    assert first_result.metadata["knowledge_id"] == knowledge.id
    assert first_result.metadata["doc_key"] == "doc_1"
    assert first_result.metadata["title"] == "Refund Policy"

    service.retrieval_service = FailingRetrievalService()
    fallback_results = await service.query(
        knowledge.id,
        QueryRequest(query="refund", top_k=3),
    )
    assert fallback_results.total >= 1
    assert fallback_results.citations[0].chunk_id == first_result.chunk_id
    assert fallback_results.citations[0].doc_key == "doc_1"
    assert fallback_results.citations[0].snippet

    service.retrieval_service = EmptyRetrievalService()
    empty_fallback_results = await service.query(
        knowledge.id,
        QueryRequest(query="refund", top_k=3),
    )
    assert empty_fallback_results.total >= 1
    assert empty_fallback_results.citations[0].chunk_id == first_result.chunk_id

    doc_v2 = await service.upload_document(
        knowledge.id,
        DocumentUpload(doc_key="doc_1", source_kind="upload"),
        file_content=b"Hello world updated",
    )
    assert doc_v2.version == 2

    versions = await service.list_document_versions(knowledge.id, "doc_1")
    assert len(versions) == 2

    await service.delete_document(doc_v2.id)
    versions_after_delete = await service.list_document_versions(knowledge.id, "doc_1")
    assert any(doc.is_latest for doc in versions_after_delete)

    rolled_back = await service.rollback_document_version(knowledge.id, "doc_1", 1)
    assert rolled_back.is_latest is True


@pytest.mark.asyncio
async def test_knowledge_async_ingest_task_worker(db):
    """Async ingestion enqueues tasks and worker processes them."""
    import app.kernel.runtime.db.models  # noqa: F401
    from app.modules.knowledge.domain import models as _knowledge_models  # noqa: F401

    SQLModel.metadata.create_all(db.get_bind())

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
        tenant_role="Owner",
        workspace_role="Owner",
    )

    knowledge_repo = KnowledgeRepository(db, ctx)
    document_repo = DocumentRepository(db, ctx)
    chunk_repo = ChunkRepository(db, ctx)
    index_repo = IndexRepository(db, ctx)
    ingest_task_repo = IngestTaskRepository(db, ctx)

    storage_port = StubStoragePort()
    vector_port = StubVectorPort()
    llm_port = StubLLMPort()
    embedding_service = EmbeddingService(llm_port)
    trace_writer = TraceWriter(db, ctx)

    index_builder = IndexBuilder(
        db=db,
        ctx=ctx,
        vector_port=vector_port,
        embedding_service=embedding_service,
        storage_port=storage_port,
    )

    pipeline = DocumentPipeline(
        db=db,
        ctx=ctx,
        storage_port=storage_port,
        trace_writer=trace_writer,
        embedding_service=embedding_service,
        index_builder=index_builder,
    )

    retrieval = RetrievalService(
        db=db,
        ctx=ctx,
        vector_port=vector_port,
        llm_port=llm_port,
        embedding_service=embedding_service,
        storage_port=storage_port,
    )

    service = KnowledgeRuntimeService(
        db,
        ctx,
        knowledge_repo,
        document_repo,
        chunk_repo,
        index_repo,
        ingest_task_repo,
        pipeline,
        retrieval,
        index_builder=index_builder,
        storage_port=storage_port,
        vector_port=vector_port,
        trace_writer=trace_writer,
    )

    knowledge = await service.create_knowledge(
        KnowledgeCreate(
            name="kb_async",
            type="document",
            description="Async knowledge",
            default_embedding_model_ref="model:test:embedding",
        )
    )

    document = await service.upload_document(
        knowledge.id,
        DocumentUpload(doc_key="doc_async", source_kind="upload"),
        file_content=b"Hello async",
        async_ingest=True,
        max_retries=0,
    )
    assert document.status == "queued"

    pending_tasks = ingest_task_repo.list_pending()
    assert pending_tasks
    task = pending_tasks[0]

    worker = KnowledgeIngestWorker(service)
    await worker.run_once()

    refreshed_task = ingest_task_repo.get_by_id(task.id)
    assert refreshed_task is not None
    assert refreshed_task.status == "succeeded"

    refreshed_doc = document_repo.get_by_id(document.id)
    assert refreshed_doc is not None
    assert refreshed_doc.status == "indexed"


@pytest.mark.asyncio
async def test_knowledge_ingest_failure_records_failed_step_and_retry_succeeds(db):
    """Failed async ingest keeps observable run/step/task state and can be retried."""
    import app.kernel.runtime.db.models  # noqa: F401
    from app.modules.knowledge.domain import models as _knowledge_models  # noqa: F401

    SQLModel.metadata.create_all(db.get_bind())
    ctx = build_request_context()
    storage = FailingGetStoragePort()
    service, _, _ = build_knowledge_test_service(db, ctx, storage_port=storage)

    knowledge = await service.create_knowledge(
        KnowledgeCreate(
            name="kb_retry_failure",
            type="document",
            description="Retry knowledge",
            default_embedding_model_ref="model:test:embedding",
        )
    )
    document = await service.upload_document(
        knowledge.id,
        DocumentUpload(doc_key="retry-doc", source_kind="upload", title="Retry Doc"),
        file_content=b"retryable content",
        async_ingest=True,
        max_retries=1,
    )

    worker = KnowledgeIngestWorker(service)
    await worker.run_once()

    failed_task = service.ingest_task_repo.list_by_knowledge(knowledge.id)[0]
    failed_run_id = failed_task.run_id
    failed_document = service.document_repo.get_by_id(document.id)
    assert failed_task.status == "queued"
    assert failed_task.retry_count == 1
    assert failed_task.error_code == "INGEST_ERROR"
    assert failed_task.run_id
    assert failed_document is not None
    assert failed_document.status == "queued"

    run = db.get(Run, failed_task.run_id)
    assert run is not None
    assert run.status == "failed"
    steps = [
        row if isinstance(row, RunStep) else row[0]
        for row in db.exec(select(RunStep).where(RunStep.run_id == failed_task.run_id)).all()
    ]
    parse_step = next(step for step in steps if step.step_id == "parse")
    assert parse_step.status == "failed"
    assert parse_step.error_code == "PIPELINE_ERROR"
    assert "storage read unavailable" in (parse_step.error_message or "")

    storage.fail_reads = False
    await worker.run_once()

    succeeded_task = service.ingest_task_repo.get_by_id(failed_task.id)
    succeeded_document = service.document_repo.get_by_id(document.id)
    assert succeeded_task is not None
    assert succeeded_task.status == "succeeded"
    assert succeeded_task.run_id != failed_run_id
    retry_run = db.get(Run, succeeded_task.run_id)
    assert retry_run is not None
    assert retry_run.source_run_id == failed_run_id
    assert retry_run.attempt_no == 2
    assert retry_run.status == "succeeded"
    assert succeeded_task.retry_count == 1
    assert succeeded_document is not None
    assert succeeded_document.status == "indexed"


@pytest.mark.asyncio
async def test_knowledge_rebuild_records_index_run_and_preserves_query(db):
    """Index rebuild exposes its run id and leaves indexed content queryable."""
    import app.kernel.runtime.db.models  # noqa: F401
    from app.modules.knowledge.domain import models as _knowledge_models  # noqa: F401

    SQLModel.metadata.create_all(db.get_bind())
    ctx = build_request_context()
    service, _, _ = build_knowledge_test_service(db, ctx)

    knowledge = await service.create_knowledge(
        KnowledgeCreate(
            name="kb_rebuild",
            type="document",
            description="Rebuild knowledge",
            default_embedding_model_ref="model:test:embedding",
        )
    )
    document = await service.upload_document(
        knowledge.id,
        DocumentUpload(doc_key="rebuild-doc", source_kind="upload", title="Rebuild Doc"),
        file_content=b"Rebuild keeps citations queryable",
    )
    assert document.status == "indexed"

    index = service.index_repo.get_by_id(knowledge.default_index_id)
    assert index is not None
    old_build_version = index.build_version

    rebuilt = await service.rebuild_index(knowledge.id, index.id)

    assert rebuilt.status == "ready"
    assert rebuilt.last_run_id
    assert rebuilt.last_build_at is not None
    assert rebuilt.build_version == old_build_version + 1
    assert rebuilt.vector_count >= 1

    run = db.get(Run, rebuilt.last_run_id)
    assert run is not None
    assert run.status == "succeeded"
    steps = [
        row if isinstance(row, RunStep) else row[0]
        for row in db.exec(select(RunStep).where(RunStep.run_id == rebuilt.last_run_id)).all()
    ]
    assert any(step.step_id == "rebuild" and step.status == "succeeded" for step in steps)

    result = await service.query(knowledge.id, QueryRequest(query="citations", top_k=3))
    assert result.citations
    assert result.citations[0].title == "Rebuild Doc"
