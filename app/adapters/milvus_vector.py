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
        coll = Collection(collection)
        coll.load()
        
        # Build search params
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        
        # Build filter expression if provided
        expr = None
        if filter:
            # Convert filter dict to Milvus expression
            conditions = []
            for key, value in filter.items():
                if isinstance(value, (int, float)):
                    conditions.append(f"{key} == {value}")
                elif isinstance(value, str):
                    conditions.append(f'{key} == "{value}"')
                elif isinstance(value, list):
                    conditions.append(f"{key} in {value}")
            if conditions:
                expr = " && ".join(conditions)
        
        # Perform search
        results = coll.search(
            data=[vector],
            anns_field="vector",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["*"] if kwargs.get("include_metadata", False) else [],
        )
        
        # Extract results
        if not results or len(results) == 0:
            return VectorQueryResult(ids=[], scores=[])
        
        result = results[0]
        ids = [str(id) for id in result.ids]
        scores = result.distances
        
        # Extract metadata if available
        metadata = None
        if hasattr(result, "entities") and result.entities:
            metadata = []
            for entity in result.entities:
                meta_dict = {}
                for field_name, field_values in entity.items():
                    if field_name != "vector":  # Exclude vector field from metadata
                        meta_dict[field_name] = field_values[0] if field_values else None
                metadata.append(meta_dict)
        
        return VectorQueryResult(
            ids=ids,
            scores=scores,
            metadata=metadata,
        )
    
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
        
        # Support both collection and index_ref parameters
        collection_name = kwargs.get("index_ref", collection)
        # If index_ref format is "ds:dataset_id:index_id", extract collection name
        if ":" in collection_name:
            # Use the index_ref as collection name, or extract meaningful part
            # For now, use as-is (Milvus collection names can contain special chars)
            pass
        
        coll = Collection(collection_name)
        coll.load()
        
        # Prepare data for insertion
        # Milvus expects data as a list of lists, where each inner list represents a field
        # Format: [ids, vectors, ...metadata_fields]
        data = [ids, vectors]
        
        # Add metadata fields if provided
        if metadata:
            # Extract all unique keys from metadata
            all_keys = set()
            for meta in metadata:
                if isinstance(meta, dict):
                    all_keys.update(meta.keys())
            
            # Add each metadata field as a separate list
            for key in sorted(all_keys):  # Sort for consistency
                field_data = [meta.get(key) if isinstance(meta, dict) else None for meta in metadata]
                data.append(field_data)
        
        # Insert data
        coll.insert(data)
        coll.flush()
    
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
        if not ids:
            return
        
        coll = Collection(collection)
        coll.load()
        
        # Delete by IDs
        # Milvus delete expects a filter expression or list of IDs
        # For Milvus 2.x, we use delete with expr
        expr = f'id in {ids}'
        coll.delete(expr)
        coll.flush()
