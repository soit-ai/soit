""" retrieval

Retrieval service for querying vector database.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.vector.interface import VectorPort
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.storage.interface import StoragePort
from app.modules.dataset.domain.models import DatasetIndex, DatasetChunk
from app.modules.dataset.infrastructure.repository import IndexRepository, ChunkRepository
from app.modules.dataset.runtime.embedding import EmbeddingService
from app.modules.dataset.application.schemas import QueryResult


class RetrievalService:
    """Service for retrieving documents from vector database."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        vector_port: VectorPort,
        llm_port: LLMPort,
        embedding_service: EmbeddingService,
        storage_port: Optional[StoragePort] = None,
    ):
        """Initialize retrieval service.
        
        Args:
            db: Database session.
            ctx: Request context.
            vector_port: Vector database gateway.
            llm_port: LLM gateway (for reranking).
            embedding_service: Embedding service.
            storage_port: Optional storage gateway for loading chunk text.
        """
        self.db = db
        self.ctx = ctx
        self.vector_port = vector_port
        self.llm_port = llm_port
        self.embedding_service = embedding_service
        self.storage_port = storage_port
        self.index_repo = IndexRepository(db, ctx)
        self.chunk_repo = ChunkRepository(db, ctx)
    
    async def query(
        self,
        dataset_id: str,
        query_text: str,
        top_k: int = 10,
        index_id: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
        use_rerank: bool = False,
        reranker_ref: Optional[str] = None,
    ) -> List[QueryResult]:
        """Query dataset for relevant documents.
        
        Args:
            dataset_id: Dataset ID.
            query_text: Query text.
            top_k: Number of results.
            index_id: Optional index ID (use primary if not specified).
            filter: Optional metadata filter.
            use_rerank: Whether to use reranking.
            reranker_ref: Optional reranker reference.
            
        Returns:
            List of QueryResult instances.
        """
        # Get index
        if index_id:
            index = self.index_repo.get_by_id(index_id)
        else:
            index = self.index_repo.get_primary(dataset_id)
        
        if not index:
            raise ValueError(f"No index found for dataset {dataset_id}")
        
        if index.status != "ready":
            raise ValueError(f"Index {index.id} is not ready (status: {index.status})")
        
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_text(
            text=query_text,
            model_ref=index.embedding_model_ref,
        )
        
        # Query vector database
        index_ref = f"ds:{dataset_id}:{index.id}"
        results = await self.vector_port.search(
            index_ref=index_ref,
            query_vector=query_embedding,
            top_k=top_k,
            **({"filter": filter} if filter else {}),
        )
        
        # Convert to QueryResult
        query_results = []
        for result in results:
            chunk_id = result.get("id") or result.get("chunk_id")
            if not chunk_id:
                continue
            
            chunk = self.chunk_repo.get_by_id(chunk_id)
            if not chunk:
                continue
            
            # Get chunk text
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
            
            query_results.append(
                QueryResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    score=result.get("score", 0.0),
                    text=text,
                    metadata={
                        "chunk_no": chunk.chunk_no,
                        "page_no": chunk.page_no,
                        "section_path": chunk.section_path,
                    },
                )
            )
        
        # Rerank if requested
        if use_rerank and query_results:
            reranker_model = reranker_ref or index.reranker_ref
            if reranker_model:
                documents = [r.text for r in query_results]
                reranked = await self.llm_port.rerank(
                    model_ref=reranker_model,
                    query=query_text,
                    documents=documents,
                    top_n=top_k,
                )
                
                # Reorder results based on reranking
                reranked_map = {doc["document"]: doc for doc in reranked}
                reranked_results = []
                for result in query_results:
                    if result.text in reranked_map:
                        reranked_item = reranked_map[result.text]
                        result.score = reranked_item.get("score", result.score)
                        reranked_results.append(result)
                
                # Sort by score descending
                reranked_results.sort(key=lambda x: x.score, reverse=True)
                query_results = reranked_results[:top_k]
        
        return query_results
    
    async def query_multiple_indexes(
        self,
        dataset_id: str,
        query_text: str,
        index_ids: List[str],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[QueryResult]:
        """Query multiple indexes and merge results.
        
        Args:
            dataset_id: Dataset ID.
            query_text: Query text.
            index_ids: List of index IDs.
            top_k: Number of results per index.
            filter: Optional metadata filter.
            
        Returns:
            Merged list of QueryResult instances.
        """
        all_results = []
        
        for index_id in index_ids:
            results = await self.query(
                dataset_id=dataset_id,
                query_text=query_text,
                top_k=top_k,
                index_id=index_id,
                filter=filter,
                use_rerank=False,
            )
            all_results.extend(results)
        
        # Deduplicate by chunk_id and sort by score
        seen = set()
        unique_results = []
        for result in all_results:
            if result.chunk_id not in seen:
                seen.add(result.chunk_id)
                unique_results.append(result)
        
        # Sort by score descending
        unique_results.sort(key=lambda x: x.score, reverse=True)
        
        return unique_results[:top_k]

