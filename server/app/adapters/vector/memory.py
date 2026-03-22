""" memory

In-memory vector adapter for tests and local runs.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import math

from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult


class InMemoryVectorPort(VectorPort):
    """In-memory VectorPort implementation."""

    def __init__(self) -> None:
        self._collections: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
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

    async def query(
        self,
        collection: str,
        vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> VectorQueryResult:
        items = self._collections.get(collection, {})
        results: List[tuple[str, float, List[float], Dict[str, Any]]] = []
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
        vectors: List[List[float]],
        ids: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
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
        ids: List[str],
        **kwargs: Any,
    ) -> None:
        store = self._collections.get(collection)
        if not store:
            return
        for doc_id in ids:
            store.pop(doc_id, None)
