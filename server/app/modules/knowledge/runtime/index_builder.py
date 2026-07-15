""" index_builder

Index builder service for vector database operations.
"""


from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.vector.interface import VectorPort
from app.modules.knowledge.domain.models import KnowledgeChunk, KnowledgeIndex
from app.modules.knowledge.infra.repository import ChunkRepository
from app.modules.knowledge.runtime.embedding import EmbeddingService


class IndexBuilder:
    """Service for building vector indexes."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        vector_port: VectorPort,
        embedding_service: EmbeddingService,
        storage_port: StoragePort | None = None,
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
        index: KnowledgeIndex,
        run_id: str | None = None,
    ) -> None:
        """Create collection in vector database.

        Args:
            index: Index configuration.
        """
        collection_name = index.collection_name or f"idx_{index.id}"
        index_ref = f"knowledge:{index.knowledge_id}:{index.id}"

        await self.vector_port.ensure_collection(
            collection=collection_name,
            dimension=index.dimension,
            metric_type=index.metric_type or "cosine",
            metadata_schema={
                "knowledge_id": "string",
                "document_id": "string",
                "chunk_id": "string",
            },
            index_ref=index_ref,
            run_id=run_id,
        )

        # Update index status
        index.status = "building"
        index.updated_at = utc_now()
        self.db.commit()

    async def build_index(
        self,
        index: KnowledgeIndex,
        chunks: list[KnowledgeChunk] | None = None,
        incremental: bool = True,
        run_id: str | None = None,
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
            if run_id:
                index.last_run_id = run_id
            index.updated_at = utc_now()
            self.db.commit()

            # Get chunks to index
            if chunks is None:
                if incremental:
                    # Get only pending chunks
                    chunks = self.chunk_repo.list_by_knowledge(
                        index.knowledge_id,
                        index_status="pending",
                        limit=10000,
                    )
                else:
                    # Get all chunks
                    chunks = self.chunk_repo.list_by_knowledge(
                        index.knowledge_id,
                        limit=10000,
                    )

            if not chunks:
                # No chunks to index
                index.status = "ready"
                index.last_build_at = utc_now()
                index.last_error_code = None
                index.last_error_message = None
                index.updated_at = utc_now()
                self.db.commit()
                return

            # Generate embeddings
            texts = []
            indexed_chunks = []
            for chunk in chunks:
                # Get chunk text (from artifact or preview)
                if chunk.text_artifact_key and self.storage_port:
                    # Load from object storage
                    try:
                        content = await self.storage_port.get(
                            key=chunk.text_artifact_key,
                            run_id=run_id,
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
                    indexed_chunks.append(chunk)

            if not texts:
                index.status = "ready"
                index.last_build_at = utc_now()
                index.last_error_code = None
                index.last_error_message = None
                index.updated_at = utc_now()
                self.db.commit()
                return

            # Generate embeddings
            embeddings = await self.embedding_service.embed_batch(
                texts=texts,
                model_ref=index.embedding_model_ref,
                run_id=run_id,
            )

            if index.dimension == 0 and embeddings:
                index.dimension = len(embeddings[0])

            # Prepare vectors for insertion
            vectors = []
            for chunk, embedding in zip(indexed_chunks, embeddings, strict=False):
                chunk_id = chunk.id
                vectors.append({
                    "id": chunk_id,
                    "vector": embedding,
                    "metadata": {
                        "chunk_id": chunk_id,
                        "knowledge_id": index.knowledge_id,
                        "document_id": chunk.document_id,
                        "text_preview": chunk.text_preview,
                    },
                })

            # Insert vectors
            index_ref = f"knowledge:{index.knowledge_id}:{index.id}"
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
                run_id=run_id,
            )

            # Update chunk vector_refs and status
            for chunk, vector_data in zip(indexed_chunks, vectors, strict=False):
                chunk.vector_ref = vector_data["id"]
                chunk.index_status = "indexed"
                chunk.indexed_at = utc_now()
                chunk.embedding_model_ref = index.embedding_model_ref

            # Update index statistics
            index.vector_count = len(vectors)
            index.chunk_count = len(indexed_chunks)
            index.doc_count = len({chunk.document_id for chunk in indexed_chunks})
            index.status = "ready"
            index.last_build_at = utc_now()
            index.last_error_code = None
            index.last_error_message = None
            if not incremental:
                index.build_version += 1

            self.db.commit()

        except Exception as e:
            # Update status to failed
            index.status = "failed"
            if run_id:
                index.last_run_id = run_id
            index.last_error_code = "BUILD_ERROR"
            index.last_error_message = str(e)
            index.updated_at = utc_now()
            self.db.commit()
            raise

    async def rebuild_index(
        self,
        index: KnowledgeIndex,
        run_id: str | None = None,
    ) -> None:
        """Rebuild index from scratch.

        Args:
            index: Index configuration.
        """
        # Delete existing vectors
        chunks = self.chunk_repo.list_by_knowledge(
            index.knowledge_id,
            limit=10000,
        )
        vector_ids = [chunk.vector_ref or chunk.id for chunk in chunks]
        collection_name = index.collection_name or f"idx_{index.id}"
        if vector_ids:
            await self.vector_port.delete(
                collection=collection_name,
                ids=vector_ids,
                run_id=run_id,
            )

        for chunk in chunks:
            chunk.index_status = "pending"
            chunk.indexed_at = None
            chunk.vector_ref = None

        self.db.commit()

        await self.build_index(index, chunks=chunks, incremental=False, run_id=run_id)

