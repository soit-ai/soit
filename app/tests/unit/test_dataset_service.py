"""test_dataset_service

Unit tests for DatasetService.
"""

import pytest
from sqlmodel import SQLModel

from app.kernel.contracts.context import RequestContext
from app.kernel.trace.writer import TraceWriter
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult
from app.kernel.ports.llm.interface import LLMPort, EmbeddingResponse, RerankResponse
from app.modules.dataset.application.service import DatasetService
from app.modules.dataset.application.schemas import (
    DatasetCreate,
    DocumentUpload,
    QueryRequest,
)
from app.modules.dataset.infra.repository import (
    DatasetRepository,
    DocumentRepository,
    ChunkRepository,
    IndexRepository,
    IngestTaskRepository,
)
from app.modules.dataset.runtime.embedding import EmbeddingService
from app.modules.dataset.runtime.index_builder import IndexBuilder
from app.modules.dataset.runtime.pipeline import DocumentPipeline
from app.modules.dataset.runtime.retrieval import RetrievalService
from app.modules.dataset.runtime.ingest_worker import DatasetIngestWorker


class StubStoragePort(StoragePort):
    """In-memory storage stub."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key, data, content_type=None, metadata=None, **kwargs):
        self.objects[key] = data
        return key

    async def get(self, key, **kwargs):
        return self.objects[key]

    async def delete(self, key, **kwargs):
        self.objects.pop(key, None)

    async def exists(self, key, **kwargs):
        return key in self.objects


class StubVectorPort(VectorPort):
    """In-memory vector store stub."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, object]]] = {}

    async def query(self, collection, vector, top_k=10, filter=None, **kwargs):
        records = self.collections.get(collection, {})
        scores = []
        for chunk_id, payload in records.items():
            stored_vector = payload["vector"]
            score = sum((q * v) for q, v in zip(vector, stored_vector))
            scores.append((chunk_id, score))

        scores.sort(key=lambda item: item[1], reverse=True)
        ids = [item[0] for item in scores[:top_k]]
        values = [item[1] for item in scores[:top_k]]
        return VectorQueryResult(ids=ids, scores=values)

    async def insert(self, collection, vectors, ids, metadata=None, **kwargs):
        store = self.collections.setdefault(collection, {})
        meta_list = metadata or [{} for _ in ids]
        for idx, vector, meta in zip(ids, vectors, meta_list):
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
        raise NotImplementedError("chat not used in dataset tests")

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


@pytest.mark.asyncio
async def test_dataset_pipeline_query_and_versioning(db):
    """Dataset pipeline indexes content and supports version rollback."""
    from app.modules.dataset.domain import models as _dataset_models  # noqa: F401
    from app.kernel.trace import models as _trace_models  # noqa: F401

    SQLModel.metadata.create_all(db.get_bind())

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
        tenant_role="Owner",
        workspace_role="Owner",
    )

    dataset_repo = DatasetRepository(db, ctx)
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

    service = DatasetService(
        db,
        ctx,
        dataset_repo,
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

    dataset = await service.create_dataset(
        DatasetCreate(
            name="kb_docs",
            type="document",
            description="Test dataset",
            default_embedding_model_ref="model:test:embedding",
        )
    )

    doc_v1 = await service.upload_document(
        dataset.id,
        DocumentUpload(doc_key="doc_1", source_type="upload"),
        file_content=b"Hello world",
    )
    assert doc_v1.status == "indexed"

    results = await service.query(
        dataset.id,
        QueryRequest(query="Hello", top_k=3),
    )
    assert results.total >= 1

    doc_v2 = await service.upload_document(
        dataset.id,
        DocumentUpload(doc_key="doc_1", source_type="upload"),
        file_content=b"Hello world updated",
    )
    assert doc_v2.version == 2

    versions = await service.list_document_versions(dataset.id, "doc_1")
    assert len(versions) == 2

    await service.delete_document(doc_v2.id)
    versions_after_delete = await service.list_document_versions(dataset.id, "doc_1")
    assert any(doc.is_latest for doc in versions_after_delete)

    rolled_back = await service.rollback_document_version(dataset.id, "doc_1", 1)
    assert rolled_back.is_latest is True


@pytest.mark.asyncio
async def test_dataset_async_ingest_task_worker(db):
    """Async ingestion enqueues tasks and worker processes them."""
    from app.modules.dataset.domain import models as _dataset_models  # noqa: F401
    from app.kernel.trace import models as _trace_models  # noqa: F401

    SQLModel.metadata.create_all(db.get_bind())

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
        tenant_role="Owner",
        workspace_role="Owner",
    )

    dataset_repo = DatasetRepository(db, ctx)
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

    service = DatasetService(
        db,
        ctx,
        dataset_repo,
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

    dataset = await service.create_dataset(
        DatasetCreate(
            name="kb_async",
            type="document",
            description="Async dataset",
            default_embedding_model_ref="model:test:embedding",
        )
    )

    document = await service.upload_document(
        dataset.id,
        DocumentUpload(doc_key="doc_async", source_type="upload"),
        file_content=b"Hello async",
        async_ingest=True,
        max_retries=0,
    )
    assert document.status == "queued"

    pending_tasks = ingest_task_repo.list_pending()
    assert pending_tasks
    task = pending_tasks[0]

    worker = DatasetIngestWorker(service)
    await worker.run_once()

    refreshed_task = ingest_task_repo.get_by_id(task.id)
    assert refreshed_task is not None
    assert refreshed_task.status == "succeeded"

    refreshed_doc = document_repo.get_by_id(document.id)
    assert refreshed_doc is not None
    assert refreshed_doc.status == "indexed"
