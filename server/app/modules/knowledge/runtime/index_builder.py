""" index_builder

Index builder service for vector database operations.
"""


import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.vector.interface import VectorPort
from app.modules.knowledge.domain.models import KnowledgeChunk, KnowledgeIndex
from app.modules.knowledge.infra.repository import (
    CHUNK_SCAN_BATCH_SIZE,
    ChunkRepository,
)
from app.modules.knowledge.runtime.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class IndexBuilder:
    """Service for building vector indexes."""

    def __init__(
        self,
        db: AsyncSession,
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
        await self.db.commit()

    async def build_index(
        self,
        index: KnowledgeIndex,
        chunks: list[KnowledgeChunk] | None = None,
        incremental: bool = True,
        run_id: str | None = None,
    ) -> None:
        """Build or update index.

        Chunks are embedded and written in bounded batches, so a knowledge
        base of any size is indexed completely.

        Args:
            index: Index configuration.
            chunks: Optional list of chunks to index (if None, scan the knowledge base).
            incremental: When scanning, index only pending chunks.
        """
        try:
            index.status = "building"
            if run_id:
                index.last_run_id = run_id
            index.updated_at = utc_now()
            await self.db.commit()

            if chunks is not None:
                for start in range(0, len(chunks), CHUNK_SCAN_BATCH_SIZE):
                    await self._index_batch(index, chunks[start:start + CHUNK_SCAN_BATCH_SIZE], run_id)
            else:
                async for batch in self.chunk_repo.iter_batches(
                    knowledge_id=index.knowledge_id,
                    index_status="pending" if incremental else None,
                ):
                    await self._index_batch(index, batch, run_id)

            chunk_count, doc_count = await self.chunk_repo.indexed_stats(index.knowledge_id)
            index.vector_count = chunk_count
            index.chunk_count = chunk_count
            index.doc_count = doc_count
            index.status = "ready"
            index.last_build_at = utc_now()
            index.last_error_code = None
            index.last_error_message = None
            index.updated_at = utc_now()
            if not incremental:
                index.build_version += 1

            await self.db.commit()

        except Exception as e:
            index.status = "failed"
            if run_id:
                index.last_run_id = run_id
            index.last_error_code = "BUILD_ERROR"
            index.last_error_message = str(e)
            index.updated_at = utc_now()
            await self.db.commit()
            raise

    async def _index_batch(
        self,
        index: KnowledgeIndex,
        chunks: list[KnowledgeChunk],
        run_id: str | None,
    ) -> None:
        """Embed one batch of chunks, write the vectors and mark the chunks indexed."""
        texts: list[str] = []
        indexed_chunks: list[KnowledgeChunk] = []
        for chunk in chunks:
            if chunk.text_artifact_key and self.storage_port:
                try:
                    content = await self.storage_port.get(
                        key=chunk.text_artifact_key,
                        run_id=run_id,
                    )
                    text = content.decode("utf-8") if isinstance(content, bytes) else content
                except Exception as e:
                    # Fall back to the stored preview when object storage is unavailable.
                    logger.warning("Failed to load chunk text from storage: %s", e)
                    text = chunk.text_preview or ""
            else:
                text = chunk.text_preview or ""

            if text:
                texts.append(text)
                indexed_chunks.append(chunk)

        if not texts:
            return

        embeddings = await self.embedding_service.embed_batch(
            texts=texts,
            model_ref=index.embedding_model_ref,
            run_id=run_id,
        )

        if index.dimension == 0 and embeddings:
            index.dimension = len(embeddings[0])

        await self.vector_port.insert(
            collection=index.collection_name or f"idx_{index.id}",
            vectors=list(embeddings),
            ids=[chunk.id for chunk in indexed_chunks],
            metadata=[
                {
                    "chunk_id": chunk.id,
                    "knowledge_id": index.knowledge_id,
                    "document_id": chunk.document_id,
                    "text_preview": chunk.text_preview,
                }
                for chunk in indexed_chunks
            ],
            index_ref=f"knowledge:{index.knowledge_id}:{index.id}",
            run_id=run_id,
        )

        indexed_at = utc_now()
        for chunk in indexed_chunks:
            chunk.vector_ref = chunk.id
            chunk.index_status = "indexed"
            chunk.indexed_at = indexed_at
            chunk.embedding_model_ref = index.embedding_model_ref

        await self.db.commit()

    async def rebuild_index(
        self,
        index: KnowledgeIndex,
        run_id: str | None = None,
    ) -> None:
        """Rebuild index from scratch.

        Args:
            index: Index configuration.
        """
        collection_name = index.collection_name or f"idx_{index.id}"
        async for batch in self.chunk_repo.iter_batches(knowledge_id=index.knowledge_id):
            vector_ids = [chunk.vector_ref or chunk.id for chunk in batch]
            if vector_ids:
                await self.vector_port.delete(
                    collection=collection_name,
                    ids=vector_ids,
                    run_id=run_id,
                )
            for chunk in batch:
                chunk.index_status = "pending"
                chunk.indexed_at = None
                chunk.vector_ref = None
            await self.db.commit()

        await self.build_index(index, chunks=None, incremental=False, run_id=run_id)
