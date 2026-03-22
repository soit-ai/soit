""" pipeline

Document processing pipeline orchestration.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.trace.writer import TraceWriter
from app.modules.knowledge.domain.models import KnowledgeDocument, KnowledgeChunk, Knowledge
from app.modules.knowledge.infra.repository import (
    KnowledgeRepository,
    DocumentRepository,
    ChunkRepository,
)
from app.modules.knowledge.infra.parsers import get_parser
from app.modules.knowledge.application.chunker import TextChunker
from app.modules.knowledge.runtime.embedding import EmbeddingService
from app.modules.knowledge.runtime.index_builder import IndexBuilder
from app.kernel.commons.time import utc_now
from app.kernel.commons.errors import KernelError


class DocumentPipeline:
    """Document processing pipeline."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        storage_port: StoragePort,
        trace_writer: TraceWriter,
        embedding_service: EmbeddingService,
        index_builder: IndexBuilder,
    ):
        """Initialize document pipeline.
        
        Args:
            db: Database session.
            ctx: Request context.
            storage_port: Storage gateway.
            trace_writer: Trace writer.
            embedding_service: Embedding service.
            index_builder: Index builder.
        """
        self.db = db
        self.ctx = ctx
        self.storage_port = storage_port
        self.trace_writer = trace_writer
        self.embedding_service = embedding_service
        self.index_builder = index_builder
        self.knowledge_repo = KnowledgeRepository(db, ctx)
        self.document_repo = DocumentRepository(db, ctx)
        self.chunk_repo = ChunkRepository(db, ctx)
    
    async def process_document(
        self,
        document: KnowledgeDocument,
        knowledge: Knowledge,
        file_content: Optional[bytes] = None,
        run_id: Optional[str] = None,
    ) -> KnowledgeDocument:
        """Process document through pipeline.
        
        Args:
            document: Document to process.
            knowledge: Knowledge instance.
            file_content: Optional file content (if None, load from storage).
            
        Returns:
            Updated document.
        """
        try:
            # Step 1: Parse document
            document.status = "parsing"
            document.updated_at = utc_now()
            self.db.commit()

            parse_step_id = None
            if run_id:
                parse_step = self.trace_writer.create_step(
                    run_id=run_id,
                    step_type="io",
                    step_id="parse",
                    input_summary=f"document_id={document.id}",
                )
                parse_step_id = parse_step.id
                self.trace_writer.update_step_status(parse_step_id, "running")

            parsed_doc = await self._parse_document(document, file_content, run_id=run_id)

            document.status = "parsed"
            document.parse_meta_json = parsed_doc.metadata
            document.updated_at = utc_now()
            self.db.commit()

            if parse_step_id:
                self.trace_writer.update_step_status(
                    parse_step_id,
                    "succeeded",
                    output_summary=f"chars={len(parsed_doc.text)}",
                )
            
            # Step 2: Chunk document
            document.status = "chunking"
            document.updated_at = utc_now()
            self.db.commit()

            chunk_step_id = None
            if run_id:
                chunk_step = self.trace_writer.create_step(
                    run_id=run_id,
                    step_type="io",
                    step_id="chunk",
                    input_summary=f"document_id={document.id}",
                )
                chunk_step_id = chunk_step.id
                self.trace_writer.update_step_status(chunk_step_id, "running")

            chunks = await self._chunk_document(document, knowledge, parsed_doc.text, run_id=run_id)

            document.status = "chunked"
            document.updated_at = utc_now()
            self.db.commit()

            if chunk_step_id:
                self.trace_writer.update_step_status(
                    chunk_step_id,
                    "succeeded",
                    output_summary=f"chunks={len(chunks)}",
                )
            
            # Step 3: Generate embeddings and index
            document.status = "indexing"
            document.updated_at = utc_now()
            self.db.commit()

            index_step_id = None
            if run_id:
                index_step = self.trace_writer.create_step(
                    run_id=run_id,
                    step_type="io",
                    step_id="index",
                    input_summary=f"document_id={document.id}",
                )
                index_step_id = index_step.id
                self.trace_writer.update_step_status(index_step_id, "running")

            await self._index_chunks(document, knowledge, chunks, run_id=run_id)

            document.status = "indexed"
            document.updated_at = utc_now()
            self.db.commit()

            if index_step_id:
                self.trace_writer.update_step_status(
                    index_step_id,
                    "succeeded",
                    output_summary=f"vectors={len(chunks)}",
                )
            
            # Update knowledge statistics
            self._update_knowledge_stats(knowledge)
            
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
        document: KnowledgeDocument,
        file_content: Optional[bytes],
        run_id: Optional[str] = None,
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
            
            # Load from storage gateway
            try:
                file_content = await self.storage_port.get(
                    key=document.file_id,
                    run_id=run_id,
                )
            except Exception as e:
                raise KernelError("STORAGE_ERROR", f"Failed to load file from storage: {str(e)}")
        
        # Get parser
        mime_type = document.mime_type or "text/plain"
        parser_class = get_parser(mime_type)
        if not parser_class:
            from app.modules.knowledge.infra.parsers.text import TextParser
            parser_class = TextParser
        
        parser = parser_class()
        parsed_doc = await parser.parse(
            content=file_content,
            mime_type=mime_type,
            filename=document.filename,
        )
        
        # Save parsed text to storage
        if parsed_doc.text:
            try:
                # Generate storage key for parsed text
                from app.kernel.commons.ids import generate_ulid
                storage_key = f"knowledge/{document.knowledge_id}/documents/{document.id}/parsed_{generate_ulid()}.txt"
                
                # Save to object storage
                await self.storage_port.put(
                    key=storage_key,
                    data=parsed_doc.text.encode("utf-8"),
                    content_type="text/plain",
                    run_id=run_id,
                )
                
                # Set artifact key
                document.raw_text_artifact_key = storage_key
            except Exception as e:
                # Log error but continue processing
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to save parsed text to storage: {str(e)}")
        
        if parsed_doc.structured_data:
            try:
                from app.kernel.commons.ids import generate_ulid
                import json
                storage_key = f"knowledge/{document.knowledge_id}/documents/{document.id}/parsed_{generate_ulid()}.json"
                await self.storage_port.put(
                    key=storage_key,
                    data=json.dumps(parsed_doc.structured_data).encode("utf-8"),
                    content_type="application/json",
                    run_id=run_id,
                )
                document.parsed_artifact_key = storage_key
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to save parsed data to storage: {str(e)}")

        if parsed_doc.metadata.get("title") and not document.title:
            document.title = parsed_doc.metadata["title"]

        return parsed_doc
    
    async def _chunk_document(
        self,
        document: KnowledgeDocument,
        knowledge: Knowledge,
        text: str,
        run_id: Optional[str] = None,
    ) -> List[KnowledgeChunk]:
        """Chunk document text.
        
        Args:
            document: Document instance.
            knowledge: Knowledge instance.
            text: Document text.
            
        Returns:
            List of KnowledgeChunk instances.
        """
        # Get chunking config
        chunking_config = document.chunking_json or knowledge.chunking_json or {}
        document.chunking_json = chunking_config
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
        
        # Create KnowledgeChunk instances
        knowledge_chunks = []
        for chunk in chunks:
            chunk_key = TextChunker.generate_chunk_key(
                document.doc_key,
                document.version,
                chunk.chunk_no,
            )
            content_hash = TextChunker.compute_content_hash(chunk.text)
            
            knowledge_chunk = KnowledgeChunk(
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                knowledge_id=document.knowledge_id,
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
                token_count=len(chunk.text.split()),
                index_status="pending",
            )
            
            # Save chunk text to storage
            try:
                # Generate storage key for chunk text
                from app.kernel.commons.ids import generate_ulid
                storage_key = f"knowledge/{document.knowledge_id}/documents/{document.id}/chunks/{chunk.chunk_no}_{generate_ulid()}.txt"
                
                # Save to object storage
                await self.storage_port.put(
                    key=storage_key,
                    data=chunk.text.encode("utf-8"),
                    content_type="text/plain",
                    run_id=run_id,
                )
                
                # Set artifact key
                knowledge_chunk.text_artifact_key = storage_key
            except Exception as e:
                # Log error but continue processing
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to save chunk text to storage: {str(e)}")
            
            knowledge_chunks.append(knowledge_chunk)
            self.db.add(knowledge_chunk)
        
        self.db.commit()
        
        return knowledge_chunks
    
    async def _index_chunks(
        self,
        document: KnowledgeDocument,
        knowledge: Knowledge,
        chunks: List[KnowledgeChunk],
        run_id: Optional[str] = None,
    ) -> None:
        """Index chunks in vector database.
        
        Args:
            document: Document instance.
            knowledge: Knowledge instance.
            chunks: List of chunks to index.
        """
        # Get default index
        index_id = knowledge.default_index_id
        if not index_id:
            # Try to get primary index
            from app.modules.knowledge.infra.repository import IndexRepository
            index_repo = IndexRepository(self.db, self.ctx)
            index = index_repo.get_primary(knowledge.id)
            if not index:
                raise KernelError("NO_INDEX", "Knowledge has no index configured")
            index_id = index.id
        
        # Get index
        from app.modules.knowledge.infra.repository import IndexRepository
        index_repo = IndexRepository(self.db, self.ctx)
        index = index_repo.get_by_id(index_id)
        if not index:
            raise KernelError("INDEX_NOT_FOUND", f"Index {index_id} not found")
        
        # Build index with these chunks
        await self.index_builder.build_index(
            index,
            chunks=chunks,
            incremental=True,
            run_id=run_id,
        )
        
        # Update document index metadata
        document.index_meta_json = {
            "index_id": index_id,
            "chunk_count": len(chunks),
            "indexed_at": utc_now().isoformat(),
        }
    
    def _update_knowledge_stats(self, knowledge: Knowledge) -> None:
        """Update knowledge statistics.
        
        Args:
            knowledge: Knowledge instance.
        """
        # Count documents and chunks
        doc_count = self.document_repo.count_by_knowledge(knowledge.id)
        chunk_count = self.chunk_repo.count_by_knowledge(knowledge.id)
        
        # Update knowledge
        self.knowledge_repo.update_stats(
            knowledge.id,
            doc_count=doc_count,
            chunk_count=chunk_count,
            last_indexed_at=utc_now(),
        )
