""" retrieval

Retrieval service for querying vector database.
"""

import re
from typing import Any

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.vector.interface import VectorPort
from app.modules.knowledge.application.runtime_schemas import QueryResult
from app.modules.knowledge.domain.models import KnowledgeChunk
from app.modules.knowledge.infra.repository import (
    ChunkRepository,
    DocumentRepository,
    IndexRepository,
)
from app.modules.knowledge.runtime.embedding import EmbeddingService


class RetrievalService:
    """Service for retrieving documents from vector database."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        vector_port: VectorPort,
        llm_port: LLMPort,
        embedding_service: EmbeddingService,
        storage_port: StoragePort | None = None,
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
        self.document_repo = DocumentRepository(db, ctx)

    def _tokenize_query(self, query_text: str) -> list[str]:
        """Split query text into tokens for keyword scoring."""
        tokens = [token.strip() for token in re.split(r"\s+", query_text or "") if token.strip()]
        if not tokens and query_text:
            return [query_text.strip()]
        return tokens

    def _keyword_score(self, text: str, tokens: list[str]) -> int:
        """Compute a simple keyword score for text."""
        if not text or not tokens:
            return 0
        haystack = text.lower()
        score = 0
        for token in tokens:
            score += haystack.count(token.lower())
        return score

    async def _load_chunk_text(
        self,
        chunk: KnowledgeChunk,
        run_id: str | None,
        prefer_full_text: bool = True,
    ) -> str:
        """Load chunk text with optional full text preference."""
        if prefer_full_text and chunk.text_artifact_key and self.storage_port:
            try:
                content = await self.storage_port.get(
                    key=chunk.text_artifact_key,
                    run_id=run_id,
                )
                if isinstance(content, bytes):
                    return content.decode("utf-8")
                return content or ""
            except Exception as exc:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("Failed to load chunk text from storage: %s", exc)
        if chunk.text_preview:
            return chunk.text_preview
        if chunk.text_artifact_key and self.storage_port:
            try:
                content = await self.storage_port.get(
                    key=chunk.text_artifact_key,
                    run_id=run_id,
                )
                if isinstance(content, bytes):
                    return content.decode("utf-8")
                return content or ""
            except Exception as exc:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("Failed to load chunk text from storage: %s", exc)
        return ""

    def _build_metadata(
        self,
        knowledge_id: str,
        chunk: KnowledgeChunk,
        document,
    ) -> dict[str, Any]:
        """Build metadata payload for query results."""
        return {
            "chunk_no": chunk.chunk_no,
            "page_no": chunk.page_no,
            "section_path": chunk.section_path,
            "doc_key": document.doc_key if document else None,
            "title": document.title if document else None,
            "source_uri": document.source_uri if document else None,
            "knowledge_id": knowledge_id,
            "document_version": chunk.document_version,
            "chunk_key": chunk.chunk_key,
            "start_offset": chunk.start_offset,
            "end_offset": chunk.end_offset,
            "source_meta": chunk.source_meta_json or {},
        }

    async def query(
        self,
        knowledge_id: str,
        query_text: str,
        top_k: int = 10,
        index_id: str | None = None,
        filter: dict[str, Any] | None = None,
        use_rerank: bool = False,
        reranker_ref: str | None = None,
        run_id: str | None = None,
    ) -> list[QueryResult]:
        """Query a knowledge base for relevant documents.

        Args:
            knowledge_id: Knowledge ID.
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
            index = self.index_repo.get_primary(knowledge_id)

        if not index:
            raise ValueError(f"No index found for knowledge {knowledge_id}")

        if index.status != "ready":
            raise ValueError(f"Index {index.id} is not ready (status: {index.status})")

        # Generate query embedding
        query_embedding = await self.embedding_service.embed_text(
            text=query_text,
            model_ref=index.embedding_model_ref,
            run_id=run_id,
        )

        # Query vector database
        collection_name = index.collection_name or f"idx_{index.id}"
        results = await self.vector_port.query(
            collection=collection_name,
            vector=query_embedding,
            top_k=top_k,
            filter=filter,
            include_metadata=True,
            run_id=run_id,
        )

        # Convert to QueryResult
        query_results = []
        for chunk_id, score in zip(results.ids, results.scores, strict=False):
            chunk = self.chunk_repo.get_by_id(chunk_id)
            if not chunk or chunk.index_status != "indexed":
                continue
            document = self.document_repo.get_by_id(chunk.document_id)
            if not document or not document.is_latest:
                continue

            text = await self._load_chunk_text(chunk, run_id, prefer_full_text=True)

            metadata = self._build_metadata(knowledge_id, chunk, document)
            metadata["vector_score"] = score
            query_results.append(
                QueryResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    score=score,
                    text=text,
                    metadata=metadata,
                )
            )

        # Rerank if requested
        if use_rerank and query_results:
            reranker_model = reranker_ref or index.reranker_ref
            if reranker_model:
                documents = [r.text for r in query_results]
                reranked = await self.llm_port.rerank(
                    model=reranker_model,
                    query=query_text,
                    documents=documents,
                    top_n=top_k,
                    run_id=run_id,
                )

                # Reorder results based on reranking
                reranked_map = {doc["document"]: doc for doc in reranked.results}
                reranked_results = []
                for result in query_results:
                    if result.text in reranked_map:
                        reranked_item = reranked_map[result.text]
                        result.score = reranked_item.get("score", result.score)
                        result.metadata["rerank_score"] = result.score
                        reranked_results.append(result)

                # Sort by score descending
                reranked_results.sort(key=lambda x: x.score, reverse=True)
                query_results = reranked_results[:top_k]

        return query_results

    async def query_keyword(
        self,
        knowledge_id: str,
        query_text: str,
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
        run_id: str | None = None,
        candidate_limit: int = 500,
        min_score: int = 1,
    ) -> list[QueryResult]:
        """Keyword-based retrieval over chunk text previews."""
        tokens = self._tokenize_query(query_text)
        if not tokens:
            return []

        chunks = self.chunk_repo.list_by_knowledge(
            knowledge_id=knowledge_id,
            index_status="indexed",
            limit=candidate_limit,
            offset=0,
        )
        if not chunks:
            return []

        results: list[QueryResult] = []
        document_cache: dict[str, Any] = {}
        for chunk in chunks:
            document = document_cache.get(chunk.document_id)
            if document is None:
                document = self.document_repo.get_by_id(chunk.document_id)
                document_cache[chunk.document_id] = document
            if not document or not document.is_latest:
                continue

            text = chunk.text_preview or ""
            if not text and chunk.text_artifact_key and self.storage_port:
                text = await self._load_chunk_text(chunk, run_id, prefer_full_text=True)
            if not text:
                continue

            score = self._keyword_score(text, tokens)
            if score < min_score:
                continue

            metadata = self._build_metadata(knowledge_id, chunk, document)
            if filter:
                if not self._passes_filter(metadata, filter):
                    continue

            results.append(
                QueryResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    score=float(score),
                    text=text,
                    metadata=metadata,
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    async def query_hybrid(
        self,
        knowledge_id: str,
        query_text: str,
        top_k: int = 10,
        index_id: str | None = None,
        filter: dict[str, Any] | None = None,
        use_rerank: bool = False,
        reranker_ref: str | None = None,
        run_id: str | None = None,
        candidate_limit: int = 500,
        min_score: int = 1,
        alpha: float = 0.7,
        keyword_top_k: int | None = None,
    ) -> list[QueryResult]:
        """Hybrid retrieval combining vector and keyword scores."""
        vector_results = await self.query(
            knowledge_id=knowledge_id,
            query_text=query_text,
            top_k=top_k,
            index_id=index_id,
            filter=filter,
            use_rerank=False,
            reranker_ref=reranker_ref,
            run_id=run_id,
        )
        keyword_results = await self.query_keyword(
            knowledge_id=knowledge_id,
            query_text=query_text,
            top_k=keyword_top_k or top_k,
            filter=filter,
            run_id=run_id,
            candidate_limit=candidate_limit,
            min_score=min_score,
        )

        merged: dict[str, QueryResult] = {}
        vector_scores: dict[str, float] = {}
        keyword_scores: dict[str, float] = {}

        for result in vector_results:
            vector_scores[result.chunk_id] = result.score
            result.metadata["vector_score"] = result.score
            merged[result.chunk_id] = result

        for result in keyword_results:
            keyword_scores[result.chunk_id] = result.score
            result.metadata["keyword_score"] = result.score
            existing = merged.get(result.chunk_id)
            if existing:
                if not existing.text:
                    existing.text = result.text
                existing.metadata.update(result.metadata or {})
            else:
                merged[result.chunk_id] = result

        max_vec = max(vector_scores.values(), default=0.0)
        max_key = max(keyword_scores.values(), default=0.0)

        combined_results: list[QueryResult] = []
        for chunk_id, result in merged.items():
            vec_norm = (vector_scores.get(chunk_id, 0.0) / max_vec) if max_vec else 0.0
            key_norm = (keyword_scores.get(chunk_id, 0.0) / max_key) if max_key else 0.0
            combined = (alpha * vec_norm) + ((1.0 - alpha) * key_norm)
            result.score = combined
            result.metadata["hybrid_score"] = combined
            combined_results.append(result)

        combined_results.sort(key=lambda item: item.score, reverse=True)
        combined_results = combined_results[:top_k]

        if use_rerank and combined_results:
            reranker_model = reranker_ref
            if not reranker_model:
                default_index = self.index_repo.get_primary(knowledge_id)
                reranker_model = default_index.reranker_ref if default_index else None
            if reranker_model:
                documents = [r.text for r in combined_results]
                reranked = await self.llm_port.rerank(
                    model=reranker_model,
                    query=query_text,
                    documents=documents,
                    top_n=top_k,
                    run_id=run_id,
                )
                reranked_map = {doc["document"]: doc for doc in reranked.results}
                reranked_results = []
                for result in combined_results:
                    if result.text in reranked_map:
                        reranked_item = reranked_map[result.text]
                        result.score = reranked_item.get("score", result.score)
                        result.metadata["rerank_score"] = result.score
                        reranked_results.append(result)
                reranked_results.sort(key=lambda x: x.score, reverse=True)
                combined_results = reranked_results[:top_k]

        return combined_results

    def _passes_filter(
        self,
        metadata: dict[str, Any],
        filter_value: dict[str, Any],
    ) -> bool:
        """Apply a simple equality filter against metadata."""
        if not filter_value:
            return True
        for key, expected in filter_value.items():
            actual = metadata.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            else:
                if actual != expected:
                    return False
        return True

    async def query_multiple_indexes(
        self,
        knowledge_id: str,
        query_text: str,
        index_ids: list[str],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
        use_rerank: bool = False,
        reranker_ref: str | None = None,
        run_id: str | None = None,
    ) -> list[QueryResult]:
        """Query multiple indexes and merge results.

        Args:
            knowledge_id: Knowledge ID.
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
                knowledge_id=knowledge_id,
                query_text=query_text,
                top_k=top_k,
                index_id=index_id,
                filter=filter,
                use_rerank=False,
                run_id=run_id,
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

        merged = unique_results[:top_k]

        if use_rerank and merged:
            if not reranker_ref:
                default_index = self.index_repo.get_primary(knowledge_id)
                reranker_ref = default_index.reranker_ref if default_index else None
            if reranker_ref:
                documents = [r.text for r in merged]
                reranked = await self.llm_port.rerank(
                    model=reranker_ref,
                    query=query_text,
                    documents=documents,
                    top_n=top_k,
                    run_id=run_id,
                )
                reranked_map = {doc["document"]: doc for doc in reranked.results}
                reranked_results = []
                for result in merged:
                    if result.text in reranked_map:
                        reranked_item = reranked_map[result.text]
                        result.score = reranked_item.get("score", result.score)
                        reranked_results.append(result)
                reranked_results.sort(key=lambda x: x.score, reverse=True)
                merged = reranked_results[:top_k]

        return merged
