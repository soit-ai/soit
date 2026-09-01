""" pgvector

PostgreSQL/pgvector vector gateway adapter.

Stores each collection as one table of `(id, embedding, metadata)` in a
dedicated schema, so a PostgreSQL instance with the `vector` extension can
stand in for Milvus during local development. Scores match what Milvus returns
for the same metric — a similarity for `cosine` and `ip`, a distance for `l2`
— because the retrieval layer compares them against thresholds.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any

from sqlalchemy import Engine, create_engine, text

from app.kernel.commons.errors import KernelError
from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult
from app.settings.settings import settings

MAX_IDENTIFIER_LENGTH = 63
"""PostgreSQL truncates identifiers past this, which would merge collections."""

MAX_INDEXABLE_DIMENSION = 2000
"""pgvector refuses an HNSW index above this many dimensions."""

_METRIC_OPERATORS = {
    # metric -> (distance operator, index operator class)
    "cosine": ("<=>", "vector_cosine_ops"),
    "ip": ("<#>", "vector_ip_ops"),
    "l2": ("<->", "vector_l2_ops"),
}


class PgVectorPort(VectorPort):
    """PostgreSQL/pgvector vector gateway adapter."""

    def __init__(self, url: str | None = None, schema: str | None = None):
        """Initialize the pgvector gateway.

        The engine is created lazily on first use, so constructing the port
        during dependency injection does not open a connection pool for a
        request that never touches the vector store.

        Args:
            url: PostgreSQL URL (defaults to settings, then the app database).
            schema: Schema holding the collection tables (defaults to settings).
        """
        self.url = url or settings.pgvector_url or settings.database_url or ""
        self.schema = schema or settings.pgvector_schema
        self._engine: Engine | None = None
        self._prepared = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _get_engine(self) -> Engine:
        """Create the engine on demand (idempotent)."""
        if self._engine is None:
            url = self.url
            if not url:
                raise KernelError(
                    "VECTOR_BACKEND_NOT_CONFIGURED",
                    "PGVECTOR_URL is not set and no database URL is configured.",
                    {"backend": "pgvector"},
                )
            # Match the app engine: psycopg (v3) is the installed driver.
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            self._engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
        return self._engine

    def _prepare(self) -> None:
        """Ensure the extension and the collection schema exist (idempotent)."""
        if self._prepared:
            return
        engine = self._get_engine()
        with engine.begin() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception as exc:
                # Creating an extension needs privileges a shared instance may
                # not grant. Say what to run rather than failing on the first
                # unknown-type error later.
                raise KernelError(
                    "VECTOR_EXTENSION_MISSING",
                    "The pgvector extension is unavailable. Run 'CREATE EXTENSION vector' "
                    "as a superuser in the target database.",
                    {"schema": self.schema},
                ) from exc
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{self._quoted(self.schema)}"'))
        self._prepared = True

    async def check_ready(self) -> None:
        """Probe the database and the extension (for readiness checks)."""
        await asyncio.to_thread(self._check_ready)

    def _check_ready(self) -> None:
        engine = self._get_engine()
        with engine.connect() as conn:
            installed = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).first()
        if installed is None:
            raise KernelError(
                "VECTOR_EXTENSION_MISSING",
                "The pgvector extension is not installed in the target database.",
                {"schema": self.schema},
            )

    # ------------------------------------------------------------------
    # Naming
    # ------------------------------------------------------------------

    @staticmethod
    def _quoted(identifier: str) -> str:
        """Escape an identifier for use inside double quotes."""
        return identifier.replace('"', '""')

    @staticmethod
    def _normalize_table_name(name: str) -> str:
        """Normalize a collection name into a PostgreSQL table name.

        Mirrors the Milvus normalizer, but against PostgreSQL's 63-byte
        identifier limit: a longer name is truncated with a digest so two
        collections that share a prefix do not become one table.

        Case is preserved for the same reason. A collection name can come from
        an index's `collection_name`, so `Main` and `main` are two collections
        to Milvus, and folding them here would pour both into one table. Every
        identifier this adapter emits is double quoted, so PostgreSQL keeps the
        case rather than folding it back.
        """
        if not name:
            return "collection"

        normalized = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_") or "collection"
        if normalized[0].isdigit():
            normalized = f"c_{normalized}"

        if len(normalized) <= MAX_IDENTIFIER_LENGTH:
            return normalized

        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
        return f"{normalized[: MAX_IDENTIFIER_LENGTH - 13]}_{digest}"

    def _table(self, collection: str) -> str:
        """Fully qualified, quoted table reference for a collection."""
        table = self._normalize_table_name(collection)
        return f'"{self._quoted(self.schema)}"."{self._quoted(table)}"'

    @staticmethod
    def _to_metric(metric_type: str | None) -> str:
        """Normalize a public metric name, defaulting to cosine."""
        value = (metric_type or "cosine").strip().lower()
        return value if value in _METRIC_OPERATORS else "cosine"

    @staticmethod
    def _to_vector_literal(vector: list[float]) -> str:
        """Render a vector as the text form pgvector parses."""
        return "[" + ",".join(repr(float(value)) for value in vector) + "]"

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------

    async def ensure_collection(
        self,
        collection: str,
        dimension: int,
        metric_type: str,
        metadata_schema: dict[str, Any] | None = None,
        *,
        index_ref: str | None = None,
        run_id: str | None = None,
    ) -> None:
        """Ensure the collection table and its index exist."""
        del metadata_schema, index_ref, run_id
        await asyncio.to_thread(
            self._ensure_collection, collection, dimension, self._to_metric(metric_type)
        )

    def _ensure_collection(self, collection: str, dimension: int, metric: str) -> None:
        self._prepare()
        table = self._table(collection)
        index_name = self._normalize_table_name(f"{collection}_embedding_idx")
        _, ops = _METRIC_OPERATORS[metric]
        try:
            with self._get_engine().begin() as conn:
                conn.execute(
                    text(
                        f"CREATE TABLE IF NOT EXISTS {table} ("
                        " id text PRIMARY KEY,"
                        f" embedding vector({int(dimension)}) NOT NULL,"
                        " metadata jsonb NOT NULL DEFAULT '{}'::jsonb)"
                    )
                )
                if dimension <= MAX_INDEXABLE_DIMENSION:
                    # Above the limit pgvector rejects the index; the table still
                    # answers queries by scanning, which is what a local
                    # development collection can afford.
                    conn.execute(
                        text(
                            f'CREATE INDEX IF NOT EXISTS "{self._quoted(index_name)}" '
                            f"ON {table} USING hnsw (embedding {ops})"
                        )
                    )
        except KernelError:
            raise
        except Exception as exc:
            raise KernelError(
                "VECTOR_COLLECTION_ERROR",
                f"Failed to ensure vector collection '{collection}': {exc}",
                {"collection": collection, "normalized_collection": table},
            ) from exc

    def _table_exists(self, conn: Any, collection: str) -> bool:
        return (
            conn.execute(
                text("SELECT to_regclass(:name)"),
                {"name": self._table(collection)},
            ).scalar()
            is not None
        )

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    async def query(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> VectorQueryResult:
        """Query similar vectors.

        Args:
            collection: Collection name.
            vector: Query vector.
            top_k: Number of results.
            filter: Optional metadata filter.
            **kwargs: Additional parameters.

        Returns:
            VectorQueryResult instance.
        """
        return await asyncio.to_thread(
            self._query,
            collection,
            vector,
            top_k,
            filter,
            self._to_metric(kwargs.get("metric_type")),
            bool(kwargs.get("include_metadata", False)),
        )

    def _query(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
        filter: dict[str, Any] | None,
        metric: str,
        include_metadata: bool,
    ) -> VectorQueryResult:
        self._prepare()
        table = self._table(collection)
        operator, _ = _METRIC_OPERATORS[metric]
        params: dict[str, Any] = {
            "query_vector": self._to_vector_literal(vector),
            "top_k": max(int(top_k), 0),
        }
        where = self._build_filter(filter, params)

        # Milvus reports a similarity for cosine and ip and a raw distance for
        # l2. Retrieval compares the number against a threshold, so the two
        # backends have to agree on which direction is "closer".
        distance = f"embedding {operator} CAST(:query_vector AS vector)"
        score = {
            "cosine": f"1 - ({distance})",
            "ip": f"-({distance})",
            "l2": distance,
        }[metric]

        with self._get_engine().connect() as conn:
            if not self._table_exists(conn, collection):
                return VectorQueryResult(ids=[], scores=[])
            rows = conn.execute(
                text(
                    f"SELECT id, {score} AS score, metadata FROM {table}"
                    f"{where} ORDER BY {distance} LIMIT :top_k"
                ),
                params,
            ).all()

        return VectorQueryResult(
            ids=[str(row[0]) for row in rows],
            scores=[float(row[1]) for row in rows],
            metadata=[self._decode_metadata(row[2]) for row in rows] if include_metadata else None,
        )

    @staticmethod
    def _decode_metadata(value: Any) -> dict[str, Any]:
        """Read a metadata column back, whatever the driver handed over."""
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except ValueError:
                return {}
            return decoded if isinstance(decoded, dict) else {}
        return {}

    @staticmethod
    def _build_filter(filter: dict[str, Any] | None, params: dict[str, Any]) -> str:
        """Build a WHERE clause over the metadata column.

        Values are bound, never interpolated; keys are bound too, so a metadata
        key cannot carry SQL into the statement.
        """
        if not filter:
            return ""
        conditions: list[str] = []
        for position, (key, value) in enumerate(filter.items()):
            key_param = f"CAST(:filter_key_{position} AS text)"
            value_param = f"filter_value_{position}"
            params[f"filter_key_{position}"] = key
            if isinstance(value, list):
                params[value_param] = json.dumps(value)
                conditions.append(
                    f"CAST(:{value_param} AS jsonb) @> (metadata -> {key_param})"
                )
                continue
            if value is None or isinstance(value, bool):
                # `str(True)` is "True" and `metadata ->> key` yields "true", so
                # comparing these as text never matches. Compare the JSON values.
                params[value_param] = json.dumps(value)
                conditions.append(
                    f"metadata -> {key_param} = CAST(:{value_param} AS jsonb)"
                )
                continue
            if not isinstance(value, int | float):
                params[value_param] = str(value)
                conditions.append(f"metadata ->> {key_param} = :{value_param}")
                continue
            params[value_param] = float(value)
            # CASE, not AND: only the chosen branch is evaluated, so a row whose
            # value is text does not fail the whole query on the numeric cast.
            conditions.append(
                f"CASE WHEN jsonb_typeof(metadata -> {key_param}) = 'number'"
                f" THEN (metadata ->> {key_param})::double precision = :{value_param}"
                " ELSE false END"
            )
        return " WHERE " + " AND ".join(conditions)

    async def insert(
        self,
        collection: str,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        """Insert vectors.

        Args:
            collection: Collection name.
            vectors: List of vectors.
            ids: Document IDs.
            metadata: Optional metadata.
            **kwargs: Additional parameters.
        """
        if not vectors or not ids:
            return
        if len(vectors) != len(ids):
            raise ValueError("Vectors and IDs must have the same length")

        await asyncio.to_thread(
            self._insert, collection, vectors, ids, metadata, self._to_metric(kwargs.get("metric_type"))
        )

    def _insert(
        self,
        collection: str,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None,
        metric: str,
    ) -> None:
        self._ensure_collection(collection, len(vectors[0]), metric)
        table = self._table(collection)
        rows = [
            {
                "id": ids[index],
                "embedding": self._to_vector_literal(vector),
                "metadata": json.dumps(
                    (metadata[index] if metadata and index < len(metadata) else None) or {},
                    ensure_ascii=True,
                    default=str,
                ),
            }
            for index, vector in enumerate(vectors)
        ]
        with self._get_engine().begin() as conn:
            # Re-indexing a chunk rewrites its row; Milvus upserts on a
            # primary key, so a plain insert would diverge on the second run.
            conn.execute(
                text(
                    f"INSERT INTO {table} (id, embedding, metadata) VALUES "
                    "(:id, CAST(:embedding AS vector), CAST(:metadata AS jsonb)) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata"
                ),
                rows,
            )

    async def delete(
        self,
        collection: str,
        ids: list[str],
        **kwargs: Any,
    ) -> None:
        """Delete vectors.

        Args:
            collection: Collection name.
            ids: Document IDs to delete.
            **kwargs: Additional parameters.
        """
        if not ids:
            return
        await asyncio.to_thread(self._delete, collection, ids)

    def _delete(self, collection: str, ids: list[str]) -> None:
        self._prepare()
        table = self._table(collection)
        with self._get_engine().begin() as conn:
            if not self._table_exists(conn, collection):
                return
            conn.execute(
                text(f"DELETE FROM {table} WHERE id = ANY(:ids)"),
                {"ids": list(ids)},
            )
