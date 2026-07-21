""" interface

Vector database port interface.
"""

from abc import ABC, abstractmethod
from typing import Any


class VectorQueryResult:
    """Vector query result."""

    def __init__(
        self,
        ids: list[str],
        scores: list[float],
        vectors: list[list[float]] | None = None,
        metadata: list[dict[str, Any]] | None = None,
    ):
        """Initialize query result.

        Args:
            ids: Document IDs.
            scores: Similarity scores.
            vectors: Optional vectors.
            metadata: Optional metadata.
        """
        self.ids = ids
        self.scores = scores
        self.vectors = vectors
        self.metadata = metadata


class VectorPort(ABC):
    """Vector database port interface."""

    async def check_ready(self) -> None:
        """Probe connectivity; raise if the vector store is unreachable.

        Default is a no-op (always ready). Adapters backed by an external store
        override this so readiness checks can report the store's availability.
        """
        return None

    @abstractmethod
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
        """Ensure a vector collection exists."""
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass
