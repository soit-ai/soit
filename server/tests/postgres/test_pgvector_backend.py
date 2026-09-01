"""PostgreSQL-only round trip for the pgvector vector backend.

Skips unless DATABASE_URL points at a PostgreSQL that has the `vector`
extension available, so the suite still runs on a machine without one.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text

from app.adapters.vector.pgvector import PgVectorPort

SCHEMA = "vector_store_test"
COLLECTION = "knowledge:pgvector-test:index-1"


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    driver_url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(driver_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:  # pragma: no cover - depends on the local instance
        pytest.skip("The pgvector extension is not available in this database")
    finally:
        engine.dispose()
    return url


@pytest.fixture
def port(database_url: str) -> Iterator[PgVectorPort]:
    adapter = PgVectorPort(url=database_url, schema=SCHEMA)
    yield adapter
    engine = adapter._get_engine()
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
    engine.dispose()


@pytest.mark.asyncio
async def test_insert_query_and_delete_round_trip(port: PgVectorPort):
    await port.ensure_collection(
        collection=COLLECTION, dimension=3, metric_type="cosine", metadata_schema={"kb": "string"}
    )
    await port.insert(
        collection=COLLECTION,
        vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]],
        ids=["near", "far", "close"],
        metadata=[{"kb": "a"}, {"kb": "b"}, {"kb": "a"}],
    )

    result = await port.query(
        collection=COLLECTION, vector=[1.0, 0.0, 0.0], top_k=3, include_metadata=True
    )

    assert result.ids[0] == "near"
    # Cosine scores are similarities, so the identical vector scores highest and
    # the orthogonal one lowest — the direction retrieval thresholds assume.
    assert result.scores[0] == pytest.approx(1.0, abs=1e-6)
    assert result.scores == sorted(result.scores, reverse=True)
    assert result.metadata is not None
    assert result.metadata[0] == {"kb": "a"}

    filtered = await port.query(collection=COLLECTION, vector=[1.0, 0.0, 0.0], filter={"kb": "b"})
    assert filtered.ids == ["far"]

    await port.delete(collection=COLLECTION, ids=["near"])
    after_delete = await port.query(collection=COLLECTION, vector=[1.0, 0.0, 0.0], top_k=3)
    assert "near" not in after_delete.ids


@pytest.mark.asyncio
async def test_insert_twice_updates_instead_of_duplicating(port: PgVectorPort):
    await port.ensure_collection(collection=COLLECTION, dimension=3, metric_type="cosine")
    await port.insert(collection=COLLECTION, vectors=[[1.0, 0.0, 0.0]], ids=["chunk"])
    await port.insert(
        collection=COLLECTION,
        vectors=[[0.0, 1.0, 0.0]],
        ids=["chunk"],
        metadata=[{"kb": "a"}],
    )

    result = await port.query(
        collection=COLLECTION, vector=[0.0, 1.0, 0.0], top_k=10, include_metadata=True
    )

    assert result.ids == ["chunk"]
    assert result.scores[0] == pytest.approx(1.0, abs=1e-6)
    assert result.metadata == [{"kb": "a"}]


@pytest.mark.asyncio
async def test_metadata_filters_match_every_json_type(port: PgVectorPort):
    await port.ensure_collection(collection=COLLECTION, dimension=3, metric_type="cosine")
    await port.insert(
        collection=COLLECTION,
        vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        ids=["published", "draft"],
        metadata=[
            {"live": True, "chunk_no": 1, "tag": "a"},
            {"live": False, "chunk_no": 2, "tag": "b"},
        ],
    )
    query = [1.0, 0.0, 0.0]

    assert (await port.query(collection=COLLECTION, vector=query, filter={"live": True})).ids == [
        "published"
    ]
    assert (await port.query(collection=COLLECTION, vector=query, filter={"live": False})).ids == [
        "draft"
    ]
    assert (await port.query(collection=COLLECTION, vector=query, filter={"chunk_no": 2})).ids == [
        "draft"
    ]
    assert (await port.query(collection=COLLECTION, vector=query, filter={"tag": "a"})).ids == [
        "published"
    ]
    assert (
        await port.query(collection=COLLECTION, vector=query, filter={"tag": ["a", "b"]})
    ).ids == ["published", "draft"]


@pytest.mark.asyncio
async def test_collections_that_differ_only_by_case_stay_apart(port: PgVectorPort):
    for collection in ("case-check:Main", "case-check:main"):
        await port.ensure_collection(collection=collection, dimension=3, metric_type="cosine")
    await port.insert(collection="case-check:Main", vectors=[[1.0, 0.0, 0.0]], ids=["upper"])
    await port.insert(collection="case-check:main", vectors=[[1.0, 0.0, 0.0]], ids=["lower"])

    upper = await port.query(collection="case-check:Main", vector=[1.0, 0.0, 0.0], top_k=10)

    assert upper.ids == ["upper"]


@pytest.mark.asyncio
async def test_check_ready_passes_against_a_prepared_database(port: PgVectorPort):
    await port.check_ready()
