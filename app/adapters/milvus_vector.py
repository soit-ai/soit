""" milvus_vector

Milvus vector gateway adapter implementation.
"""

from typing import List, Dict, Any, Optional
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType

from app.kernel.gateways.vector.interface import VectorGateway, VectorQueryResult
from app.kernel.config.settings import settings


class MilvusGateway(VectorGateway):
    """Milvus vector gateway adapter."""
    
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        """Initialize Milvus gateway.
        
        Args:
            host: Milvus host (defaults to settings).
            port: Milvus port (defaults to settings).
        """
        self.host = host or settings.milvus_host
        self.port = port or settings.milvus_port
        connections.connect("default", host=self.host, port=self.port)
    
    async def query(
        self,
        collection: str,
        vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> VectorQueryResult:
        """Query similar vectors."""
        coll = Collection(collection)
        coll.load()
        
        # Build search params
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        
        # Perform search
        results = coll.search(
            data=[vector],
            anns_field="vector",
            param=search_params,
            limit=top_k,
            expr=str(filter) if filter else None,
        )
        
        # Extract results
        ids = [str(id) for id in results[0].ids]
        scores = results[0].distances
        
        return VectorQueryResult(
            ids=ids,
            scores=scores,
        )
    
    async def insert(
        self,
        collection: str,
        vectors: List[List[float]],
        ids: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> None:
        """Insert vectors."""
        coll = Collection(collection)
        # In production, properly format and insert data
        # This is a placeholder
        pass
    
    async def delete(
        self,
        collection: str,
        ids: List[str],
        **kwargs,
    ) -> None:
        """Delete vectors."""
        coll = Collection(collection)
        # In production, delete by IDs
        # This is a placeholder
        pass
