""" index_builder

Index builder service for vector database operations.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.vector.interface import VectorPort
from app.kernel.ports.storage.interface import StoragePort
from app.modules.dataset.domain.models import DatasetIndex, DatasetChunk
from app.modules.dataset.infra.repository import ChunkRepository
from app.modules.dataset.runtime.embedding import EmbeddingService
from app.kernel.commons.time import utc_now


class IndexBuilder:
    """Service for building vector indexes."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        vector_port: VectorPort,
        embedding_service: EmbeddingService,
        storage_port: Optional[StoragePort] = None,
    ):
        """Initialize index builder.
        
        Args:
            db: Database session.
            ctx: Request context.
            vector_port: Vector database gateway.
            embedding_service: Embedding service.
            storage_port: Optional storage gateway for loading chunk text.
        """
        self.db = db
        self.ctx = ctx
        self.vector_port = vector_port
        self.embedding_service = embedding_service
        self.storage_port = storage_port
        self.chunk_repo = ChunkRepository(db, ctx)
    
    async def create_collection(
        self,
        index: DatasetIndex,
    ) -> None:
        """Create collection in vector database.
        
        Args:
            index: Index configuration.
        """
        collection_name = index.collection_name or f"idx_{index.id}"
        index_ref = f"ds:{index.dataset_id}:{index.id}"
        
        # Create collection if not exists
        # Note: This is a placeholder - actual implementation depends on vector gateway
        # For Milvus, we would create collection with schema
        
        # Update index status
        index.status = "building"
        index.updated_at = utc_now()
        self.db.commit()
    
    async def build_index(
        self,
        index: DatasetIndex,
        chunks: Optional[List[DatasetChunk]] = None,
        incremental: bool = True,
    ) -> None:
        """Build or update index.
        
        Args:
            index: Index configuration.
            chunks: Optional list of chunks to index (if None, index all pending chunks).
            incremental: Whether this is an incremental update.
        """
        try:
            # Update status
            index.status = "building"
            index.updated_at = utc_now()
            self.db.commit()
            
            # Get chunks to index
            if chunks is None:
                if incremental:
                    # Get only pending chunks
                    chunks = self.chunk_repo.list_by_dataset(
                        index.dataset_id,
                        index_status="pending",
                        limit=10000,
                    )
                else:
                    # Get all chunks
                    chunks = self.chunk_repo.list_by_dataset(
                        index.dataset_id,
                        limit=10000,
                    )
            
            if not chunks:
                # No chunks to index
                index.status = "ready"
                index.updated_at = utc_now()
                self.db.commit()
                return
            
            # Generate embeddings
            texts = []
            chunk_ids = []
            for chunk in chunks:
                # Get chunk text (from artifact or preview)
                if chunk.text_artifact_key and self.storage_port:
                    # Load from object storage
                    try:
                        content = await self.storage_port.get(
                            storage_key=chunk.text_artifact_key,
                        )
                        text = content.decode("utf-8") if isinstance(content, bytes) else content
                    except Exception as e:
                        # Fallback to preview if storage load fails
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to load chunk text from storage: {str(e)}")
                        text = chunk.text_preview or ""
                else:
                    text = chunk.text_preview or ""
                
                if text:
                    texts.append(text)
                    chunk_ids.append(chunk.id)
            
            if not texts:
                index.status = "ready"
                index.updated_at = utc_now()
                self.db.commit()
                return
            
            # Generate embeddings
            embeddings = await self.embedding_service.embed_batch(
                texts=texts,
                model_ref=index.embedding_model_ref,
            )
            
            # Prepare vectors for insertion
            vectors = []
            for i, (chunk_id, embedding) in enumerate(zip(chunk_ids, embeddings)):
                vectors.append({
                    "id": chunk_id,
                    "vector": embedding,
                    "metadata": {
                        "chunk_id": chunk_id,
                        "dataset_id": index.dataset_id,
                        "document_id": chunks[i].document_id,
                    },
                })
            
            # Insert vectors
            index_ref = f"ds:{index.dataset_id}:{index.id}"
            collection_name = index.collection_name or f"idx_{index.id}"
            
            # Extract IDs and vectors from vector data
            vector_ids = [v["id"] for v in vectors]
            vector_embeddings = [v["vector"] for v in vectors]
            vector_metadata = [v.get("metadata", {}) for v in vectors]
            
            await self.vector_port.insert(
                collection=collection_name,
                vectors=vector_embeddings,
                ids=vector_ids,
                metadata=vector_metadata,
                index_ref=index_ref,
            )
            
            # Update chunk vector_refs and status
            for chunk, vector_data in zip(chunks, vectors):
                chunk.vector_ref = vector_data["id"]
                chunk.index_status = "indexed"
                chunk.indexed_at = utc_now()
                chunk.embedding_model_ref = index.embedding_model_ref
            
            # Update index statistics
            index.vector_count = len(vectors)
            index.chunk_count = len(chunks)
            index.status = "ready"
            index.last_build_at = utc_now()
            if not incremental:
                index.build_version += 1
            
            self.db.commit()
            
        except Exception as e:
            # Update status to failed
            index.status = "failed"
            index.last_error_code = "BUILD_ERROR"
            index.last_error_message = str(e)
            index.updated_at = utc_now()
            self.db.commit()
            raise
    
    async def rebuild_index(
        self,
        index: DatasetIndex,
    ) -> None:
        """Rebuild index from scratch.
        
        Args:
            index: Index configuration.
        """
        await self.build_index(index, incremental=False)

