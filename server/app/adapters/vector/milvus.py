""" milvus_vector

Milvus vector gateway adapter implementation.
"""

import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path
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

LITE_MODE = "lite"
"""Value of `MILVUS_MODE` that runs the embedded Milvus Lite engine."""

_loaded_collections: set[tuple[str, str, int, str, str]] = set()
"""Collections this process has loaded, keyed by connection and name."""


class MilvusVectorPort(VectorPort):
    """Milvus vector gateway adapter.

    Talks to a Milvus deployment over gRPC, or to an embedded Milvus Lite
    database file when `MILVUS_MODE=lite`. Both modes speak the same client
    API, so the mode only changes how the connection is opened and which index
    parameters are legal.
    """

    mode: str = "server"
    host: str = "localhost"
    port: int = 19530
    lite_file: str = ""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        *,
        mode: str | None = None,
        lite_file: str | None = None,
    ):
        """Initialize Milvus gateway.

        The Milvus connection is established lazily on first use (not here), so that
        constructing the port during request dependency injection does not fail when
        the vector store is temporarily unavailable.

        Args:
            host: Milvus host (defaults to settings).
            port: Milvus port (defaults to settings).
            mode: `server` or `lite` (defaults to settings).
            lite_file: Milvus Lite database file (defaults to settings).
        """
        self.mode = (mode or settings.milvus_mode or "server").strip().lower()
        self.host = host or settings.milvus_host
        self.port = port or settings.milvus_port
        self.lite_file = lite_file or settings.milvus_lite_file

    def _lite_uri(self) -> str:
        """Resolve the Milvus Lite database file into a connectable URI."""
        if sys.platform == "win32":
            # milvus-lite publishes no Windows wheel, so pymilvus would fail on
            # an import several frames deep. Say why here instead.
            raise KernelError(
                "VECTOR_LITE_UNSUPPORTED",
                "Milvus Lite has no Windows build. Run the server under WSL, or set MILVUS_MODE=server.",
                {"platform": sys.platform},
            )
        path = Path(self.lite_file).expanduser()
        if path.suffix != ".db":
            raise KernelError(
                "VECTOR_LITE_UNSUPPORTED",
                "MILVUS_LITE_FILE must be a local file path ending in '.db'.",
                {"lite_file": self.lite_file},
            )
        try:
            import milvus_lite  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
        except ImportError as exc:
            raise KernelError(
                "VECTOR_LITE_UNSUPPORTED",
                "Milvus Lite is not installed. Run `uv sync --extra milvus-lite`, or set MILVUS_MODE=server.",
                {"lite_file": self.lite_file},
            ) from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    def _ensure_connected(self) -> None:
        """Connect to Milvus on demand (idempotent)."""
        try:
            if connections.has_connection("default"):
                return
        except Exception:
            pass
        if self.mode == LITE_MODE:
            connections.connect("default", uri=self._lite_uri())
            return
        connections.connect("default", host=self.host, port=self.port)

    def _index_params(self, metric_type: str) -> dict[str, Any]:
        """Index parameters for the active mode.

        Milvus Lite implements FLAT only, and rejects the IVF_FLAT `nlist`
        tuning a server accepts. Local debugging collections are small enough
        that an exhaustive index costs nothing.
        """
        if self.mode == LITE_MODE:
            return {"index_type": "FLAT", "metric_type": metric_type, "params": {}}
        return {"index_type": "IVF_FLAT", "metric_type": metric_type, "params": {"nlist": 1024}}

    async def check_ready(self) -> None:
        """Probe vector-store connectivity; raise if unreachable (for readiness checks).

        The client blocks for as long as DNS and the connection take, over
        thirty seconds for a host that does not exist, so it runs off the event
        loop and the caller can stop waiting.
        """
        await asyncio.to_thread(self._check_ready)

    def _check_ready(self) -> None:
        self._ensure_connected()
        utility.get_server_version()

    def _load_key(self, collection_name: str) -> tuple[str, str, int, str, str]:
        return (self.mode, self.host, self.port, self.lite_file, collection_name)

    def _load_once(self, coll: Collection, collection_name: str) -> None:
        """Load a collection into memory the first time this process uses it.

        Loading an already loaded collection is a round trip to Milvus that
        every search used to pay; a search that finds it released reloads it.
        """
        key = self._load_key(collection_name)
        if key in _loaded_collections:
            return
        coll.load()
        _loaded_collections.add(key)

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
                index_params=self._index_params(metric_type),
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
        milvus_metric = self._to_milvus_metric(metric_type)
        await asyncio.to_thread(
            self._ensure_collection_connected,
            collection,
            dimension,
            bool(metadata_schema),
            milvus_metric,
        )

    def _ensure_collection_connected(
        self,
        collection_name: str,
        dimension: int,
        include_metadata: bool,
        metric_type: str,
    ) -> None:
        self._ensure_connected()
        self._ensure_collection(
            collection_name=collection_name,
            dimension=dimension,
            include_metadata=include_metadata,
            metric_type=metric_type,
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
        # pymilvus is a blocking gRPC client: on the event loop, one search
        # would stall every other request and execution in the process.
        return await asyncio.to_thread(self._query, collection, vector, top_k, filter, kwargs)

    def _query(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
        filter: dict[str, Any] | None,
        kwargs: dict[str, Any],
    ) -> VectorQueryResult:
        self._ensure_connected()
        collection_name = self._normalize_collection_name(collection)
        if not utility.has_collection(collection_name):
            return VectorQueryResult(ids=[], scores=[])

        coll = Collection(collection_name)
        self._load_once(coll, collection_name)

        # Build search params
        search_params = {
            "metric_type": self._to_milvus_metric(kwargs.get("metric_type")),
            "params": {} if self.mode == LITE_MODE else {"nprobe": 10},
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

        def search() -> Any:
            return coll.search(
                data=[vector],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=output_fields,
            )

        try:
            results = search()
        except Exception:
            # Released or recreated since this process loaded it: load again
            # and retry once.
            _loaded_collections.discard(self._load_key(collection_name))
            self._load_once(coll, collection_name)
            results = search()

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

        await asyncio.to_thread(self._insert, collection, vectors, ids, metadata)

    def _insert(
        self,
        collection: str,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None,
    ) -> None:
        self._ensure_connected()
        collection_name = self._normalize_collection_name(collection)

        dimension = len(vectors[0])
        include_metadata = bool(metadata)
        coll = self._ensure_collection(collection_name, dimension, include_metadata)
        self._load_once(coll, collection_name)

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

        await asyncio.to_thread(self._delete, collection, ids)

    def _delete(self, collection: str, ids: list[str]) -> None:
        self._ensure_connected()
        collection_name = self._normalize_collection_name(collection)
        coll = Collection(collection_name)
        self._load_once(coll, collection_name)

        # Delete by IDs
        # Milvus delete expects a filter expression or list of IDs
        # For Milvus 2.x, we use delete with expr
        expr = f'id in {ids}'
        coll.delete(expr)
        coll.flush()
