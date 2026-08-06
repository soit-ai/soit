"""service

Internal knowledge runtime service.
"""

import hashlib
import re
from datetime import datetime
from typing import Any
from urllib.parse import unquote, urlparse

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import KernelError
from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_KNOWLEDGE
from app.kernel.ports.http.interface import HttpFetchPort
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.vector.interface import VectorPort
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.kernel.runtime.runs.schemas import (
    RunCostByModelResponse,
    RunCostByModeResponse,
    RunCostByProviderResponse,
    RunCostSummaryResponse,
    RunResponse,
)
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.knowledge.application.chunker import TextChunker
from app.modules.knowledge.application.ports import (
    ChunkRepositoryPort,
    DocumentRepositoryPort,
    IndexRepositoryPort,
    IngestTaskRepositoryPort,
    KnowledgeRepositoryPort,
)
from app.modules.knowledge.application.runtime_schemas import (
    DocumentUpload,
    IndexCreate,
    IndexUpdate,
    KnowledgeConsumerUsageResponse,
    KnowledgeCreate,
    KnowledgeUpdate,
    QueryCitation,
    QueryRequest,
    QueryResponse,
    QueryResult,
)
from app.modules.knowledge.domain.models import (
    Knowledge,
    KnowledgeDocument,
    KnowledgeIndex,
    KnowledgeIngestTask,
)
from app.modules.knowledge.domain.versioning import DocumentVersioning
from app.modules.knowledge.runtime.index_builder import IndexBuilder
from app.modules.knowledge.runtime.pipeline import DocumentPipeline
from app.modules.knowledge.runtime.retrieval import RetrievalService

UPLOAD_STREAM_CHUNK_SIZE = 1024 * 1024


class KnowledgeRuntimeService:
    """Service for managing knowledge data."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        knowledge_repo: KnowledgeRepositoryPort,
        document_repo: DocumentRepositoryPort,
        chunk_repo: ChunkRepositoryPort,
        index_repo: IndexRepositoryPort,
        ingest_task_repo: IngestTaskRepositoryPort | None = None,
        pipeline: DocumentPipeline | None = None,
        retrieval_service: RetrievalService | None = None,
        index_builder: IndexBuilder | None = None,
        storage_port: StoragePort | None = None,
        vector_port: VectorPort | None = None,
        trace_writer: TraceWriter | None = None,
        http_fetch_port: HttpFetchPort | None = None,
    ):
        """Initialize knowledge runtime service.

        Args:
            db: Database session.
            ctx: Request context.
            pipeline: Optional document pipeline (required for document processing).
            retrieval_service: Optional retrieval service (required for querying).
            index_builder: Optional index builder (required for rebuild).
            storage_port: Optional storage gateway (required for file persistence).
            vector_port: Optional vector gateway (required for deletions).
            trace_writer: Optional trace writer.
        """
        self.db = db
        self.ctx = ctx
        self.knowledge_repo = knowledge_repo
        self.document_repo = document_repo
        self.chunk_repo = chunk_repo
        self.index_repo = index_repo
        self.ingest_task_repo = ingest_task_repo
        self.pipeline = pipeline
        self.retrieval_service = retrieval_service
        self.index_builder = index_builder
        self.storage_port = storage_port
        self.vector_port = vector_port
        self.trace_writer = trace_writer
        self.http_fetch_port = http_fetch_port
        self.versioning = DocumentVersioning(db, ctx)

    def _resolve_knowledge_trace_subject(
        self,
        knowledge_id: str | None,
        *,
        version_id: str | None = None,
    ) -> tuple[str, str, str | None]:
        return "knowledge", knowledge_id or self.ctx.workspace_id, version_id

    def _resolve_knowledge_create_id(self, knowledge_in: KnowledgeCreate, **kwargs) -> str:
        """Resolve a knowledge id for create RBAC checks."""
        return knowledge_in.name or f"new:{self.ctx.workspace_id}"

    def _resolve_knowledge_id_from_document(self, document_id: str) -> str:
        """Resolve a knowledge id for document-scoped RBAC checks."""
        document = self.document_repo.get_by_id(document_id)
        if not document:
            raise KernelError("NOT_FOUND", f"Document {document_id} not found")
        return document.knowledge_id

    @staticmethod
    def _compose_knowledge_run_summary(knowledge_id: str, summary: str) -> str:
        base = f"knowledge_id={knowledge_id}"
        summary = (summary or "").strip()
        if not summary:
            return base
        return f"{base}; {summary}"

    @staticmethod
    def _extract_summary_field(input_summary: str | None, field: str) -> str | None:
        if not input_summary:
            return None
        pattern = rf"(?:^|[;,\s]){re.escape(field)}=([^;,\s]+)"
        match = re.search(pattern, input_summary)
        if not match:
            return None
        return match.group(1).strip()

    def _run_belongs_to_knowledge(self, run: Run, knowledge_id: str) -> bool:
        if run.subject_kind == "knowledge" and run.subject_id == knowledge_id:
            return True
        summary_knowledge_id = self._extract_summary_field(run.input_summary, "knowledge_id")
        if summary_knowledge_id:
            return summary_knowledge_id == knowledge_id

        if run.mode == "knowledge_ingest":
            if not self.ingest_task_repo:
                return False
            tasks = self.ingest_task_repo.list_by_knowledge(knowledge_id, limit=10000, offset=0)
            return any(task.run_id == run.id for task in tasks if task.run_id)

        if run.mode in ("knowledge_index", "knowledge_index_delete"):
            index_id = self._extract_summary_field(run.input_summary, "index_id")
            if not index_id:
                return False
            index = self.index_repo.get_by_id(index_id)
            return bool(index and index.knowledge_id == knowledge_id)

        return False

    def _list_knowledge_runs_raw(
        self,
        *,
        knowledge_id: str,
        mode: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        kind: str | None = None,
    ) -> list[Run]:
        clauses: list[Any] = [
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
            Run.subject_kind == "knowledge",
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if status:
            clauses.append(Run.status == status)
        if kind:
            clauses.append(Run.kind == kind)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        query = select(Run).where(and_(*clauses)).order_by(desc(Run.created_at)).limit(5000)
        raw_rows = list(self.db.exec(query).all())
        runs: list[Run] = []
        for row in raw_rows:
            if hasattr(row, "id"):
                runs.append(row)
            else:
                try:
                    runs.append(row[0])
                except Exception:
                    continue
        return [run for run in runs if self._run_belongs_to_knowledge(run, knowledge_id)]

    def _extract_snippets(
        self,
        text: str,
        query_text: str,
        max_snippets: int,
        snippet_length: int,
    ) -> list[str]:
        """Extract query-centered snippets from text."""
        if not text or max_snippets <= 0:
            return []
        query_text = (query_text or "").strip()
        if not query_text:
            return [text[:snippet_length]]

        tokens = [token for token in re.split(r"\s+", query_text) if token]
        if not tokens:
            tokens = [query_text]

        lower_text = text.lower()
        positions: list[int] = []
        for token in tokens:
            idx = lower_text.find(token.lower())
            if idx != -1:
                positions.append(idx)

        if not positions:
            return [text[:snippet_length]]

        snippets: list[str] = []
        half = max(10, snippet_length // 2)
        for idx in positions[:max_snippets]:
            start = max(idx - half, 0)
            end = min(start + snippet_length, len(text))
            snippet = text[start:end].strip()
            if snippet and snippet not in snippets:
                snippets.append(snippet)
        return snippets[:max_snippets]

    def _query_indexed_chunks_fallback(
        self,
        *,
        knowledge_id: str,
        query: str,
        top_k: int,
    ) -> list[QueryResult]:
        chunks = self.chunk_repo.list_by_knowledge(
            knowledge_id,
            index_status="indexed",
            limit=max(top_k * 10, top_k),
            offset=0,
        )
        if not chunks:
            return []
        query_terms = {
            token.lower()
            for token in re.split(r"\W+", query or "")
            if len(token) > 1
        }
        ranked = []
        for chunk in chunks:
            text = chunk.text_preview or ""
            text_lower = text.lower()
            overlap = sum(1 for term in query_terms if term in text_lower)
            score = float(overlap / max(len(query_terms), 1)) if query_terms else 0.0
            ranked.append((score, chunk))
        ranked.sort(key=lambda item: (item[0], item[1].chunk_no), reverse=True)

        results: list[QueryResult] = []
        for score, chunk in ranked[:top_k]:
            document = self.document_repo.get_by_id(chunk.document_id)
            metadata = {
                "knowledge_id": chunk.knowledge_id,
                "doc_key": document.doc_key if document else None,
                "title": document.title if document else None,
                "source_uri": document.source_uri if document else None,
                "chunk_no": chunk.chunk_no,
                "page_no": chunk.page_no,
                "section_path": chunk.section_path or [],
                "fallback": "indexed_chunks",
            }
            results.append(
                QueryResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    score=score,
                    text=text,
                    metadata=metadata,
                )
            )
        return results

    @rbac_guard(RESOURCE_KNOWLEDGE, "create", resource_id_resolver=_resolve_knowledge_create_id)
    async def create_knowledge(self, knowledge_in: KnowledgeCreate) -> Knowledge:
        """Create a new knowledge base.

        Args:
            knowledge_in: Knowledge creation schema.

        Returns:
            Created Knowledge instance.
        """
        # Check if name already exists
        existing = self.knowledge_repo.get_by_name(knowledge_in.name)
        if existing:
            raise KernelError("DUPLICATE_NAME", f"Knowledge '{knowledge_in.name}' already exists")

        # Create knowledge
        knowledge = Knowledge(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            name=knowledge_in.name,
            type=knowledge_in.type,
            description=knowledge_in.description,
            visibility=knowledge_in.visibility,
            settings_json=knowledge_in.settings_json or {},
            chunking_json=knowledge_in.chunking_json or {},
            retrieval_json=knowledge_in.retrieval_json or {},
            default_embedding_model_ref=knowledge_in.default_embedding_model_ref,
            default_reranker_ref=knowledge_in.default_reranker_ref,
            tags=knowledge_in.tags,
            created_by=self.ctx.user_id,
            updated_by=self.ctx.user_id,
        )

        knowledge = self.knowledge_repo.create(knowledge)

        if knowledge_in.default_embedding_model_ref:
            existing_primary = self.index_repo.get_primary(knowledge.id)
            if not existing_primary:
                index = KnowledgeIndex(
                    tenant_id=self.ctx.tenant_id,
                    workspace_id=self.ctx.workspace_id,
                    knowledge_id=knowledge.id,
                    name="default",
                    is_primary=True,
                    provider="milvus",
                    embedding_model_ref=knowledge_in.default_embedding_model_ref,
                    dimension=0,
                    metric_type="cosine",
                    index_params_json={},
                    search_params_json={},
                    filters_json={},
                    status="draft",
                    build_version=1,
                    created_by=self.ctx.user_id,
                    updated_by=self.ctx.user_id,
                )
                index = self.index_repo.create(index)
                knowledge.default_index_id = index.id
                knowledge.updated_at = utc_now()
                self.db.commit()
                self.db.refresh(knowledge)

        return knowledge

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def get_knowledge(self, knowledge_id: str) -> Knowledge:
        """Get a knowledge base by ID.

        Args:
            knowledge_id: Knowledge ID.

        Returns:
            Knowledge instance.
        """
        knowledge = self.knowledge_repo.get_by_id(knowledge_id)
        if not knowledge:
            raise KernelError("NOT_FOUND", f"Knowledge {knowledge_id} not found")
        return knowledge

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id")
    async def update_knowledge(self, knowledge_id: str, knowledge_in: KnowledgeUpdate) -> Knowledge:
        """Update a knowledge base.

        Args:
            knowledge_id: Knowledge ID.
            knowledge_in: Knowledge update schema.

        Returns:
            Updated Knowledge instance.
        """
        knowledge = await self.get_knowledge(knowledge_id)

        # Update fields
        if knowledge_in.name is not None:
            # Check if new name conflicts
            existing = self.knowledge_repo.get_by_name(knowledge_in.name)
            if existing and existing.id != knowledge_id:
                raise KernelError("DUPLICATE_NAME", f"Knowledge '{knowledge_in.name}' already exists")
            knowledge.name = knowledge_in.name

        if knowledge_in.description is not None:
            knowledge.description = knowledge_in.description

        if knowledge_in.status is not None:
            knowledge.status = knowledge_in.status

        if knowledge_in.visibility is not None:
            knowledge.visibility = knowledge_in.visibility

        if knowledge_in.settings_json is not None:
            knowledge.settings_json = knowledge_in.settings_json

        if knowledge_in.chunking_json is not None:
            knowledge.chunking_json = knowledge_in.chunking_json

        if knowledge_in.retrieval_json is not None:
            knowledge.retrieval_json = knowledge_in.retrieval_json

        if knowledge_in.default_embedding_model_ref is not None:
            knowledge.default_embedding_model_ref = knowledge_in.default_embedding_model_ref

        if knowledge_in.default_reranker_ref is not None:
            knowledge.default_reranker_ref = knowledge_in.default_reranker_ref

        if knowledge_in.tags is not None:
            knowledge.tags = knowledge_in.tags

        knowledge.updated_by = self.ctx.user_id
        knowledge.updated_at = utc_now()

        self.db.commit()
        self.db.refresh(knowledge)

        return knowledge

    def _resolve_index(
        self,
        knowledge: Knowledge,
        index_id: str | None = None,
    ) -> KnowledgeIndex | None:
        """Resolve index for knowledge.

        Args:
            knowledge: Knowledge instance.
            index_id: Optional index ID.

        Returns:
            KnowledgeIndex instance or None.
        """
        if index_id:
            index = self.index_repo.get_by_id(index_id)
        elif knowledge.default_index_id:
            index = self.index_repo.get_by_id(knowledge.default_index_id)
        else:
            index = None

        if not index:
            index = self.index_repo.get_primary(knowledge.id)

        return index

    def _set_primary_index(self, knowledge: Knowledge, index: KnowledgeIndex) -> None:
        """Set the knowledge primary index.

        Args:
            knowledge: Knowledge instance.
            index: Index to mark as primary.
        """
        indexes = self.index_repo.list_by_knowledge(knowledge.id, limit=1000, offset=0)
        for item in indexes:
            if item.id != index.id and item.is_primary:
                item.is_primary = False
                item.updated_at = utc_now()

        index.is_primary = True
        index.updated_at = utc_now()
        index.updated_by = self.ctx.user_id

        knowledge.default_index_id = index.id
        knowledge.updated_at = utc_now()
        knowledge.updated_by = self.ctx.user_id

        self.db.commit()
        self.db.refresh(index)
        self.db.refresh(knowledge)

    def _resolve_document_index(
        self,
        knowledge: Knowledge,
        document: KnowledgeDocument,
    ) -> KnowledgeIndex | None:
        """Resolve index for a document.

        Args:
            knowledge: Knowledge instance.
            document: Document instance.

        Returns:
            KnowledgeIndex instance or None.
        """
        index_id = None
        if document.index_meta_json:
            index_id = document.index_meta_json.get("index_id")
        return self._resolve_index(knowledge, index_id)

    async def _get_document_for_knowledge(self, knowledge_id: str, document_id: str) -> KnowledgeDocument:
        """Get document and verify knowledge ownership."""
        document = await self.get_document(document_id)
        if document.knowledge_id != knowledge_id:
            raise KernelError("NOT_FOUND", f"Document {document_id} not found")
        return document

    async def _persist_upload_file(
        self,
        knowledge_id: str,
        document: KnowledgeDocument,
        document_in: DocumentUpload,
        file_content: Any | None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist upload file to storage and normalize payload."""
        payload = document_in.model_dump(exclude_none=True)

        if (
            file_content is None
            and document_in.source_kind == "crawler"
            and document_in.source_uri
            and not payload.get("file_id")
        ):
            fetched_content, fetched_mime, fetched_filename = await self._fetch_source_content(document_in.source_uri)
            file_content = fetched_content
            payload.setdefault("mime_type", fetched_mime)
            payload.setdefault("filename", fetched_filename)
            payload.setdefault("title", document.title or fetched_filename or document_in.source_uri)
            payload.setdefault("size_bytes", len(fetched_content))
            document.mime_type = payload.get("mime_type")
            document.filename = payload.get("filename")
            if not document.title:
                document.title = payload.get("title")

        if not file_content:
            return payload

        if not self.storage_port:
            raise KernelError("STORAGE_NOT_AVAILABLE", "Storage gateway is not configured")

        is_stream = self._is_upload_stream(file_content)
        if is_stream:
            size_bytes = payload.get("size_bytes")
            checksum = payload.get("checksum")
        else:
            size_bytes = payload.get("size_bytes") or len(file_content)
            checksum = payload.get("checksum") or hashlib.sha256(file_content).hexdigest()
        content_hash = payload.get("content_hash") or checksum

        if size_bytes is not None:
            payload["size_bytes"] = size_bytes
        if checksum:
            payload["checksum"] = checksum
            payload["content_hash"] = content_hash

        if not payload.get("file_id"):
            storage_key = (
                f"tenants/{self.ctx.tenant_id}/workspaces/{self.ctx.workspace_id}/"
                f"knowledge/{knowledge_id}/raw/{generate_ulid()}"
            )
            if is_stream:
                size_bytes, checksum = await self._stream_upload_to_storage(
                    storage_key,
                    file_content,
                    content_type=document.mime_type,
                    run_id=run_id,
                )
                content_hash = payload.get("content_hash") or checksum
                payload["size_bytes"] = size_bytes
                payload["checksum"] = checksum
                payload["content_hash"] = content_hash
            else:
                await self.storage_port.put(
                    key=storage_key,
                    data=file_content,
                    content_type=document.mime_type,
                    run_id=run_id,
                )
            payload["file_id"] = storage_key
            document.file_id = storage_key

        document.size_bytes = payload.get("size_bytes")
        document.checksum = payload.get("checksum")
        document.content_hash = payload.get("content_hash")
        document.updated_by = self.ctx.user_id
        document.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(document)
        return payload

    @staticmethod
    def _is_upload_stream(file_content: Any) -> bool:
        return file_content is not None and not isinstance(file_content, bytes) and hasattr(file_content, "read")

    async def _stream_upload_to_storage(
        self,
        storage_key: str,
        file_content: Any,
        *,
        content_type: str | None,
        run_id: str | None,
    ) -> tuple[int, str]:
        hasher = hashlib.sha256()
        size_bytes = 0

        open_writer = getattr(self.storage_port, "open_writer", None)
        if open_writer:
            try:
                async with await open_writer(
                    key=storage_key,
                    content_type=content_type,
                    run_id=run_id,
                ) as writer:
                    while True:
                        chunk = await self._read_upload_chunk(file_content)
                        if not chunk:
                            break
                        size_bytes += len(chunk)
                        hasher.update(chunk)
                        await writer.write(chunk)
                return size_bytes, hasher.hexdigest()
            except KernelError as exc:
                if exc.code != "STORAGE_STREAMING_NOT_SUPPORTED":
                    raise

        chunks: list[bytes] = []
        while True:
            chunk = await self._read_upload_chunk(file_content)
            if not chunk:
                break
            size_bytes += len(chunk)
            hasher.update(chunk)
            chunks.append(chunk)
        await self.storage_port.put(
            key=storage_key,
            data=b"".join(chunks),
            content_type=content_type,
            run_id=run_id,
        )
        return size_bytes, hasher.hexdigest()

    @staticmethod
    async def _read_upload_chunk(file_content: Any) -> bytes:
        try:
            chunk = await file_content.read(UPLOAD_STREAM_CHUNK_SIZE)
        except TypeError:
            chunk = await file_content.read()
        if isinstance(chunk, str):
            return chunk.encode("utf-8")
        return chunk

    @staticmethod
    def _guess_filename_from_uri(source_uri: str) -> str:
        parsed = urlparse(source_uri)
        candidate = unquote((parsed.path or "").split("/")[-1]).strip()
        if candidate:
            return candidate
        host = parsed.netloc or "crawler"
        return f"{host}.html"

    async def _fetch_source_content(self, source_uri: str) -> tuple[bytes, str, str]:
        if self.http_fetch_port is None:
            raise KernelError(
                "CRAWLER_FETCH_NOT_CONFIGURED",
                "Governed HTTP fetch port is not configured",
            )

        max_bytes = 5 * 1024 * 1024
        try:
            resource = await self.http_fetch_port.fetch(
                self.ctx,
                source_uri,
                max_bytes=max_bytes,
            )
        except KernelError:
            raise
        except Exception as exc:
            raise KernelError("CRAWLER_FETCH_FAILED", f"Failed to fetch source_uri: {exc}") from exc

        content = resource.content or b""
        if not content:
            raise KernelError("CRAWLER_EMPTY_CONTENT", "Fetched content is empty")

        if len(content) > max_bytes:
            raise KernelError("CRAWLER_CONTENT_TOO_LARGE", "Fetched content exceeds 5MB limit")

        content_type = resource.content_type or "text/html"
        filename = self._guess_filename_from_uri(resource.final_url)
        return content, content_type, filename

    async def _process_document_ingest(
        self,
        knowledge: Knowledge,
        document: KnowledgeDocument,
        file_content: bytes | None,
        run_id: str | None,
    ) -> KnowledgeDocument:
        """Process document ingestion pipeline and update knowledge stats."""
        if not self.pipeline:
            raise KernelError("PIPELINE_NOT_AVAILABLE", "Document pipeline is not configured")

        document = await self.pipeline.process_document(
            document,
            knowledge,
            file_content,
            run_id=run_id,
        )

        knowledge.last_ingested_at = utc_now()
        knowledge.updated_at = utc_now()
        knowledge.updated_by = self.ctx.user_id
        self.db.commit()

        return document

    async def enqueue_ingest_task(
        self,
        knowledge_id: str,
        document_in: DocumentUpload,
        file_content: Any | None = None,
        max_retries: int = 1,
    ) -> tuple[KnowledgeDocument, KnowledgeIngestTask]:
        """Enqueue a knowledge ingestion task and return the document."""
        if not self.ingest_task_repo:
            raise KernelError("INGEST_TASK_REPO_NOT_AVAILABLE", "Ingest task repository is not configured")
        if not self.pipeline:
            raise KernelError("PIPELINE_NOT_AVAILABLE", "Document pipeline is not configured")

        knowledge = await self.get_knowledge(knowledge_id)

        run_id = None
        if self.trace_writer:
            subject_kind, subject_id, _ = self._resolve_knowledge_trace_subject(knowledge_id, version_id=document_in.doc_key)
            run = self.trace_writer.create_run(
                mode="knowledge_ingest",
                kind="batch",
                subject_kind=subject_kind,
                subject_id=subject_id,
                subject_version_id=document_in.doc_key,
                input_summary=self._compose_knowledge_run_summary(knowledge_id, f"doc_key={document_in.doc_key}"),
            )
            run_id = run.id

        document = self.versioning.create_version(
            knowledge_id=knowledge_id,
            doc_key=document_in.doc_key,
            status="queued",
            source_kind=document_in.source_kind,
            source_uri=document_in.source_uri,
            file_id=document_in.file_id,
            title=document_in.title,
            language=document_in.language,
            mime_type=document_in.mime_type,
            filename=document_in.filename,
            size_bytes=document_in.size_bytes,
            checksum=document_in.checksum,
            content_hash=document_in.content_hash,
            access_policy_json=document_in.access_policy_json or {},
            created_by=self.ctx.user_id,
            updated_by=self.ctx.user_id,
        )

        payload = await self._persist_upload_file(
            knowledge.id,
            document,
            document_in,
            file_content,
            run_id=run_id,
        )

        task = KnowledgeIngestTask(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            knowledge_id=knowledge_id,
            document_id=document.id,
            status="queued",
            payload_json=payload,
            run_id=run_id,
            retry_count=0,
            max_retries=max(0, max_retries),
            created_by=self.ctx.user_id,
            updated_by=self.ctx.user_id,
        )
        task = self.ingest_task_repo.create(task)
        return document, task

    async def process_ingest_task(
        self,
        task: KnowledgeIngestTask,
        *,
        lease_owner: str | None = None,
    ) -> KnowledgeDocument:
        """Process a queued ingestion task.

        ``lease_owner`` makes every terminal write conditional on this worker
        still holding the lease, so a worker that was superseded cannot record
        an outcome over the one that actually owns the task.
        """
        if not self.ingest_task_repo:
            raise KernelError("INGEST_TASK_REPO_NOT_AVAILABLE", "Ingest task repository is not configured")
        if not self.pipeline:
            raise KernelError("PIPELINE_NOT_AVAILABLE", "Document pipeline is not configured")

        # A task whose knowledge or document no longer exists can never
        # succeed. Fail it terminally here; raising without a status write
        # would leave it claimed until the lease expires and the queue would
        # retry it forever.
        def _orphaned(message: str) -> KernelError:
            if self.trace_writer and task.run_id:
                self.trace_writer.update_run_status(
                    task.run_id, "failed", output_summary=message
                )
            self.ingest_task_repo.update_status(
                task,
                "failed",
                error_code="NOT_FOUND",
                error_message=message,
                run_id=task.run_id,
                expected_lease_owner=lease_owner,
            )
            return KernelError("NOT_FOUND", message)

        knowledge = self.knowledge_repo.get_by_id(task.knowledge_id)
        if not knowledge:
            raise _orphaned(f"Knowledge {task.knowledge_id} not found")
        if not task.document_id:
            raise _orphaned("Ingest task missing document_id")
        document = self.document_repo.get_by_id(task.document_id)
        if not document:
            raise _orphaned(f"Document {task.document_id} not found")

        run_id = task.run_id
        if self.trace_writer:
            previous_run = self.db.get(Run, run_id) if run_id else None
            if previous_run and previous_run.status in {"succeeded", "failed", "canceled", "expired"}:
                subject_kind, subject_id, _ = self._resolve_knowledge_trace_subject(
                    task.knowledge_id,
                    version_id=document.doc_key,
                )
                run = self.trace_writer.create_run(
                    mode="knowledge_ingest",
                    kind="batch",
                    subject_kind=subject_kind,
                    subject_id=subject_id,
                    subject_version_id=document.doc_key,
                    input_summary=self._compose_knowledge_run_summary(
                        task.knowledge_id,
                        f"doc_key={document.doc_key}",
                    ),
                    source_run_id=previous_run.id,
                    attempt_no=max(previous_run.attempt_no + 1, task.retry_count + 1),
                    request_id=f"knowledge-ingest:{task.id}:{task.retry_count + 1}",
                )
                run_id = run.id
            elif not run_id:
                subject_kind, subject_id, _ = self._resolve_knowledge_trace_subject(task.knowledge_id, version_id=document.doc_key)
                run = self.trace_writer.create_run(
                    mode="knowledge_ingest",
                    kind="batch",
                    subject_kind=subject_kind,
                    subject_id=subject_id,
                    subject_version_id=document.doc_key,
                    input_summary=self._compose_knowledge_run_summary(task.knowledge_id, f"doc_key={document.doc_key}"),
                )
                run_id = run.id
            self.trace_writer.update_run_status(run_id, "running")
            self.ingest_task_repo.update_status(task, "running", run_id=run_id)

        try:
            document = await self._process_document_ingest(
                knowledge,
                document,
                file_content=None,
                run_id=run_id,
            )
            latest = self.ingest_task_repo.get_by_id(task.id)
            if latest and latest.status == "canceled":
                if self.trace_writer and run_id:
                    self.trace_writer.update_run_status(run_id, "canceled")
                return document
            if self.trace_writer and run_id:
                self.trace_writer.update_run_status(run_id, "succeeded")
            self.ingest_task_repo.update_status(
                task,
                "succeeded",
                run_id=run_id,
                expected_lease_owner=lease_owner,
            )
            return document
        except Exception as exc:
            if self.trace_writer and run_id:
                self.trace_writer.update_run_status(run_id, "failed", output_summary=str(exc))
            next_retry = task.retry_count + 1
            if next_retry <= task.max_retries:
                document.status = "queued"
                document.error_code = None
                document.error_message = None
                document.updated_at = utc_now()
                document.updated_by = self.ctx.user_id
                self.db.commit()
                self.db.refresh(document)
                self.ingest_task_repo.update_status(
                    task,
                    "queued",
                    error_code="INGEST_ERROR",
                    error_message=str(exc),
                    run_id=run_id,
                    retry_count=next_retry,
                )
            else:
                self.ingest_task_repo.update_status(
                    task,
                    "failed",
                    error_code="INGEST_ERROR",
                    error_message=str(exc),
                    run_id=run_id,
                    retry_count=next_retry,
                    expected_lease_owner=lease_owner,
                )
            raise

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def list_ingest_tasks(
        self,
        knowledge_id: str,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[KnowledgeIngestTask]:
        """List ingest tasks for a knowledge."""
        if not self.ingest_task_repo:
            raise KernelError("INGEST_TASK_REPO_NOT_AVAILABLE", "Ingest task repository is not configured")
        await self.get_knowledge(knowledge_id)
        return self.ingest_task_repo.list_by_knowledge(
            knowledge_id=knowledge_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def get_ingest_task(self, knowledge_id: str, task_id: str) -> KnowledgeIngestTask:
        """Get ingest task by ID."""
        if not self.ingest_task_repo:
            raise KernelError("INGEST_TASK_REPO_NOT_AVAILABLE", "Ingest task repository is not configured")
        task = self.ingest_task_repo.get_by_id(task_id)
        if not task or task.knowledge_id != knowledge_id:
            raise KernelError("NOT_FOUND", f"Ingest task {task_id} not found")
        return task

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id")
    async def retry_ingest_task(self, knowledge_id: str, task_id: str) -> KnowledgeIngestTask:
        """Retry a failed ingest task."""
        task = await self.get_ingest_task(knowledge_id, task_id)
        if task.status not in ("failed", "canceled"):
            raise KernelError("INVALID_STATUS", "Only failed/canceled tasks can be retried")

        document = None
        if task.document_id:
            document = self.document_repo.get_by_id(task.document_id)
            if document and document.knowledge_id == knowledge_id:
                document.status = "queued"
                document.error_code = None
                document.error_message = None
                document.updated_at = utc_now()
                document.updated_by = self.ctx.user_id
                self.db.commit()
                self.db.refresh(document)

        task.error_code = None
        task.error_message = None
        task.run_id = None
        task.started_at = None
        task.finished_at = None
        self.db.commit()
        self.db.refresh(task)
        return self.ingest_task_repo.update_status(task, "queued")

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id")
    async def cancel_ingest_task(self, knowledge_id: str, task_id: str) -> KnowledgeIngestTask:
        """Cancel an ingest task."""
        task = await self.get_ingest_task(knowledge_id, task_id)
        if task.status in ("succeeded", "failed", "canceled"):
            raise KernelError("INVALID_STATUS", "Only queued/running tasks can be canceled")
        return self.ingest_task_repo.update_status(task, "canceled")

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id")
    async def retry_document_ingest(
        self,
        knowledge_id: str,
        document_id: str,
        max_retries: int = 1,
    ) -> KnowledgeIngestTask:
        """Retry ingestion for a document by creating a new task."""
        if not self.ingest_task_repo:
            raise KernelError("INGEST_TASK_REPO_NOT_AVAILABLE", "Ingest task repository is not configured")
        if not self.pipeline:
            raise KernelError("PIPELINE_NOT_AVAILABLE", "Document pipeline is not configured")

        knowledge = await self.get_knowledge(knowledge_id)
        document = await self._get_document_for_knowledge(knowledge_id, document_id)

        if document.status not in ("failed", "deleted"):
            raise KernelError("INVALID_STATUS", "Only failed documents can be retried")
        if not document.file_id:
            raise KernelError("NO_FILE", "Document file_id is missing, cannot retry ingest")

        payload = {
            "doc_key": document.doc_key,
            "source_kind": document.source_kind,
            "source_uri": document.source_uri,
            "file_id": document.file_id,
            "title": document.title,
            "language": document.language,
            "mime_type": document.mime_type,
            "filename": document.filename,
            "size_bytes": document.size_bytes,
            "checksum": document.checksum,
            "content_hash": document.content_hash,
            "access_policy_json": document.access_policy_json or {},
        }

        document.status = "queued"
        document.error_code = None
        document.error_message = None
        document.updated_at = utc_now()
        document.updated_by = self.ctx.user_id
        self.db.commit()
        self.db.refresh(document)

        task = KnowledgeIngestTask(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            knowledge_id=knowledge.id,
            document_id=document.id,
            status="queued",
            payload_json=payload,
            retry_count=0,
            max_retries=max(0, max_retries),
            created_by=self.ctx.user_id,
            updated_by=self.ctx.user_id,
        )
        return self.ingest_task_repo.create(task)

    async def _cleanup_document_artifacts(
        self,
        knowledge: Knowledge,
        document: KnowledgeDocument,
        chunks: list[Any],
        run_id: str | None = None,
    ) -> None:
        """Cleanup document artifacts from storage and vector index.

        Args:
            knowledge: Knowledge instance.
            document: Document instance.
            chunks: Chunk list for the document.
            run_id: Optional run id for trace emission.
        """
        index = self._resolve_document_index(knowledge, document)
        if self.vector_port and index:
            vector_ids = [chunk.vector_ref or chunk.id for chunk in chunks if chunk.vector_ref or chunk.id]
            if vector_ids:
                collection_name = index.collection_name or f"idx_{index.id}"
                await self.vector_port.delete(
                    collection=collection_name,
                    ids=vector_ids,
                    run_id=run_id,
                )

        if self.storage_port:
            keys = []
            if document.file_id:
                keys.append(document.file_id)
            if document.raw_text_artifact_key:
                keys.append(document.raw_text_artifact_key)
            if document.parsed_artifact_key:
                keys.append(document.parsed_artifact_key)
            for chunk in chunks:
                if chunk.text_artifact_key:
                    keys.append(chunk.text_artifact_key)

            if keys:
                import logging
                logger = logging.getLogger(__name__)
                for key in keys:
                    try:
                        await self.storage_port.delete(key=key, run_id=run_id)
                    except Exception as exc:
                        logger.warning("Failed to delete storage key %s: %s", key, exc)

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id")
    async def create_index(self, knowledge_id: str, index_in: IndexCreate) -> KnowledgeIndex:
        """Create a new index for a knowledge.

        Args:
            knowledge_id: Knowledge ID.
            index_in: Index creation schema.

        Returns:
            Created KnowledgeIndex instance.
        """
        knowledge = await self.get_knowledge(knowledge_id)

        existing = self.index_repo.get_by_name(knowledge_id, index_in.name)
        if existing:
            raise KernelError("DUPLICATE_NAME", f"Index '{index_in.name}' already exists")

        existing_primary = self.index_repo.get_primary(knowledge_id)
        is_primary = index_in.is_primary or existing_primary is None

        index = KnowledgeIndex(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            knowledge_id=knowledge_id,
            name=index_in.name,
            is_primary=is_primary,
            provider=index_in.provider,
            embedding_model_ref=index_in.embedding_model_ref,
            dimension=index_in.dimension,
            metric_type=index_in.metric_type,
            collection_name=index_in.collection_name,
            partition_strategy=index_in.partition_strategy,
            namespace=index_in.namespace,
            index_params_json=index_in.index_params_json or {},
            search_params_json=index_in.search_params_json or {},
            reranker_ref=index_in.reranker_ref,
            filters_json=index_in.filters_json or {},
            status="draft",
            build_version=1,
            created_by=self.ctx.user_id,
            updated_by=self.ctx.user_id,
        )

        index = self.index_repo.create(index)

        if knowledge.default_embedding_model_ref is None:
            knowledge.default_embedding_model_ref = index.embedding_model_ref
            knowledge.updated_by = self.ctx.user_id

        if is_primary:
            self._set_primary_index(knowledge, index)
        else:
            knowledge.updated_at = utc_now()
            knowledge.updated_by = self.ctx.user_id
            self.db.commit()

        return index

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def list_indexes(
        self,
        knowledge_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[KnowledgeIndex]:
        """List indexes for knowledge.

        Args:
            knowledge_id: Knowledge ID.
            limit: Maximum number of indexes.
            offset: Offset for pagination.

        Returns:
            List of KnowledgeIndex instances.
        """
        await self.get_knowledge(knowledge_id)
        return self.index_repo.list_by_knowledge(knowledge_id, limit=limit, offset=offset)

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def get_index(self, knowledge_id: str, index_id: str) -> KnowledgeIndex:
        """Get index by ID.

        Args:
            knowledge_id: Knowledge ID.
            index_id: Index ID.

        Returns:
            KnowledgeIndex instance.
        """
        index = self.index_repo.get_by_id(index_id)
        if not index or index.knowledge_id != knowledge_id:
            raise KernelError("NOT_FOUND", f"Index {index_id} not found")
        return index

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id")
    async def update_index(
        self,
        knowledge_id: str,
        index_id: str,
        index_in: IndexUpdate,
    ) -> KnowledgeIndex:
        """Update index.

        Args:
            knowledge_id: Knowledge ID.
            index_id: Index ID.
            index_in: Index update schema.

        Returns:
            Updated KnowledgeIndex instance.
        """
        knowledge = await self.get_knowledge(knowledge_id)
        index = await self.get_index(knowledge_id, index_id)

        if index_in.name:
            existing = self.index_repo.get_by_name(knowledge_id, index_in.name)
            if existing and existing.id != index_id:
                raise KernelError("DUPLICATE_NAME", f"Index '{index_in.name}' already exists")
            index.name = index_in.name

        if index_in.status:
            index.status = index_in.status
        if index_in.search_params_json is not None:
            index.search_params_json = index_in.search_params_json
        if index_in.reranker_ref is not None:
            index.reranker_ref = index_in.reranker_ref
        if index_in.filters_json is not None:
            index.filters_json = index_in.filters_json

        index.updated_at = utc_now()
        index.updated_by = self.ctx.user_id

        if index_in.is_primary is True:
            self._set_primary_index(knowledge, index)
        else:
            if index_in.is_primary is False and index.is_primary:
                index.is_primary = False
                knowledge.default_index_id = None
                candidates = [
                    item for item in self.index_repo.list_by_knowledge(knowledge_id, limit=1000, offset=0)
                    if item.id != index.id
                ]
                if candidates:
                    candidates[0].is_primary = True
                    candidates[0].updated_at = utc_now()
                    candidates[0].updated_by = self.ctx.user_id
                    knowledge.default_index_id = candidates[0].id
            knowledge.updated_at = utc_now()
            knowledge.updated_by = self.ctx.user_id
            self.db.commit()
            self.db.refresh(index)

        return index

    @rbac_guard(RESOURCE_KNOWLEDGE, "delete", resource_id_arg="knowledge_id")
    async def delete_index(self, knowledge_id: str, index_id: str) -> None:
        """Delete index (soft delete).

        Args:
            knowledge_id: Knowledge ID.
            index_id: Index ID.
        """
        knowledge = await self.get_knowledge(knowledge_id)
        index = await self.get_index(knowledge_id, index_id)

        run_id = None
        if self.trace_writer:
            subject_kind, subject_id, _ = self._resolve_knowledge_trace_subject(knowledge_id, version_id=index_id)
            run = self.trace_writer.create_run(
                mode="knowledge_index_delete",
                kind="batch",
                subject_kind=subject_kind,
                subject_id=subject_id,
                subject_version_id=index_id,
                input_summary=self._compose_knowledge_run_summary(knowledge_id, f"index_id={index_id}"),
            )
            run_id = run.id
            self.trace_writer.update_run_status(run_id, "running")

        try:
            if self.vector_port:
                chunks = self.chunk_repo.list_by_knowledge(knowledge_id, limit=10000, offset=0)
                vector_ids = [chunk.vector_ref or chunk.id for chunk in chunks if chunk.vector_ref or chunk.id]
                if vector_ids:
                    collection_name = index.collection_name or f"idx_{index.id}"
                    await self.vector_port.delete(
                        collection=collection_name,
                        ids=vector_ids,
                        run_id=run_id,
                    )

            index.is_primary = False
            index.status = "disabled"
            index.deleted_at = utc_now()
            index.updated_at = utc_now()
            index.updated_by = self.ctx.user_id

            if knowledge.default_index_id == index.id:
                knowledge.default_index_id = None

            candidates = [
                item for item in self.index_repo.list_by_knowledge(knowledge_id, limit=1000, offset=0)
                if item.id != index.id
            ]
            if candidates:
                candidates[0].is_primary = True
                candidates[0].updated_at = utc_now()
                candidates[0].updated_by = self.ctx.user_id
                knowledge.default_index_id = candidates[0].id

            knowledge.updated_at = utc_now()
            knowledge.updated_by = self.ctx.user_id

            self.db.commit()
            if run_id:
                self.trace_writer.update_run_status(run_id, "succeeded")
        except Exception as exc:
            if run_id:
                self.trace_writer.update_run_status(run_id, "failed", output_summary=str(exc))
            raise

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def list_document_versions(
        self,
        knowledge_id: str,
        doc_key: str,
    ) -> list[KnowledgeDocument]:
        """List all versions for a document key.

        Args:
            knowledge_id: Knowledge ID.
            doc_key: Document key.

        Returns:
            List of KnowledgeDocument instances.
        """
        await self.get_knowledge(knowledge_id)
        return self.versioning.list_versions(knowledge_id, doc_key)

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id")
    async def rollback_document_version(
        self,
        knowledge_id: str,
        doc_key: str,
        target_version: int,
    ) -> KnowledgeDocument:
        """Rollback document to a specific version.

        Args:
            knowledge_id: Knowledge ID.
            doc_key: Document key.
            target_version: Version number to rollback.

        Returns:
            KnowledgeDocument instance.
        """
        await self.get_knowledge(knowledge_id)
        try:
            document = self.versioning.rollback_to_version(knowledge_id, doc_key, target_version)
        except ValueError as exc:
            raise KernelError("NOT_FOUND", str(exc)) from exc

        document.updated_by = self.ctx.user_id
        document.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(document)
        return document

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id")
    async def upload_document(
        self,
        knowledge_id: str,
        document_in: DocumentUpload,
        file_content: Any | None = None,
        async_ingest: bool = False,
        max_retries: int = 1,
    ) -> KnowledgeDocument:
        """Upload and process a document.

        Args:
            knowledge_id: Knowledge ID.
            document_in: Document upload schema.
            file_content: Optional file content.
            async_ingest: Whether to enqueue ingestion instead of processing inline.
            max_retries: Max retries for async ingest.

        Returns:
            Created KnowledgeDocument instance.

        Raises:
            KernelError: If pipeline is not available.
        """
        if document_in.source_kind == "upload" and not file_content and not document_in.file_id:
            raise KernelError("NO_FILE", "File content or file_id is required for upload source")
        if document_in.source_kind == "crawler" and not document_in.source_uri:
            raise KernelError("INVALID_SOURCE_URI", "source_uri is required for crawler source")

        if async_ingest:
            document, _task = await self.enqueue_ingest_task(
                knowledge_id=knowledge_id,
                document_in=document_in,
                file_content=file_content,
                max_retries=max_retries,
            )
            return document

        if not self.pipeline:
            raise KernelError("PIPELINE_NOT_AVAILABLE", "Document pipeline is not configured")

        knowledge = await self.get_knowledge(knowledge_id)

        run_id = None
        if self.trace_writer:
            subject_kind, subject_id, _ = self._resolve_knowledge_trace_subject(knowledge_id, version_id=document_in.doc_key)
            run = self.trace_writer.create_run(
                mode="knowledge_ingest",
                kind="batch",
                subject_kind=subject_kind,
                subject_id=subject_id,
                subject_version_id=document_in.doc_key,
                input_summary=self._compose_knowledge_run_summary(knowledge_id, f"doc_key={document_in.doc_key}"),
            )
            run_id = run.id
            self.trace_writer.update_run_status(run_id, "running")

        try:
            # Create new document version
            document = self.versioning.create_version(
                knowledge_id=knowledge_id,
                doc_key=document_in.doc_key,
                source_kind=document_in.source_kind,
                source_uri=document_in.source_uri,
                file_id=document_in.file_id,
                title=document_in.title,
                language=document_in.language,
                mime_type=document_in.mime_type,
                filename=document_in.filename,
                size_bytes=document_in.size_bytes,
                checksum=document_in.checksum,
                content_hash=document_in.content_hash,
                access_policy_json=document_in.access_policy_json or {},
                created_by=self.ctx.user_id,
                updated_by=self.ctx.user_id,
            )

            await self._persist_upload_file(
                knowledge.id,
                document,
                document_in,
                file_content,
                run_id=run_id,
            )

            document = await self._process_document_ingest(
                knowledge,
                document,
                None if self._is_upload_stream(file_content) else file_content,
                run_id=run_id,
            )

            if run_id:
                self.trace_writer.update_run_status(run_id, "succeeded")

            return document
        except Exception as exc:
            if run_id:
                self.trace_writer.update_run_status(run_id, "failed", output_summary=str(exc))
            raise

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def list_documents(
        self,
        knowledge_id: str,
        is_latest_only: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> list[KnowledgeDocument]:
        """List documents in knowledge.

        Args:
            knowledge_id: Knowledge ID.
            is_latest_only: Only return latest versions.
            limit: Maximum number of documents.
            offset: Offset for pagination.

        Returns:
            List of KnowledgeDocument instances.
        """
        return self.document_repo.list_by_knowledge(
            knowledge_id=knowledge_id,
            is_latest_only=is_latest_only,
            limit=limit,
            offset=offset,
        )

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def list_chunks(
        self,
        knowledge_id: str,
        document_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Any]:
        """List chunks for a document."""
        await self._get_document_for_knowledge(knowledge_id, document_id)
        return self.chunk_repo.list_by_document(
            document_id=document_id,
            limit=limit,
            offset=offset,
        )

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id")
    async def update_chunk(
        self,
        knowledge_id: str,
        document_id: str,
        chunk_id: str,
        content: str | None = None,
        index_status: str | None = None,
    ) -> Any:
        """Update chunk content or status."""
        document = await self._get_document_for_knowledge(knowledge_id, document_id)
        chunk = self.chunk_repo.get_by_id(chunk_id)
        if not chunk or chunk.document_id != document.id:
            raise KernelError("NOT_FOUND", f"Chunk {chunk_id} not found")

        if content is not None:
            text = content.strip()
            chunk.text_preview = text[:512] if text else ""
            chunk.content_hash = TextChunker.compute_content_hash(text) if text else None
            if self.storage_port:
                storage_key = chunk.text_artifact_key
                if not storage_key:
                    storage_key = (
                        f"knowledge/{knowledge_id}/documents/{document_id}/chunks/"
                        f"{chunk.chunk_no}_{generate_ulid()}.txt"
                    )
                    chunk.text_artifact_key = storage_key
                await self.storage_port.put(
                    key=storage_key,
                    data=text.encode("utf-8"),
                    content_type="text/plain",
                )

        if index_status is not None:
            chunk.index_status = index_status

        chunk.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(chunk)
        return chunk

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_resolver=_resolve_knowledge_id_from_document)
    async def get_document(self, document_id: str) -> KnowledgeDocument:
        """Get document by ID.

        Args:
            document_id: Document ID.

        Returns:
            KnowledgeDocument instance.
        """
        document = self.document_repo.get_by_id(document_id)
        if not document:
            raise KernelError("NOT_FOUND", f"Document {document_id} not found")
        return document

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def get_document_content(self, knowledge_id: str, document_id: str) -> tuple[bytes, str]:
        """Get document content for preview.

        Args:
            knowledge_id: Knowledge ID.
            document_id: Document ID.

        Returns:
            Tuple of (content bytes, media type).
        """
        if not self.storage_port:
            raise KernelError("STORAGE_NOT_AVAILABLE", "Storage gateway is not configured")

        document = await self._get_document_for_knowledge(knowledge_id, document_id)
        storage_key = document.raw_text_artifact_key or document.file_id
        if not storage_key:
            raise KernelError("NO_CONTENT", "Document content is not available")

        data = await self.storage_port.get(key=storage_key)
        if storage_key == document.raw_text_artifact_key:
            media_type = "text/plain"
        else:
            media_type = document.mime_type or "application/octet-stream"
        return data, media_type

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def download_document(self, knowledge_id: str, document_id: str) -> tuple[bytes, str, str]:
        """Download document file.

        Args:
            knowledge_id: Knowledge ID.
            document_id: Document ID.

        Returns:
            Tuple of (content bytes, media type, filename).
        """
        if not self.storage_port:
            raise KernelError("STORAGE_NOT_AVAILABLE", "Storage gateway is not configured")

        document = await self._get_document_for_knowledge(knowledge_id, document_id)
        storage_key = document.file_id or document.raw_text_artifact_key
        if not storage_key:
            raise KernelError("NO_FILE", "Document file is not available")

        data = await self.storage_port.get(key=storage_key)
        if storage_key == document.file_id:
            media_type = document.mime_type or "application/octet-stream"
            filename = document.filename or document.title or f"{document.doc_key}.bin"
        else:
            media_type = "text/plain"
            filename = document.filename or document.title or f"{document.doc_key}.txt"
        return data, media_type, filename

    @rbac_guard(RESOURCE_KNOWLEDGE, "delete", resource_id_resolver=_resolve_knowledge_id_from_document)
    async def delete_document(self, document_id: str) -> None:
        """Delete document (soft delete).

        Args:
            document_id: Document ID.
        """
        document = await self.get_document(document_id)
        knowledge = await self.get_knowledge(document.knowledge_id)

        run_id = None
        if self.trace_writer:
            subject_kind, subject_id, _ = self._resolve_knowledge_trace_subject(document.knowledge_id, version_id=document.id)
            run = self.trace_writer.create_run(
                mode="knowledge_document_delete",
                kind="batch",
                subject_kind=subject_kind,
                subject_id=subject_id,
                subject_version_id=document.id,
                input_summary=self._compose_knowledge_run_summary(document.knowledge_id, f"document_id={document.id}"),
            )
            run_id = run.id
            self.trace_writer.update_run_status(run_id, "running")

        try:
            chunks = self.chunk_repo.list_by_document(document_id, limit=10000, offset=0)
            await self._cleanup_document_artifacts(knowledge, document, chunks, run_id=run_id)

            for chunk in chunks:
                self.db.delete(chunk)

            document.status = "deleted"
            document.deleted_at = utc_now()
            document.updated_at = utc_now()
            document.updated_by = self.ctx.user_id

            if document.is_latest:
                document.is_latest = False
                versions = self.versioning.list_versions(document.knowledge_id, document.doc_key)
                for version_doc in versions:
                    if version_doc.id != document.id:
                        version_doc.is_latest = True
                        version_doc.updated_at = utc_now()
                        version_doc.updated_by = self.ctx.user_id
                        break

            self.db.commit()

            doc_count = self.document_repo.count_by_knowledge(knowledge.id)
            chunk_count = self.chunk_repo.count_by_knowledge(knowledge.id)
            self.knowledge_repo.update_stats(
                knowledge.id,
                doc_count=doc_count,
                chunk_count=chunk_count,
            )

            if run_id:
                self.trace_writer.update_run_status(run_id, "succeeded")
        except Exception as exc:
            if run_id:
                self.trace_writer.update_run_status(run_id, "failed", output_summary=str(exc))
            raise

    @rbac_guard(RESOURCE_KNOWLEDGE, "run", resource_id_arg="knowledge_id")
    async def rebuild_index(self, knowledge_id: str, index_id: str | None = None) -> KnowledgeIndex:
        """Rebuild index.

        Args:
            knowledge_id: Knowledge ID.
            index_id: Optional index ID (use primary if not specified).

        Returns:
            Updated KnowledgeIndex instance.
        """
        if not self.index_builder:
            raise KernelError("INDEX_BUILDER_NOT_AVAILABLE", "Index builder is not configured")

        knowledge = await self.get_knowledge(knowledge_id)

        index = self._resolve_index(knowledge, index_id)
        if not index:
            raise KernelError("NOT_FOUND", "No index found for knowledge")

        run_id = None
        step_id = None
        if self.trace_writer:
            subject_kind, subject_id, _ = self._resolve_knowledge_trace_subject(knowledge_id, version_id=index.id)
            run = self.trace_writer.create_run(
                mode="knowledge_index",
                kind="batch",
                subject_kind=subject_kind,
                subject_id=subject_id,
                subject_version_id=index.id,
                input_summary=self._compose_knowledge_run_summary(knowledge_id, f"index_id={index.id}"),
            )
            run_id = run.id
            self.trace_writer.update_run_status(run_id, "running")
            step = self.trace_writer.create_step(
                run_id=run_id,
                step_type="io",
                step_id="rebuild",
                input_summary=self._compose_knowledge_run_summary(knowledge_id, f"index_id={index.id}"),
            )
            step_id = step.id
            self.trace_writer.update_step_status(step_id, "running")
            index.last_run_id = run_id
            index.updated_at = utc_now()
            self.db.commit()

        try:
            await self.index_builder.rebuild_index(index, run_id=run_id)
            if run_id:
                index.last_run_id = run_id
            index.last_error_code = None
            index.last_error_message = None
            index.updated_at = utc_now()
            index.updated_by = self.ctx.user_id
            self.db.commit()
            self.db.refresh(index)

            doc_count = self.document_repo.count_by_knowledge(knowledge.id)
            chunk_count = self.chunk_repo.count_by_knowledge(knowledge.id)
            self.knowledge_repo.update_stats(
                knowledge.id,
                doc_count=doc_count,
                chunk_count=chunk_count,
                last_indexed_at=utc_now(),
            )

            if step_id:
                self.trace_writer.update_step_status(step_id, "succeeded")
            if run_id:
                self.trace_writer.update_run_status(run_id, "succeeded")
        except Exception as exc:
            if run_id:
                index.last_run_id = run_id
            if not index.last_error_code:
                index.last_error_code = "REBUILD_ERROR"
            index.last_error_message = str(exc)
            index.updated_at = utc_now()
            index.updated_by = self.ctx.user_id
            self.db.commit()
            if step_id:
                self.trace_writer.update_step_status(step_id, "failed", output_summary=str(exc))
            if run_id:
                self.trace_writer.update_run_status(run_id, "failed", output_summary=str(exc))
            raise

        return index

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def list_runs_for_knowledge(
        self,
        knowledge_id: str,
        *,
        mode: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        kind: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[RunResponse]:
        """List trace runs scoped to a knowledge."""
        await self.get_knowledge(knowledge_id)
        runs = self._list_knowledge_runs_raw(
            knowledge_id=knowledge_id,
            mode=mode,
            status=status,
            started_after=started_after,
            started_before=started_before,
            kind=kind,
        )
        sliced = runs[offset: offset + limit]
        return [RunResponse.model_validate(item) for item in sliced]

    def _list_knowledge_cost_entries(self, run_ids: list[str]) -> list[RunCostEntry]:
        if not run_ids:
            return []
        query = select(RunCostEntry).where(
            and_(
                RunCostEntry.tenant_id == self.ctx.tenant_id,
                RunCostEntry.workspace_id == self.ctx.workspace_id,
                RunCostEntry.run_id.in_(run_ids),
            )
        )
        raw_rows = list(self.db.exec(query).all())
        entries: list[RunCostEntry] = []
        for row in raw_rows:
            if hasattr(row, "id"):
                entries.append(row)
            else:
                try:
                    entries.append(row[0])
                except Exception:
                    continue
        return entries

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def summarize_run_costs_for_knowledge(
        self,
        knowledge_id: str,
        *,
        mode: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        kind: str | None = None,
    ) -> RunCostSummaryResponse:
        """Summarize run cost metrics scoped to a knowledge."""
        await self.get_knowledge(knowledge_id)
        runs = self._list_knowledge_runs_raw(
            knowledge_id=knowledge_id,
            mode=mode,
            status=status,
            started_after=started_after,
            started_before=started_before,
            kind=kind,
        )
        run_ids = [run.id for run in runs]
        entries = self._list_knowledge_cost_entries(run_ids)

        summary = RunCostSummaryResponse(
            tokens_prompt=0,
            tokens_completion=0,
            embedding_count=0,
            rerank_count=0,
            ms_total=0,
            storage_bytes=0,
        )
        for entry in entries:
            summary.tokens_prompt += int(entry.prompt_tokens or 0)
            summary.tokens_completion += int(entry.completion_tokens or 0)
            summary.embedding_count += int(entry.embedding_count or 0)
            summary.rerank_count += int(entry.rerank_count or 0)
            summary.ms_total += int(entry.latency_ms or 0)
            summary.storage_bytes += int(entry.storage_bytes or 0)
            summary.request_count += int(entry.request_count or 0)
            summary.vector_count += int(entry.vector_count or 0)
        return summary

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def summarize_run_costs_by_mode_for_knowledge(
        self,
        knowledge_id: str,
        *,
        mode: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        kind: str | None = None,
    ) -> list[RunCostByModeResponse]:
        """Summarize run cost metrics by mode scoped to a knowledge."""
        await self.get_knowledge(knowledge_id)
        runs = self._list_knowledge_runs_raw(
            knowledge_id=knowledge_id,
            mode=mode,
            status=status,
            started_after=started_after,
            started_before=started_before,
            kind=kind,
        )
        run_map = {run.id: run for run in runs}
        entries = self._list_knowledge_cost_entries(list(run_map.keys()))

        buckets: dict[str, dict[str, int]] = {}
        for entry in entries:
            run = run_map.get(entry.run_id)
            if not run:
                continue
            bucket = buckets.setdefault(
                run.mode,
                {
                    "tokens_prompt": 0,
                    "tokens_completion": 0,
                    "embedding_count": 0,
                    "rerank_count": 0,
                    "ms_total": 0,
                    "storage_bytes": 0,
                },
            )
            if entry.prompt_tokens:
                bucket["tokens_prompt"] += int(entry.prompt_tokens)
            if entry.completion_tokens:
                bucket["tokens_completion"] += int(entry.completion_tokens)
            if entry.unit in ("embeddings", "embedding"):
                bucket["embedding_count"] += int(entry.quantity)
            if entry.unit == "rerank":
                bucket["rerank_count"] += int(entry.quantity)
            if entry.unit == "ms":
                bucket["ms_total"] += int(entry.quantity)
            if entry.unit == "bytes":
                bucket["storage_bytes"] += int(entry.quantity)

        return [
            RunCostByModeResponse(mode=key, **value)
            for key, value in sorted(buckets.items(), key=lambda item: item[0])
        ]

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def summarize_run_costs_by_provider_for_knowledge(
        self,
        knowledge_id: str,
        *,
        mode: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        kind: str | None = None,
    ) -> list[RunCostByProviderResponse]:
        """Summarize run cost metrics by provider scoped to a knowledge."""
        await self.get_knowledge(knowledge_id)
        runs = self._list_knowledge_runs_raw(
            knowledge_id=knowledge_id,
            mode=mode,
            status=status,
            started_after=started_after,
            started_before=started_before,
            kind=kind,
        )
        entries = self._list_knowledge_cost_entries([run.id for run in runs])

        buckets: dict[str | None, dict[str, int]] = {}
        for entry in entries:
            provider = entry.provider
            bucket = buckets.setdefault(
                provider,
                {
                    "tokens_prompt": 0,
                    "tokens_completion": 0,
                    "embedding_count": 0,
                    "rerank_count": 0,
                    "ms_total": 0,
                    "storage_bytes": 0,
                },
            )
            if entry.prompt_tokens:
                bucket["tokens_prompt"] += int(entry.prompt_tokens)
            if entry.completion_tokens:
                bucket["tokens_completion"] += int(entry.completion_tokens)
            if entry.unit in ("embeddings", "embedding"):
                bucket["embedding_count"] += int(entry.quantity)
            if entry.unit == "rerank":
                bucket["rerank_count"] += int(entry.quantity)
            if entry.unit == "ms":
                bucket["ms_total"] += int(entry.quantity)
            if entry.unit == "bytes":
                bucket["storage_bytes"] += int(entry.quantity)

        return [
            RunCostByProviderResponse(provider=key, **value)
            for key, value in sorted(buckets.items(), key=lambda item: (item[0] or ""))
        ]

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def summarize_run_costs_by_model_for_knowledge(
        self,
        knowledge_id: str,
        *,
        mode: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        kind: str | None = None,
    ) -> list[RunCostByModelResponse]:
        """Summarize run cost metrics by model scoped to a knowledge."""
        await self.get_knowledge(knowledge_id)
        runs = self._list_knowledge_runs_raw(
            knowledge_id=knowledge_id,
            mode=mode,
            status=status,
            started_after=started_after,
            started_before=started_before,
            kind=kind,
        )
        entries = self._list_knowledge_cost_entries([run.id for run in runs])

        buckets: dict[str | None, dict[str, int]] = {}
        for entry in entries:
            model_ref = entry.model_ref
            bucket = buckets.setdefault(
                model_ref,
                {
                    "tokens_prompt": 0,
                    "tokens_completion": 0,
                    "embedding_count": 0,
                    "rerank_count": 0,
                    "ms_total": 0,
                    "storage_bytes": 0,
                },
            )
            if entry.prompt_tokens:
                bucket["tokens_prompt"] += int(entry.prompt_tokens)
            if entry.completion_tokens:
                bucket["tokens_completion"] += int(entry.completion_tokens)
            if entry.unit in ("embeddings", "embedding"):
                bucket["embedding_count"] += int(entry.quantity)
            if entry.unit == "rerank":
                bucket["rerank_count"] += int(entry.quantity)
            if entry.unit == "ms":
                bucket["ms_total"] += int(entry.quantity)
            if entry.unit == "bytes":
                bucket["storage_bytes"] += int(entry.quantity)

        return [
            RunCostByModelResponse(model_ref=key, **value)
            for key, value in sorted(buckets.items(), key=lambda item: (item[0] or ""))
        ]

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id")
    async def list_knowledge_usages(
        self,
        knowledge_id: str,
        *,
        limit: int = 100,
    ) -> list[KnowledgeConsumerUsageResponse]:
        """List active agent/workflow usages for this knowledge base."""
        await self.get_knowledge(knowledge_id)
        del knowledge_id, limit
        return []

    @rbac_guard(RESOURCE_KNOWLEDGE, "run", resource_id_arg="knowledge_id")
    async def query(
        self,
        knowledge_id: str,
        query_request: QueryRequest,
    ) -> QueryResponse:
        """Query knowledge for relevant documents.

        Args:
            knowledge_id: Knowledge ID.
            query_request: Query request schema.

        Returns:
            QueryResponse instance.

        Raises:
            KernelError: If retrieval service is not available.
        """
        if not self.retrieval_service:
            raise KernelError("RETRIEVAL_NOT_AVAILABLE", "Retrieval service is not configured")

        knowledge = await self.get_knowledge(knowledge_id)
        retrieval_config = knowledge.retrieval_json or {}

        filter_value = query_request.filter or retrieval_config.get("filter")
        use_rerank = query_request.use_rerank or retrieval_config.get("use_rerank", False)
        reranker_ref = query_request.reranker_ref or knowledge.default_reranker_ref
        strategy = query_request.strategy or retrieval_config.get("strategy", "vector")

        keyword_top_k = query_request.keyword_top_k or retrieval_config.get("keyword_top_k") or query_request.top_k
        candidate_limit = query_request.keyword_candidate_limit or retrieval_config.get("keyword_candidate_limit") or 500
        keyword_min_score = query_request.keyword_min_score or retrieval_config.get("keyword_min_score") or 1
        hybrid_alpha = query_request.hybrid_alpha or retrieval_config.get("hybrid_alpha") or 0.7

        run_id = None
        step_id = None
        if self.trace_writer:
            subject_kind, subject_id, _ = self._resolve_knowledge_trace_subject(knowledge_id)
            run = self.trace_writer.create_run(
                mode="knowledge_query",
                kind="tool",
                subject_kind=subject_kind,
                subject_id=subject_id,
                input_summary=self._compose_knowledge_run_summary(knowledge_id, f"query={query_request.query}"),
            )
            run_id = run.id
            self.trace_writer.update_run_status(run_id, "running")
            step = self.trace_writer.create_step(
                run_id=run_id,
                step_type="retrieval",
                step_id="retrieve",
                input_summary=self._compose_knowledge_run_summary(knowledge_id, f"query={query_request.query}"),
            )
            step_id = step.id
            self.trace_writer.update_step_status(step_id, "running")

        try:
            try:
                if strategy == "multi_index":
                    index_ids = query_request.index_ids or retrieval_config.get("index_ids")
                    if not index_ids:
                        indexes = self.index_repo.list_by_knowledge(knowledge_id, limit=1000, offset=0)
                        index_ids = [item.id for item in indexes if item.status == "ready"]
                    if not index_ids:
                        raise KernelError("NOT_FOUND", "No ready indexes available for multi-index retrieval")
                    results = await self.retrieval_service.query_multiple_indexes(
                        knowledge_id=knowledge_id,
                        query_text=query_request.query,
                        index_ids=index_ids,
                        top_k=query_request.top_k,
                        filter=filter_value,
                        use_rerank=use_rerank,
                        reranker_ref=reranker_ref,
                        run_id=run_id,
                    )
                elif strategy == "keyword":
                    results = await self.retrieval_service.query_keyword(
                        knowledge_id=knowledge_id,
                        query_text=query_request.query,
                        top_k=keyword_top_k,
                        filter=filter_value,
                        run_id=run_id,
                        candidate_limit=candidate_limit,
                        min_score=keyword_min_score,
                    )
                elif strategy == "hybrid":
                    index_id = query_request.index_id or knowledge.default_index_id
                    results = await self.retrieval_service.query_hybrid(
                        knowledge_id=knowledge_id,
                        query_text=query_request.query,
                        top_k=query_request.top_k,
                        index_id=index_id,
                        filter=filter_value,
                        use_rerank=use_rerank,
                        reranker_ref=reranker_ref,
                        run_id=run_id,
                        candidate_limit=candidate_limit,
                        min_score=keyword_min_score,
                        alpha=hybrid_alpha,
                        keyword_top_k=keyword_top_k,
                    )
                else:
                    index_id = query_request.index_id or knowledge.default_index_id
                    results = await self.retrieval_service.query(
                        knowledge_id=knowledge_id,
                        query_text=query_request.query,
                        top_k=query_request.top_k,
                        index_id=index_id,
                        filter=filter_value,
                        use_rerank=use_rerank,
                        reranker_ref=reranker_ref,
                        run_id=run_id,
                    )
            except Exception:
                results = self._query_indexed_chunks_fallback(
                    knowledge_id=knowledge_id,
                    query=query_request.query,
                    top_k=query_request.top_k,
                )
                if not results:
                    raise
                strategy = f"{strategy}_chunk_fallback"

            if not results:
                fallback_results = self._query_indexed_chunks_fallback(
                    knowledge_id=knowledge_id,
                    query=query_request.query,
                    top_k=query_request.top_k,
                )
                if fallback_results:
                    results = fallback_results
                    strategy = f"{strategy}_chunk_fallback"

            if query_request.include_snippets:
                for result in results:
                    result.snippets = self._extract_snippets(
                        result.text,
                        query_request.query,
                        query_request.max_snippets,
                        query_request.snippet_length,
                    )

            citations: list[QueryCitation] = []
            for idx, result in enumerate(results):
                metadata = result.metadata or {}
                snippet = result.snippets[0] if result.snippets else None
                citations.append(
                    QueryCitation(
                        chunk_id=result.chunk_id,
                        document_id=result.document_id,
                        rank=idx + 1,
                        score=result.score,
                        knowledge_id=metadata.get("knowledge_id"),
                        doc_key=metadata.get("doc_key"),
                        title=metadata.get("title"),
                        source_uri=metadata.get("source_uri"),
                        chunk_no=metadata.get("chunk_no"),
                        page_no=metadata.get("page_no"),
                        section_path=metadata.get("section_path"),
                        snippet=snippet,
                    )
                )

            metrics = {
                "knowledge_id": knowledge_id,
                "strategy": strategy,
                "top_k": query_request.top_k,
                "result_count": len(results),
                "citation_count": len(citations),
                "use_rerank": use_rerank,
            }
            scores = [float(result.score) for result in results if result.score is not None]
            if scores:
                metrics["avg_score"] = sum(scores) / len(scores)
                metrics["max_score"] = max(scores)
                metrics["min_score"] = min(scores)
            if strategy == "multi_index":
                metrics["index_count"] = len(index_ids)
            if strategy in ("vector", "hybrid"):
                metrics["index_id"] = query_request.index_id or knowledge.default_index_id
            if strategy in ("keyword", "hybrid"):
                metrics["keyword_candidate_limit"] = candidate_limit
                metrics["keyword_min_score"] = keyword_min_score
                metrics["keyword_top_k"] = keyword_top_k

            if step_id:
                self.trace_writer.update_step_status(
                    step_id,
                    "succeeded",
                    output_summary=f"results={len(results)}",
                    metrics=metrics,
                )
            if run_id:
                self.trace_writer.update_run_status(run_id, "succeeded")

            return QueryResponse(
                results=results,
                total=len(results),
                citations=citations,
            )
        except Exception as exc:
            if step_id:
                self.trace_writer.update_step_status(step_id, "failed", output_summary=str(exc))
            if run_id:
                self.trace_writer.update_run_status(run_id, "failed", output_summary=str(exc))
            raise

    @workspace_guard("read")
    async def list_knowledge(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Knowledge]:
        """List knowledge bases.

        Args:
            limit: Maximum number of knowledge bases.
            offset: Offset for pagination.

        Returns:
            List of Knowledge instances.
        """
        return self.knowledge_repo.list(limit=limit, offset=offset)

    @rbac_guard(RESOURCE_KNOWLEDGE, "delete", resource_id_arg="knowledge_id")
    async def delete_knowledge(self, knowledge_id: str) -> None:
        """Delete a knowledge base (soft delete).

        Args:
            knowledge_id: Knowledge ID.

        Raises:
            KernelError: If the knowledge base is not found.
        """
        knowledge = await self.get_knowledge(knowledge_id)

        run_id = None
        if self.trace_writer:
            subject_kind, subject_id, _ = self._resolve_knowledge_trace_subject(knowledge_id)
            run = self.trace_writer.create_run(
                mode="knowledge_delete",
                kind="batch",
                subject_kind=subject_kind,
                subject_id=subject_id,
                input_summary=f"knowledge_id={knowledge_id}",
            )
            run_id = run.id
            self.trace_writer.update_run_status(run_id, "running")

        try:
            documents = self.document_repo.list_by_knowledge(
                knowledge_id=knowledge_id,
                is_latest_only=False,
                limit=10000,
                offset=0,
            )
            chunks = self.chunk_repo.list_by_knowledge(
                knowledge_id=knowledge_id,
                limit=10000,
                offset=0,
            )
            indexes = self.index_repo.list_by_knowledge(knowledge_id, limit=1000, offset=0)

            if self.vector_port:
                vector_ids = [chunk.vector_ref or chunk.id for chunk in chunks if chunk.vector_ref or chunk.id]
                if vector_ids:
                    for index in indexes:
                        collection_name = index.collection_name or f"idx_{index.id}"
                        await self.vector_port.delete(
                            collection=collection_name,
                            ids=vector_ids,
                            run_id=run_id,
                        )

            if self.storage_port:
                import logging
                logger = logging.getLogger(__name__)
                keys = []
                for doc in documents:
                    if doc.file_id:
                        keys.append(doc.file_id)
                    if doc.raw_text_artifact_key:
                        keys.append(doc.raw_text_artifact_key)
                    if doc.parsed_artifact_key:
                        keys.append(doc.parsed_artifact_key)
                for chunk in chunks:
                    if chunk.text_artifact_key:
                        keys.append(chunk.text_artifact_key)

                for key in keys:
                    try:
                        await self.storage_port.delete(key=key, run_id=run_id)
                    except Exception as exc:
                        logger.warning("Failed to delete storage key %s: %s", key, exc)

            for chunk in chunks:
                self.db.delete(chunk)

            for doc in documents:
                doc.deleted_at = utc_now()
                doc.status = "deleted"
                doc.is_latest = False
                doc.updated_at = utc_now()
                doc.updated_by = self.ctx.user_id

            for index in indexes:
                index.deleted_at = utc_now()
                index.status = "disabled"
                index.is_primary = False
                index.updated_at = utc_now()
                index.updated_by = self.ctx.user_id

            knowledge.deleted_at = utc_now()
            knowledge.status = "deleted"
            knowledge.default_index_id = None
            knowledge.doc_count = 0
            knowledge.chunk_count = 0
            knowledge.updated_at = utc_now()
            knowledge.updated_by = self.ctx.user_id

            self.db.commit()
            if run_id:
                self.trace_writer.update_run_status(run_id, "succeeded")
        except Exception as exc:
            if run_id:
                self.trace_writer.update_run_status(run_id, "failed", output_summary=str(exc))
            raise

