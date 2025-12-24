""" interface

Vector database gateway interface.
"""

from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod


class VectorQueryResult:
    """Vector query result."""
    
    def __init__(
        self,
        ids: List[str],
        scores: List[float],
        vectors: Optional[List[List[float]]] = None,
        metadata: Optional[List[Dict[str, Any]]] = None,
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


class VectorGateway(ABC):
    """Vector database gateway interface."""
    
    @abstractmethod
    async def query(
        self,
        collection: str,
        vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
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
        vectors: List[List[float]],
        ids: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
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
        ids: List[str],
        **kwargs: Any,
    ) -> None:
        """Delete vectors.
        
        Args:
            collection: Collection name.
            ids: Document IDs to delete.
            **kwargs: Additional parameters.
        """
        pass
