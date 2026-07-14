""" memory

In-memory vector adapter for tests and local runs.
"""

from __future__ import annotations

import math
from typing import Any

from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult


class InMemoryVectorPort(VectorPort):
    """In-memory VectorPort implementation."""

    def __init__(self) -> None:
        self._collections: dict[str, dict[str, dict[str, Any]]] = {}
        self._collection_definitions: dict[str, dict[str, Any]] = {}

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        length = min(len(a), len(b))
        if length == 0:
            return 0.0
        dot = sum(a[i] * b[i] for i in range(length))
        norm_a = math.sqrt(sum(a[i] * a[i] for i in range(length)))
        norm_b = math.sqrt(sum(b[i] * b[i] for i in range(length)))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

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
        if collection in self._collection_definitions:
            return
        self._collection_definitions[collection] = {
            "dimension": dimension,
            "metric_type": metric_type,
            "metadata_schema": metadata_schema or {},
            "index_ref": index_ref,
            "run_id": run_id,
        }
        self._collections.setdefault(collection, {})

    async def query(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> VectorQueryResult:
        items = self._collections.get(collection, {})
        results: list[tuple[str, float, list[float], dict[str, Any]]] = []
        for doc_id, payload in items.items():
            metadata = payload.get("metadata") or {}
            if filter:
                if any(metadata.get(key) != value for key, value in filter.items()):
                    continue
            score = self._cosine_similarity(vector, payload.get("vector") or [])
            results.append((doc_id, score, payload.get("vector") or [], metadata))

        results.sort(key=lambda item: item[1], reverse=True)
        top = results[:top_k]
        return VectorQueryResult(
            ids=[item[0] for item in top],
            scores=[item[1] for item in top],
            vectors=[item[2] for item in top],
            metadata=[item[3] for item in top],
        )

    async def insert(
        self,
        collection: str,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        store = self._collections.setdefault(collection, {})
        for index, vector in enumerate(vectors):
            if index >= len(ids):
                break
            meta = None
            if metadata and index < len(metadata):
                meta = metadata[index]
            store[ids[index]] = {"vector": vector, "metadata": meta}

    async def delete(
        self,
        collection: str,
        ids: list[str],
        **kwargs: Any,
    ) -> None:
        store = self._collections.get(collection)
        if not store:
            return
        for doc_id in ids:
            store.pop(doc_id, None)
