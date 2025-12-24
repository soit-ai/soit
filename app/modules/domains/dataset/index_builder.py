""" index_builder

Index builder service for vector database operations.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.gateways.vector.interface import VectorGateway
from app.modules.domains.dataset.models import DatasetIndex, DatasetChunk
from app.modules.domains.dataset.repository import ChunkRepository
from app.modules.domains.dataset.embedding import EmbeddingService
from app.kernel.commons.time import utcnow as utc_now


class IndexBuilder:
    """Service for building vector indexes."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        vector_gateway: VectorGateway,
        embedding_service: EmbeddingService,
    ):
        """Initialize index builder.
        
        Args:
            db: Database session.
            ctx: Request context.
            vector_gateway: Vector database gateway.
            embedding_service: Embedding service.
        """
        self.db = db
        self.ctx = ctx
        self.vector_gateway = vector_gateway
        self.embedding_service = embedding_service
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
                if chunk.text_artifact_key:
                    # TODO: Load from object storage
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
            await self.vector_gateway.insert(
                index_ref=index_ref,
                vectors=vectors,
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

