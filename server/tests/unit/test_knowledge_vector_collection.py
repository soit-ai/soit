"""Tests for Knowledge vector collection creation."""

import json

import pytest
from sqlmodel import SQLModel

import app.adapters.vector.milvus as milvus_module
from app.adapters.vector.milvus import MilvusVectorPort
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult
from app.modules.knowledge.domain.models import KnowledgeIndex
from app.modules.knowledge.runtime.embedding import EmbeddingService
from app.modules.knowledge.runtime.index_builder import IndexBuilder


class FakeVectorPort(VectorPort):
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, object]] = {}
        self.created_collections: list[str] = []
        self.ensure_attempts: list[str] = []

    async def ensure_collection(
        self,
        collection: str,
        dimension: int,
        metric_type: str,
        metadata_schema: dict[str, object] | None = None,
        *,
        index_ref: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self.ensure_attempts.append(collection)
        if collection in self.collections:
            return
        self.collections[collection] = {
            "dimension": dimension,
            "metric_type": metric_type,
            "metadata_schema": metadata_schema or {},
            "index_ref": index_ref,
            "run_id": run_id,
        }
        self.created_collections.append(collection)

    async def query(self, collection, vector, top_k=10, filter=None, **kwargs):
        return VectorQueryResult(ids=[], scores=[])

    async def insert(self, collection, vectors, ids, metadata=None, **kwargs):
        return None

    async def delete(self, collection, ids, **kwargs):
        return None


class FakeConnections:
    """Stub for pymilvus.connections so lazy _ensure_connected is a no-op in tests."""

    @staticmethod
    def has_connection(alias: str) -> bool:
        return True

    @staticmethod
    def connect(*args, **kwargs) -> None:
        return None


class FakeLLMPort(LLMPort):
    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        raise NotImplementedError

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_index_builder_creates_vector_collection_idempotently(db):
    from app.modules.knowledge.domain import models as _knowledge_models  # noqa: F401

    SQLModel.metadata.create_all(db.get_bind())
    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    fake_vector = FakeVectorPort()
    builder = IndexBuilder(
        db=db,
        ctx=ctx,
        vector_port=fake_vector,
        embedding_service=EmbeddingService(FakeLLMPort()),
    )
    index = KnowledgeIndex(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        knowledge_id="knowledge-1",
        name="primary",
        is_primary=True,
        provider="memory",
        collection_name=None,
        embedding_model_ref="model:test:embedding",
        dimension=3,
        metric_type="cosine",
    )
    db.add(index)
    db.commit()
    db.refresh(index)

    await builder.create_collection(index)
    await builder.create_collection(index)

    expected_collection = index.collection_name or f"idx_{index.id}"
    assert index.status == "building"
    assert fake_vector.created_collections == [expected_collection]
    assert fake_vector.ensure_attempts == [expected_collection, expected_collection]
    assert fake_vector.collections[expected_collection]["metadata_schema"] == {
        "knowledge_id": "string",
        "document_id": "string",
        "chunk_id": "string",
    }


@pytest.mark.asyncio
async def test_milvus_ensure_collection_is_idempotent_and_maps_metrics(monkeypatch):
    port = object.__new__(MilvusVectorPort)
    existing: set[str] = set()
    has_collection_calls: list[str] = []
    captured_params: list[dict[str, object]] = []

    class FakeUtility:
        @staticmethod
        def has_collection(name: str) -> bool:
            has_collection_calls.append(name)
            return name in existing

    class FakeCollection:
        def __init__(self, name: str, schema=None) -> None:
            self.name = name
            self.schema = schema
            if schema is not None:
                existing.add(name)

        def create_index(self, field_name: str, index_params: dict[str, object]) -> None:
            captured_params.append({"field_name": field_name, **index_params})

    monkeypatch.setattr(milvus_module, "utility", FakeUtility)
    monkeypatch.setattr(milvus_module, "Collection", FakeCollection)
    monkeypatch.setattr(milvus_module, "connections", FakeConnections)

    await port.ensure_collection(
        collection="knowledge:kb-1:index-1",
        dimension=3,
        metric_type="cosine",
        metadata_schema={"knowledge_id": "string"},
    )
    await port.ensure_collection(
        collection="knowledge:kb-1:index-1",
        dimension=3,
        metric_type="ip",
        metadata_schema={"knowledge_id": "string"},
    )

    normalized = MilvusVectorPort._normalize_collection_name("knowledge:kb-1:index-1")
    assert has_collection_calls == [normalized, normalized]
    assert len(captured_params) == 1
    assert captured_params[0]["field_name"] == "vector"
    assert captured_params[0]["metric_type"] == "COSINE"
    assert MilvusVectorPort._to_milvus_metric("ip") == "IP"
    assert MilvusVectorPort._to_milvus_metric("l2") == "L2"


@pytest.mark.asyncio
async def test_milvus_insert_query_delete_use_same_normalized_collection(monkeypatch):
    port = object.__new__(MilvusVectorPort)
    collection = "knowledge:kb-1:index-1"
    normalized = MilvusVectorPort._normalize_collection_name(collection)
    ensure_calls: list[str] = []
    opened_collections: list[str] = []
    inserted_data: list[object] = []
    search_params: dict[str, object] = {}
    delete_exprs: list[str] = []

    class FakeUtility:
        @staticmethod
        def has_collection(name: str) -> bool:
            return name == normalized

    class FakeHit:
        entity = {"metadata": json.dumps({"title": "Milvus Doc", "chunk_no": 1})}

    class FakeSearchResult:
        ids = ["vec-1"]
        distances = [0.12]

        def __iter__(self):
            return iter([FakeHit()])

    class FakeCollection:
        def __init__(self, name: str, schema=None) -> None:
            del schema
            self.name = name
            opened_collections.append(name)

        def load(self) -> None:
            return None

        def insert(self, data: list[object]) -> None:
            inserted_data.extend(data)

        def flush(self) -> None:
            return None

        def search(self, **kwargs):
            search_params.update(kwargs["param"])
            return [FakeSearchResult()]

        def delete(self, expr: str) -> None:
            delete_exprs.append(expr)

    def fake_ensure_collection(collection_name, dimension, include_metadata, metric_type="L2"):
        del dimension, include_metadata, metric_type
        ensure_calls.append(collection_name)
        return FakeCollection(collection_name)

    monkeypatch.setattr(milvus_module, "utility", FakeUtility)
    monkeypatch.setattr(milvus_module, "Collection", FakeCollection)
    monkeypatch.setattr(milvus_module, "connections", FakeConnections)
    monkeypatch.setattr(port, "_ensure_collection", fake_ensure_collection)

    await port.insert(
        collection=collection,
        vectors=[[0.1, 0.2, 0.3]],
        ids=["vec-1"],
        metadata=[{"title": "Milvus Doc", "chunk_no": 1}],
        index_ref="knowledge:kb-1:different-index-ref",
    )
    result = await port.query(
        collection=collection,
        vector=[0.1, 0.2, 0.3],
        top_k=1,
        include_metadata=True,
        metric_type="cosine",
    )
    await port.delete(collection=collection, ids=["vec-1"])

    assert ensure_calls == [normalized]
    assert opened_collections == [normalized, normalized, normalized]
    assert json.loads(inserted_data[2][0]) == {"title": "Milvus Doc", "chunk_no": 1}
    assert search_params["metric_type"] == "COSINE"
    assert result.ids == ["vec-1"]
    assert result.metadata == [{"title": "Milvus Doc", "chunk_no": 1}]
    assert delete_exprs == ["id in ['vec-1']"]
