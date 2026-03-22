""" milvus_vector

Milvus vector gateway adapter implementation.
"""

from typing import List, Dict, Any, Optional
import hashlib
import json
import re
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility

from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult
from app.settings.settings import settings


class MilvusVectorPort(VectorPort):
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

    def _ensure_collection(
        self,
        collection_name: str,
        dimension: int,
        include_metadata: bool,
    ) -> Collection:
        """Ensure collection exists with expected schema."""
        normalized = self._normalize_collection_name(collection_name)
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
            index_params={"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 1024}},
        )
        return coll
    
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
        collection_name = self._normalize_collection_name(collection)
        if not utility.has_collection(collection_name):
            return VectorQueryResult(ids=[], scores=[])

        coll = Collection(collection_name)
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
        collection_name = self._normalize_collection_name(kwargs.get("index_ref", collection))
        
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
        
        collection_name = self._normalize_collection_name(collection)
        coll = Collection(collection_name)
        coll.load()
        
        # Delete by IDs
        # Milvus delete expects a filter expression or list of IDs
        # For Milvus 2.x, we use delete with expr
        expr = f'id in {ids}'
        coll.delete(expr)
        coll.flush()
