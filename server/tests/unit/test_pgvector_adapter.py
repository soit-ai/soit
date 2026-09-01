"""The pgvector adapter builds the SQL Milvus's behaviour implies.

These tests never touch a database. The round trip against a real PostgreSQL
lives in `tests/postgres/test_pgvector_backend.py`, which skips without one.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.adapters.vector.pgvector import PgVectorPort
from app.settings.settings import Settings


def _port(**kwargs: Any) -> PgVectorPort:
    return PgVectorPort(url="postgresql://u:p@localhost:5432/soit", schema="vector_store", **kwargs)


class _RecordingConnection:
    """Captures statements instead of executing them."""

    def __init__(self, rows: list[tuple[Any, ...]] | None = None, table_exists: bool = True) -> None:
        self.statements: list[tuple[str, Any]] = []
        self._rows = rows or []
        self._table_exists = table_exists

    def execute(self, statement: Any, params: Any = None) -> _RecordingConnection:
        sql = str(statement)
        self.statements.append((sql, params))
        return self

    def scalar(self) -> Any:
        return "table" if self._table_exists else None

    def all(self) -> list[tuple[Any, ...]]:
        return self._rows

    def first(self) -> Any:
        return (1,)

    def __enter__(self) -> _RecordingConnection:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _FakeEngine:
    def __init__(self, conn: _RecordingConnection) -> None:
        self._conn = conn

    def begin(self) -> _RecordingConnection:
        return self._conn

    def connect(self) -> _RecordingConnection:
        return self._conn


def _wire(port: PgVectorPort, conn: _RecordingConnection) -> None:
    """Give the port a fake engine and skip the one-time DDL."""
    port._engine = _FakeEngine(conn)  # type: ignore[assignment]
    port._prepared = True


def _sql(conn: _RecordingConnection, needle: str) -> str:
    return next(sql for sql, _ in conn.statements if needle in sql)


def test_table_name_stays_within_the_postgres_identifier_limit():
    normalized = PgVectorPort._normalize_table_name("k" * 300)
    assert len(normalized) <= 63


def test_table_names_that_share_a_prefix_do_not_collide():
    first = PgVectorPort._normalize_table_name("knowledge:" + "a" * 80 + ":index-1")
    second = PgVectorPort._normalize_table_name("knowledge:" + "a" * 80 + ":index-2")
    assert first != second


def test_table_name_normalizes_the_collection_the_way_milvus_does():
    assert PgVectorPort._normalize_table_name("knowledge:kb-1:index-1") == "knowledge_kb_1_index_1"
    assert PgVectorPort._normalize_table_name("1st").startswith("c_")


def test_table_names_keep_the_case_that_tells_collections_apart():
    # Milvus keeps these apart, so folding them here would pour two
    # collections into one table.
    assert PgVectorPort._normalize_table_name("Main") != PgVectorPort._normalize_table_name("main")


@pytest.mark.asyncio
async def test_ensure_collection_creates_the_table_and_a_matching_index():
    conn = _RecordingConnection()
    port = _port()
    _wire(port, conn)

    await port.ensure_collection(
        collection="knowledge:kb-1:index-1", dimension=1536, metric_type="cosine"
    )

    create = _sql(conn, "CREATE TABLE")
    assert '"vector_store"."knowledge_kb_1_index_1"' in create
    assert "vector(1536)" in create
    assert "vector_cosine_ops" in _sql(conn, "CREATE INDEX")


@pytest.mark.asyncio
async def test_ensure_collection_skips_the_index_above_the_pgvector_limit():
    conn = _RecordingConnection()
    port = _port()
    _wire(port, conn)

    await port.ensure_collection(collection="wide", dimension=4096, metric_type="cosine")

    # pgvector refuses an HNSW index that wide; a scan still answers queries.
    assert not any("CREATE INDEX" in sql for sql, _ in conn.statements)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("metric", "operator", "score"),
    [
        ("cosine", "<=>", "1 - ("),
        ("ip", "<#>", "-("),
        ("l2", "<->", "embedding <->"),
    ],
)
async def test_query_reports_the_same_direction_as_milvus(metric, operator, score):
    conn = _RecordingConnection(rows=[("chunk-1", 0.75, {"knowledge_id": "kb-1"})])
    port = _port()
    _wire(port, conn)

    result = await port.query(collection="c", vector=[0.1, 0.2], top_k=5, metric_type=metric)

    select = _sql(conn, "SELECT id")
    assert operator in select
    assert score in select
    # Cosine and ip carry a similarity, l2 a distance, and both orders put the
    # closest row first.
    assert f"ORDER BY embedding {operator}" in select
    assert result.ids == ["chunk-1"]
    assert result.scores == [0.75]


@pytest.mark.asyncio
async def test_query_returns_metadata_only_when_asked_like_milvus():
    rows = [("chunk-1", 0.9, {"knowledge_id": "kb-1"})]
    port = _port()

    conn = _RecordingConnection(rows=rows)
    _wire(port, conn)
    assert (await port.query(collection="c", vector=[0.1])).metadata is None

    conn = _RecordingConnection(rows=rows)
    _wire(port, conn)
    with_metadata = await port.query(collection="c", vector=[0.1], include_metadata=True)
    assert with_metadata.metadata == [{"knowledge_id": "kb-1"}]


@pytest.mark.asyncio
async def test_query_on_a_missing_collection_returns_nothing():
    conn = _RecordingConnection(table_exists=False)
    port = _port()
    _wire(port, conn)

    result = await port.query(collection="never-indexed", vector=[0.1])

    assert result.ids == []
    assert result.scores == []
    assert not any("SELECT id" in sql for sql, _ in conn.statements)


@pytest.mark.asyncio
async def test_query_binds_filter_keys_and_values_rather_than_interpolating():
    conn = _RecordingConnection()
    port = _port()
    _wire(port, conn)

    await port.query(
        collection="c",
        vector=[0.1],
        filter={"knowledge_id": "kb-1'; DROP TABLE users; --", "chunk_no": 3, "tag": ["a", "b"]},
    )

    sql, params = next((sql, p) for sql, p in conn.statements if "SELECT id" in sql)
    assert "DROP TABLE" not in sql
    assert params["filter_value_0"] == "kb-1'; DROP TABLE users; --"
    assert params["filter_key_1"] == "chunk_no"
    assert params["filter_value_1"] == 3.0
    # A number compares numerically only where the stored value is a number,
    # so a text value does not fail the whole query on the cast.
    assert "jsonb_typeof" in sql
    assert params["filter_value_2"] == '["a", "b"]'


@pytest.mark.asyncio
@pytest.mark.parametrize(("value", "encoded"), [(True, "true"), (False, "false"), (None, "null")])
async def test_query_compares_booleans_and_nulls_as_json(value, encoded):
    conn = _RecordingConnection()
    port = _port()
    _wire(port, conn)

    await port.query(collection="c", vector=[0.1], filter={"published": value})

    sql, params = next((sql, p) for sql, p in conn.statements if "SELECT id" in sql)
    # `str(True)` is "True" and the stored JSON reads back as "true", so a text
    # comparison would never match.
    assert "CAST(:filter_value_0 AS jsonb)" in sql
    assert params["filter_value_0"] == encoded


@pytest.mark.asyncio
async def test_insert_upserts_because_reindexing_rewrites_a_chunk():
    conn = _RecordingConnection()
    port = _port()
    _wire(port, conn)

    await port.insert(
        collection="c",
        vectors=[[0.1, 0.2], [0.3, 0.4]],
        ids=["a", "b"],
        metadata=[{"knowledge_id": "kb-1"}, {}],
    )

    sql, params = next((sql, p) for sql, p in conn.statements if "INSERT INTO" in sql)
    assert "ON CONFLICT (id) DO UPDATE" in sql
    assert [row["id"] for row in params] == ["a", "b"]
    assert params[0]["embedding"] == "[0.1,0.2]"
    assert params[0]["metadata"] == '{"knowledge_id": "kb-1"}'


@pytest.mark.asyncio
async def test_insert_rejects_mismatched_ids():
    port = _port()
    with pytest.raises(ValueError, match="same length"):
        await port.insert(collection="c", vectors=[[0.1]], ids=["a", "b"])


@pytest.mark.asyncio
async def test_delete_removes_the_given_ids():
    conn = _RecordingConnection()
    port = _port()
    _wire(port, conn)

    await port.delete(collection="c", ids=["a", "b"])

    sql, params = next((sql, p) for sql, p in conn.statements if "DELETE FROM" in sql)
    assert "id = ANY(:ids)" in sql
    assert params == {"ids": ["a", "b"]}


@pytest.mark.asyncio
async def test_delete_on_a_missing_collection_is_a_no_op():
    conn = _RecordingConnection(table_exists=False)
    port = _port()
    _wire(port, conn)

    await port.delete(collection="never-indexed", ids=["a"])

    assert not any("DELETE FROM" in sql for sql, _ in conn.statements)


def test_url_falls_back_to_the_application_database(monkeypatch):
    import app.adapters.vector.pgvector as pgvector_mod

    monkeypatch.setattr(pgvector_mod.settings, "pgvector_url", None, raising=False)
    monkeypatch.setattr(
        pgvector_mod.settings, "database_url", "postgresql://u:p@localhost:5432/soit", raising=False
    )
    assert PgVectorPort().url == "postgresql://u:p@localhost:5432/soit"


def test_settings_reject_an_unknown_backend():
    with pytest.raises(ValueError, match="VECTOR_BACKEND"):
        Settings(vector_backend="qdrant", _env_file=None)


def test_production_refuses_the_pgvector_backend():
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql://soit:secret@db.internal:5432/soit",
        event_bus_backend="redis",
        vector_backend="pgvector",
    )
    with pytest.raises(ValueError, match="Milvus vector backend"):
        settings.validate_runtime_requirements()


def test_container_builds_the_backend_the_settings_name(monkeypatch):
    from app.adapters.vector.pgvector import PgVectorPort as Port
    from app.wiring.container import Container

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("SOIT_TESTING", "0")
    import app.wiring.container as container_mod

    monkeypatch.setattr(container_mod.settings, "vector_backend", "pgvector", raising=False)
    assert isinstance(Container()._create_vector_port(), Port)
