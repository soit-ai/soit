""" repository

Knowledge repositories using scope-aware base.
"""

from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.infra.db.repository import Repository
from app.kernel.commons.errors import ConflictError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.common import lease
from app.modules.knowledge.domain.models import (
    Knowledge,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIndex,
    KnowledgeIngestTask,
)


class KnowledgeRepository(Repository[Knowledge]):
    """Repository for Knowledge model."""

    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize knowledge repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Knowledge, db, ctx)

    def get_by_id(self, knowledge_id: str) -> Knowledge | None:
        """Get knowledge by ID.

        Args:
            knowledge_id: Knowledge ID.

        Returns:
            Knowledge instance or None.
        """
        query = select(Knowledge).where(
            and_(
                Knowledge.tenant_id == self.ctx.tenant_id,
                Knowledge.workspace_id == self.ctx.workspace_id,
                Knowledge.id == knowledge_id,
                Knowledge.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def get_by_name(self, name: str) -> Knowledge | None:
        """Get knowledge by name.

        Args:
            ctx: Request context.
            name: Knowledge name.

        Returns:
            Knowledge instance or None if not found.
        """
        query = select(Knowledge).where(
            and_(
                Knowledge.tenant_id == self.ctx.tenant_id,
                Knowledge.workspace_id == self.ctx.workspace_id,
                Knowledge.name == name,
                Knowledge.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list(
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
        query = select(Knowledge).where(
            and_(
                Knowledge.tenant_id == self.ctx.tenant_id,
                Knowledge.workspace_id == self.ctx.workspace_id,
                Knowledge.deleted_at.is_(None),
            )
        ).order_by(Knowledge.created_at.desc()).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def update_stats(
        self,
        knowledge_id: str,
        doc_count: int | None = None,
        chunk_count: int | None = None,
        last_indexed_at: datetime | None = None,
    ) -> Knowledge:
        """Update knowledge statistics.

        Args:
            knowledge_id: Knowledge ID.
            doc_count: Optional document count to set.
            chunk_count: Optional chunk count to set.

        Returns:
            Updated Knowledge instance.
        """
        knowledge = self.get_by_id(knowledge_id)
        if not knowledge:
            raise ValueError(f"Knowledge not found: {knowledge_id}")

        if doc_count is not None:
            knowledge.doc_count = doc_count
        if chunk_count is not None:
            knowledge.chunk_count = chunk_count
        if last_indexed_at is not None:
            knowledge.last_indexed_at = last_indexed_at

        from app.kernel.commons.time import utc_now
        knowledge.updated_at = utc_now()

        self.db.commit()
        self.db.refresh(knowledge)
        return knowledge


class DocumentRepository(Repository[KnowledgeDocument]):
    """Repository for KnowledgeDocument model."""

    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize document repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(KnowledgeDocument, db, ctx)

    def get_by_id(self, document_id: str) -> KnowledgeDocument | None:
        """Get document by ID.

        Args:
            document_id: Document ID.

        Returns:
            KnowledgeDocument instance or None.
        """
        query = select(KnowledgeDocument).where(
            and_(
                KnowledgeDocument.tenant_id == self.ctx.tenant_id,
                KnowledgeDocument.workspace_id == self.ctx.workspace_id,
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def get_by_key(
        self,
        knowledge_id: str,
        doc_key: str,
        version: int | None = None,
    ) -> KnowledgeDocument | None:
        """Get document by key and optional version.

        Args:
            ctx: Request context.
            knowledge_id: Knowledge ID.
            doc_key: Document key.
            version: Optional version number (if None, get latest).

        Returns:
            KnowledgeDocument instance or None if not found.
        """
        query = select(KnowledgeDocument).where(
            and_(
                KnowledgeDocument.tenant_id == self.ctx.tenant_id,
                KnowledgeDocument.workspace_id == self.ctx.workspace_id,
                KnowledgeDocument.knowledge_id == knowledge_id,
                KnowledgeDocument.doc_key == doc_key,
                KnowledgeDocument.deleted_at.is_(None),
            )
        )

        if version:
            query = query.where(KnowledgeDocument.version == version)
        else:
            query = query.where(KnowledgeDocument.is_latest.is_(True))

        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list_by_knowledge(
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
        query = select(KnowledgeDocument).where(
            and_(
                KnowledgeDocument.tenant_id == self.ctx.tenant_id,
                KnowledgeDocument.workspace_id == self.ctx.workspace_id,
                KnowledgeDocument.knowledge_id == knowledge_id,
                KnowledgeDocument.deleted_at.is_(None),
            )
        )

        if is_latest_only:
            query = query.where(KnowledgeDocument.is_latest.is_(True))

        query = query.order_by(KnowledgeDocument.created_at.desc()).offset(offset).limit(limit)

        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def get_next_version(self, knowledge_id: str, doc_key: str) -> int:
        """Get next version number for document key.

        Args:
            knowledge_id: Knowledge ID.
            doc_key: Document key.

        Returns:
            Next version number.
        """
        query = select(func.max(KnowledgeDocument.version)).where(
            and_(
                KnowledgeDocument.tenant_id == self.ctx.tenant_id,
                KnowledgeDocument.workspace_id == self.ctx.workspace_id,
                KnowledgeDocument.knowledge_id == knowledge_id,
                KnowledgeDocument.doc_key == doc_key,
            )
        )
        max_version = self.db.exec(query).one()
        if isinstance(max_version, list | tuple) or hasattr(max_version, "_mapping"):
            max_version = max_version[0]
        return (max_version or 0) + 1

    def count_by_knowledge(self, knowledge_id: str) -> int:
        """Count documents in knowledge (latest versions only).

        Args:
            knowledge_id: Knowledge ID.

        Returns:
            Document count.
        """
        query = select(func.count()).select_from(KnowledgeDocument).where(
            and_(
                KnowledgeDocument.tenant_id == self.ctx.tenant_id,
                KnowledgeDocument.workspace_id == self.ctx.workspace_id,
                KnowledgeDocument.knowledge_id == knowledge_id,
                KnowledgeDocument.is_latest.is_(True),
                KnowledgeDocument.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).one()
        if isinstance(result, list | tuple) or hasattr(result, "_mapping"):
            return int(result[0] or 0)
        return int(result or 0)


class ChunkRepository(Repository[KnowledgeChunk]):
    """Repository for KnowledgeChunk model."""

    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize chunk repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(KnowledgeChunk, db, ctx)

    def list_by_document(
        self,
        document_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[KnowledgeChunk]:
        """List chunks for a document.

        Args:
            document_id: Document ID.
            limit: Maximum number of chunks.
            offset: Offset for pagination.

        Returns:
            List of KnowledgeChunk instances.
        """
        query = select(KnowledgeChunk).where(
            and_(
                KnowledgeChunk.tenant_id == self.ctx.tenant_id,
                KnowledgeChunk.workspace_id == self.ctx.workspace_id,
                KnowledgeChunk.document_id == document_id,
            )
        ).order_by(KnowledgeChunk.chunk_no).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def list_by_knowledge(
        self,
        knowledge_id: str,
        index_status: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[KnowledgeChunk]:
        """List chunks in knowledge.

        Args:
            knowledge_id: Knowledge ID.
            index_status: Optional filter by index_status.
            limit: Maximum number of chunks.
            offset: Offset for pagination.

        Returns:
            List of KnowledgeChunk instances.
        """
        query = select(KnowledgeChunk).where(
            and_(
                KnowledgeChunk.tenant_id == self.ctx.tenant_id,
                KnowledgeChunk.workspace_id == self.ctx.workspace_id,
                KnowledgeChunk.knowledge_id == knowledge_id,
            )
        )

        if index_status:
            query = query.where(KnowledgeChunk.index_status == index_status)

        query = query.order_by(KnowledgeChunk.created_at.desc()).offset(offset).limit(limit)

        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def count_by_knowledge(self, knowledge_id: str) -> int:
        """Count chunks in knowledge.

        Args:
            knowledge_id: Knowledge ID.

        Returns:
            Chunk count.
        """
        query = select(func.count()).select_from(KnowledgeChunk).where(
            and_(
                KnowledgeChunk.tenant_id == self.ctx.tenant_id,
                KnowledgeChunk.workspace_id == self.ctx.workspace_id,
                KnowledgeChunk.knowledge_id == knowledge_id,
            )
        )
        result = self.db.exec(query).one()
        if isinstance(result, list | tuple) or hasattr(result, "_mapping"):
            return int(result[0] or 0)
        return int(result or 0)


class IndexRepository(Repository[KnowledgeIndex]):
    """Repository for KnowledgeIndex model."""

    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize index repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(KnowledgeIndex, db, ctx)

    def get_by_id(self, index_id: str) -> KnowledgeIndex | None:
        """Get index by ID.

        Args:
            index_id: Index ID.

        Returns:
            KnowledgeIndex instance or None.
        """
        query = select(KnowledgeIndex).where(
            and_(
                KnowledgeIndex.tenant_id == self.ctx.tenant_id,
                KnowledgeIndex.workspace_id == self.ctx.workspace_id,
                KnowledgeIndex.id == index_id,
                KnowledgeIndex.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def get_by_name(self, knowledge_id: str, name: str) -> KnowledgeIndex | None:
        """Get index by name.

        Args:
            knowledge_id: Knowledge ID.
            name: Index name.

        Returns:
            KnowledgeIndex instance or None if not found.
        """
        query = select(KnowledgeIndex).where(
            and_(
                KnowledgeIndex.tenant_id == self.ctx.tenant_id,
                KnowledgeIndex.workspace_id == self.ctx.workspace_id,
                KnowledgeIndex.knowledge_id == knowledge_id,
                KnowledgeIndex.name == name,
                KnowledgeIndex.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def get_primary(self, knowledge_id: str) -> KnowledgeIndex | None:
        """Get primary index for knowledge.

        Args:
            knowledge_id: Knowledge ID.

        Returns:
            Primary KnowledgeIndex instance or None if not found.
        """
        query = select(KnowledgeIndex).where(
            and_(
                KnowledgeIndex.tenant_id == self.ctx.tenant_id,
                KnowledgeIndex.workspace_id == self.ctx.workspace_id,
                KnowledgeIndex.knowledge_id == knowledge_id,
                KnowledgeIndex.is_primary.is_(True),
                KnowledgeIndex.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list_by_knowledge(
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
        query = select(KnowledgeIndex).where(
            and_(
                KnowledgeIndex.tenant_id == self.ctx.tenant_id,
                KnowledgeIndex.workspace_id == self.ctx.workspace_id,
                KnowledgeIndex.knowledge_id == knowledge_id,
                KnowledgeIndex.deleted_at.is_(None),
            )
        ).order_by(KnowledgeIndex.created_at.desc()).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)


class IngestTaskRepository(Repository[KnowledgeIngestTask]):
    """Repository for KnowledgeIngestTask model."""

    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize ingest task repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(KnowledgeIngestTask, db, ctx)

    def create(self, task: KnowledgeIngestTask) -> KnowledgeIngestTask:
        """Create a new ingestion task."""
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_by_id(self, task_id: str) -> KnowledgeIngestTask | None:
        """Get task by ID."""
        query = select(KnowledgeIngestTask).where(
            and_(
                KnowledgeIngestTask.tenant_id == self.ctx.tenant_id,
                KnowledgeIngestTask.workspace_id == self.ctx.workspace_id,
                KnowledgeIngestTask.id == task_id,
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list_pending(self, limit: int = 20) -> list[KnowledgeIngestTask]:
        """List queued tasks."""
        query = select(KnowledgeIngestTask).where(
            and_(
                KnowledgeIngestTask.tenant_id == self.ctx.tenant_id,
                KnowledgeIngestTask.workspace_id == self.ctx.workspace_id,
                KnowledgeIngestTask.status == "queued",
            )
        ).order_by(KnowledgeIngestTask.created_at.asc()).limit(limit)
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def list_by_knowledge(
        self,
        knowledge_id: str,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[KnowledgeIngestTask]:
        """List tasks by knowledge."""
        query = select(KnowledgeIngestTask).where(
            and_(
                KnowledgeIngestTask.tenant_id == self.ctx.tenant_id,
                KnowledgeIngestTask.workspace_id == self.ctx.workspace_id,
                KnowledgeIngestTask.knowledge_id == knowledge_id,
            )
        )
        if status:
            query = query.where(KnowledgeIngestTask.status == status)
        query = query.order_by(KnowledgeIngestTask.created_at.desc()).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def claim_next(
        self,
        *,
        worker_id: str | None = None,
        lease_seconds: int | None = None,
    ) -> KnowledgeIngestTask | None:
        """Claim the next queued task, or reclaim one with an expired lease."""
        from app.kernel.commons.time import utc_now

        task = lease.claim_next(
            self.db,
            KnowledgeIngestTask,
            worker_id=worker_id or f"knowledge-ingest:{self.ctx.user_id}",
            lease_seconds=lease.normalize_lease_seconds(lease_seconds),
            extra_where=(
                KnowledgeIngestTask.tenant_id == self.ctx.tenant_id,
                KnowledgeIngestTask.workspace_id == self.ctx.workspace_id,
            ),
        )
        if not task:
            return None
        if task.started_at is None:
            task.started_at = utc_now()
        task.updated_by = self.ctx.user_id
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_status(
        self,
        task: KnowledgeIngestTask,
        status: str,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
        run_id: str | None = None,
        retry_count: int | None = None,
        expected_lease_owner: str | None = None,
    ) -> KnowledgeIngestTask:
        """Update task status and metadata.

        When ``expected_lease_owner`` is given the write is refused unless that
        worker still holds the lease. A worker whose lease lapsed has already
        been superseded, and letting it record an outcome would overwrite the
        result of the worker that actually owns the task.
        """
        from app.kernel.commons.time import utc_now

        if expected_lease_owner is not None:
            self.db.refresh(task)
            if task.lease_owner != expected_lease_owner:
                raise ConflictError(
                    f"Ingest task {task.id} is no longer owned by {expected_lease_owner}"
                )
        task.status = status
        task.updated_at = utc_now()
        task.updated_by = self.ctx.user_id
        if status == "queued":
            task.started_at = None
            task.finished_at = None
        if status == "running" and task.started_at is None:
            task.started_at = utc_now()
        if status in ("succeeded", "failed", "canceled"):
            task.finished_at = utc_now()
        if status != "running":
            # Leaving the running state ends the execution lease. A retry that
            # returns to "queued" must be claimable by any worker, and a
            # terminal task must never look like live work.
            task.lease_owner = None
            task.lease_expires_at = None
        if error_code is not None:
            task.error_code = error_code
        if error_message is not None:
            task.error_message = error_message
        if run_id is not None:
            task.run_id = run_id
        if retry_count is not None:
            task.retry_count = retry_count
        self.db.commit()
        self.db.refresh(task)
        return task
