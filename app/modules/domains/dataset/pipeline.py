""" pipeline

Document processing pipeline orchestration.
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.gateways.storage.interface import StorageGateway
from app.kernel.trace.writer import TraceWriter
from app.modules.domains.dataset.models import DatasetDocument, DatasetChunk, Dataset
from app.modules.domains.dataset.repository import (
    DatasetRepository,
    DocumentRepository,
    ChunkRepository,
)
from app.modules.domains.dataset.parsers import get_parser
from app.modules.domains.dataset.chunker import TextChunker
from app.modules.domains.dataset.embedding import EmbeddingService
from app.modules.domains.dataset.index_builder import IndexBuilder
from app.kernel.commons.time import utcnow as utc_now
from app.kernel.commons.errors import KernelError


class DocumentPipeline:
    """Document processing pipeline."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        storage_gateway: StorageGateway,
        trace_writer: TraceWriter,
        embedding_service: EmbeddingService,
        index_builder: IndexBuilder,
    ):
        """Initialize document pipeline.
        
        Args:
            db: Database session.
            ctx: Request context.
            storage_gateway: Storage gateway.
            trace_writer: Trace writer.
            embedding_service: Embedding service.
            index_builder: Index builder.
        """
        self.db = db
        self.ctx = ctx
        self.storage_gateway = storage_gateway
        self.trace_writer = trace_writer
        self.embedding_service = embedding_service
        self.index_builder = index_builder
        self.dataset_repo = DatasetRepository(db, ctx)
        self.document_repo = DocumentRepository(db, ctx)
        self.chunk_repo = ChunkRepository(db, ctx)
    
    async def process_document(
        self,
        document: DatasetDocument,
        dataset: Dataset,
        file_content: Optional[bytes] = None,
    ) -> DatasetDocument:
        """Process document through pipeline.
        
        Args:
            document: Document to process.
            dataset: Dataset instance.
            file_content: Optional file content (if None, load from storage).
            
        Returns:
            Updated document.
        """
        try:
            # Step 1: Parse document
            document.status = "parsing"
            document.updated_at = utc_now()
            self.db.commit()
            
            parsed_doc = await self._parse_document(document, file_content)
            
            document.status = "parsed"
            document.parse_meta_json = parsed_doc.metadata
            document.updated_at = utc_now()
            self.db.commit()
            
            # Step 2: Chunk document
            document.status = "chunking"
            document.updated_at = utc_now()
            self.db.commit()
            
            chunks = await self._chunk_document(document, dataset, parsed_doc.text)
            
            document.status = "chunked"
            document.updated_at = utc_now()
            self.db.commit()
            
            # Step 3: Generate embeddings and index
            document.status = "indexing"
            document.updated_at = utc_now()
            self.db.commit()
            
            await self._index_chunks(document, dataset, chunks)
            
            document.status = "indexed"
            document.updated_at = utc_now()
            self.db.commit()
            
            # Update dataset statistics
            self._update_dataset_stats(dataset)
            
            return document
            
        except Exception as e:
            # Mark document as failed
            document.status = "failed"
            document.error_code = "PIPELINE_ERROR"
            document.error_message = str(e)
            document.retry_count += 1
            document.updated_at = utc_now()
            self.db.commit()
            raise
    
    async def _parse_document(
        self,
        document: DatasetDocument,
        file_content: Optional[bytes],
    ) -> Any:
        """Parse document.
        
        Args:
            document: Document instance.
            file_content: Optional file content.
            
        Returns:
            ParsedDocument instance.
        """
        # Load file content if not provided
        if file_content is None:
            if not document.file_id:
                raise KernelError("NO_FILE", "Document has no file_id")
            
            # TODO: Load from storage gateway
            # For now, raise error
            raise KernelError("NOT_IMPLEMENTED", "File loading from storage not implemented")
        
        # Get parser
        mime_type = document.mime_type or "text/plain"
        parser_class = get_parser(mime_type)
        
        if not parser_class:
            raise KernelError("UNSUPPORTED_FORMAT", f"Unsupported MIME type: {mime_type}")
        
        parser = parser_class()
        parsed_doc = await parser.parse(
            content=file_content,
            mime_type=mime_type,
            filename=document.filename,
        )
        
        # Save parsed text to storage
        if parsed_doc.text:
            # TODO: Save to object storage and set raw_text_artifact_key
            pass
        
        return parsed_doc
    
    async def _chunk_document(
        self,
        document: DatasetDocument,
        dataset: Dataset,
        text: str,
    ) -> List[DatasetChunk]:
        """Chunk document text.
        
        Args:
            document: Document instance.
            dataset: Dataset instance.
            text: Document text.
            
        Returns:
            List of DatasetChunk instances.
        """
        # Get chunking config
        chunking_config = document.chunking_json or dataset.chunking_json or {}
        chunk_size = chunking_config.get("chunk_size", 1000)
        chunk_overlap = chunking_config.get("chunk_overlap", 200)
        separators = chunking_config.get("separators", None)
        
        # Create chunker
        chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
        )
        
        # Chunk text
        chunks = chunker.chunk(text)
        
        # Create DatasetChunk instances
        dataset_chunks = []
        for chunk in chunks:
            chunk_key = TextChunker.generate_chunk_key(
                document.doc_key,
                document.version,
                chunk.chunk_no,
            )
            content_hash = TextChunker.compute_content_hash(chunk.text)
            
            dataset_chunk = DatasetChunk(
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                dataset_id=document.dataset_id,
                document_id=document.id,
                document_version=document.version,
                chunk_no=chunk.chunk_no,
                chunk_key=chunk_key,
                content_hash=content_hash,
                text_preview=chunk.text[:512],  # Preview
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                page_no=chunk.page_no,
                section_path=chunk.section_path or [],
                char_count=len(chunk.text),
                index_status="pending",
            )
            
            # Save chunk text to storage
            # TODO: Save to object storage and set text_artifact_key
            
            dataset_chunks.append(dataset_chunk)
            self.db.add(dataset_chunk)
        
        self.db.commit()
        
        return dataset_chunks
    
    async def _index_chunks(
        self,
        document: DatasetDocument,
        dataset: Dataset,
        chunks: List[DatasetChunk],
    ) -> None:
        """Index chunks in vector database.
        
        Args:
            document: Document instance.
            dataset: Dataset instance.
            chunks: List of chunks to index.
        """
        # Get default index
        index_id = dataset.default_index_id
        if not index_id:
            # Try to get primary index
            from app.modules.domains.dataset.repository import IndexRepository
            index_repo = IndexRepository(self.db, self.ctx)
            index = index_repo.get_primary(dataset.id)
            if not index:
                raise KernelError("NO_INDEX", "Dataset has no index configured")
            index_id = index.id
        
        # Get index
        from app.modules.domains.dataset.repository import IndexRepository
        index_repo = IndexRepository(self.db, self.ctx)
            index = index_repo.get_by_id(index_id)
        if not index:
            raise KernelError("INDEX_NOT_FOUND", f"Index {index_id} not found")
        
        # Build index with these chunks
        await self.index_builder.build_index(index, chunks=chunks, incremental=True)
        
        # Update document index metadata
        document.index_meta_json = {
            "index_id": index_id,
            "chunk_count": len(chunks),
            "indexed_at": utc_now().isoformat(),
        }
    
    def _update_dataset_stats(self, dataset: Dataset) -> None:
        """Update dataset statistics.
        
        Args:
            dataset: Dataset instance.
        """
        # Count documents and chunks
        doc_count = self.document_repo.count_by_dataset(dataset.id)
        chunk_count = self.chunk_repo.count_by_dataset(dataset.id)
        
        # Update dataset
        self.dataset_repo.update_stats(
            dataset.id,
            doc_count=doc_count,
            chunk_count=chunk_count,
        )
