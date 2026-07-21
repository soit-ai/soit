""" milvus_vector

Milvus vector gateway adapter implementation.
"""

import hashlib
import json
import re
from typing import Any

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.kernel.commons.errors import KernelError
from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult
from app.settings.settings import settings


class MilvusVectorPort(VectorPort):
    """Milvus vector gateway adapter."""

    def __init__(self, host: str | None = None, port: int | None = None):
        """Initialize Milvus gateway.

        The Milvus connection is established lazily on first use (not here), so that
        constructing the port during request dependency injection does not fail when
        the vector store is temporarily unavailable.

        Args:
            host: Milvus host (defaults to settings).
            port: Milvus port (defaults to settings).
        """
        self.host = host or settings.milvus_host
        self.port = port or settings.milvus_port

    def _ensure_connected(self) -> None:
        """Connect to Milvus on demand (idempotent)."""
        try:
            if connections.has_connection("default"):
                return
        except Exception:
            pass
        connections.connect("default", host=self.host, port=self.port)

    async def check_ready(self) -> None:
        """Probe vector-store connectivity; raise if unreachable (for readiness checks)."""
        self._ensure_connected()
        utility.get_server_version()

    @staticmethod
    def _normalize_collection_name(name: str) -> str:
        """Normalize collection name to Milvus-compatible format."""
        if not name:
            return "collection"

        normalized = re.sub(r"[^A-Za-z0-9_]+", "_", name)
        normalized = normalized.strip("_") or "collection"
        if normalized[0].isdigit():
            normalized = f"c_{normalized}"

        max_len = 255
        if len(normalized) <= max_len:
            return normalized

        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
        trimmed = normalized[: max_len - 13]
        return f"{trimmed}_{digest}"

    @staticmethod
    def _to_milvus_metric(metric_type: str | None) -> str:
        """Map public metric names to Milvus metric names."""
        value = (metric_type or "cosine").lower()
        return {
            "cosine": "COSINE",
            "ip": "IP",
            "l2": "L2",
        }.get(value, value.upper())

    def _ensure_collection(
        self,
        collection_name: str,
        dimension: int,
        include_metadata: bool,
        metric_type: str = "L2",
    ) -> Collection:
        """Ensure collection exists with expected schema."""
        normalized = self._normalize_collection_name(collection_name)
        try:
            if utility.has_collection(normalized):
                return Collection(normalized)

            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, auto_id=False, max_length=256),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
            ]

            if include_metadata:
                fields.append(FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=8192))

            schema = CollectionSchema(fields=fields, description="soit vector collection")
            coll = Collection(name=normalized, schema=schema)
            coll.create_index(
                field_name="vector",
                index_params={"index_type": "IVF_FLAT", "metric_type": metric_type, "params": {"nlist": 1024}},
            )
            return coll
        except Exception as exc:
            raise KernelError(
                "VECTOR_COLLECTION_ERROR",
                f"Failed to ensure vector collection '{collection_name}': {exc}",
                {"collection": collection_name, "normalized_collection": normalized},
            ) from exc

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
        """Ensure Milvus collection exists."""
        del index_ref, run_id
        self._ensure_connected()
        milvus_metric = self._to_milvus_metric(metric_type)
        self._ensure_collection(
            collection_name=collection,
            dimension=dimension,
            include_metadata=bool(metadata_schema),
            metric_type=milvus_metric,
        )

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
        self._ensure_connected()
        collection_name = self._normalize_collection_name(collection)
        if not utility.has_collection(collection_name):
            return VectorQueryResult(ids=[], scores=[])

        coll = Collection(collection_name)
        coll.load()

        # Build search params
        search_params = {
            "metric_type": self._to_milvus_metric(kwargs.get("metric_type")),
            "params": {"nprobe": 10},
        }

        # Build filter expression if provided
        expr = None
        if filter:
            # Convert filter dict to Milvus expression
            conditions = []
            for key, value in filter.items():
                if isinstance(value, int | float):
                    conditions.append(f"{key} == {value}")
                elif isinstance(value, str):
                    conditions.append(f'{key} == "{value}"')
                elif isinstance(value, list):
                    conditions.append(f"{key} in {value}")
            if conditions:
                expr = " && ".join(conditions)

        # Perform search
        output_fields = []
        if kwargs.get("include_metadata", False):
            output_fields = ["metadata"]

        results = coll.search(
            data=[vector],
            anns_field="vector",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=output_fields,
        )

        # Extract results
        if not results or len(results) == 0:
            return VectorQueryResult(ids=[], scores=[])

        result = results[0]
        ids = [str(id) for id in result.ids]
        scores = result.distances

        # Extract metadata if available
        metadata = None
        if kwargs.get("include_metadata", False):
            metadata = []
            for hit in result:
                raw_meta = None
                if hasattr(hit, "entity") and hit.entity is not None:
                    raw_meta = hit.entity.get("metadata")
                if isinstance(raw_meta, str):
                    try:
                        raw_meta = json.loads(raw_meta)
                    except Exception:
                        pass
                metadata.append(raw_meta or {})

        return VectorQueryResult(
            ids=ids,
            scores=scores,
            metadata=metadata,
        )

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
            collection: Collection name (or index_ref from kwargs).
            vectors: List of vectors.
            ids: Document IDs.
            metadata: Optional metadata.
            **kwargs: Additional parameters (may contain index_ref).
        """
        if not vectors or not ids:
            return

        if len(vectors) != len(ids):
            raise ValueError("Vectors and IDs must have the same length")

        self._ensure_connected()
        collection_name = self._normalize_collection_name(collection)

        dimension = len(vectors[0])
        include_metadata = bool(metadata)
        coll = self._ensure_collection(collection_name, dimension, include_metadata)
        coll.load()

        # Prepare data for insertion
        # Milvus expects data as a list of lists, where each inner list represents a field
        # Format: [ids, vectors, ...metadata_fields]
        data = [ids, vectors]
        if metadata:
            serialized = [json.dumps(item, ensure_ascii=True, default=str) for item in metadata]
            data.append(serialized)

        # Insert data
        coll.insert(data)
        coll.flush()

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

        self._ensure_connected()
        collection_name = self._normalize_collection_name(collection)
        coll = Collection(collection_name)
        coll.load()

        # Delete by IDs
        # Milvus delete expects a filter expression or list of IDs
        # For Milvus 2.x, we use delete with expr
        expr = f'id in {ids}'
        coll.delete(expr)
        coll.flush()
