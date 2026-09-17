""" versioning

Document versioning management.
"""


from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.modules.knowledge.domain.models import KnowledgeDocument
from app.modules.knowledge.infra.repository import DocumentRepository


class DocumentVersioning:
    """Service for managing document versions."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        """Initialize versioning service.

        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
        self.document_repo = DocumentRepository(db, ctx)

    async def create_version(
        self,
        knowledge_id: str,
        doc_key: str,
        status: str = "uploaded",
        **kwargs,
    ) -> KnowledgeDocument:
        """Create a new document version.

        Args:
            knowledge_id: Knowledge ID.
            doc_key: Document key.
            **kwargs: Additional document fields.

        Returns:
            New KnowledgeDocument instance.
        """
        # Get next version number
        version = await self.document_repo.get_next_version(knowledge_id, doc_key)

        # Mark previous versions as not latest
        previous_versions = await self._get_versions(knowledge_id, doc_key)
        for prev_version in previous_versions:
            if prev_version.is_latest:
                prev_version.is_latest = False
                prev_version.updated_at = utc_now()
                prev_version.updated_by = self.ctx.user_id

        # Create new version
        new_document = KnowledgeDocument(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            knowledge_id=knowledge_id,
            doc_key=doc_key,
            version=version,
            is_latest=True,
            status=status,
            **kwargs,
        )

        self.db.add(new_document)
        await self.db.commit()

        return new_document

    async def get_latest_version(
        self,
        knowledge_id: str,
        doc_key: str,
    ) -> KnowledgeDocument | None:
        """Get latest version of document.

        Args:
            knowledge_id: Knowledge ID.
            doc_key: Document key.

        Returns:
            Latest KnowledgeDocument instance or None.
        """
        return await self.document_repo.get_by_key(knowledge_id, doc_key)

    async def get_version(
        self,
        knowledge_id: str,
        doc_key: str,
        version: int,
    ) -> KnowledgeDocument | None:
        """Get specific version of document.

        Args:
            knowledge_id: Knowledge ID.
            doc_key: Document key.
            version: Version number.

        Returns:
            KnowledgeDocument instance or None.
        """
        return await self.document_repo.get_by_key(knowledge_id, doc_key, version=version)

    async def list_versions(
        self,
        knowledge_id: str,
        doc_key: str,
    ) -> list[KnowledgeDocument]:
        """List all versions of document.

        Args:
            knowledge_id: Knowledge ID.
            doc_key: Document key.

        Returns:
            List of KnowledgeDocument instances.
        """
        return await self._get_versions(knowledge_id, doc_key)

    async def rollback_to_version(
        self,
        knowledge_id: str,
        doc_key: str,
        target_version: int,
    ) -> KnowledgeDocument:
        """Rollback to a specific version.

        Args:
            knowledge_id: Knowledge ID.
            doc_key: Document key.
            target_version: Target version number.

        Returns:
            Rolled back KnowledgeDocument instance.
        """
        # Get target version
        target_doc = await self.get_version(knowledge_id, doc_key, target_version)
        if not target_doc:
            raise ValueError(f"Version {target_version} not found")

        # Mark all versions as not latest
        all_versions = await self._get_versions(knowledge_id, doc_key)
        for version_doc in all_versions:
            if version_doc.is_latest:
                version_doc.is_latest = False
                version_doc.updated_at = utc_now()
                version_doc.updated_by = self.ctx.user_id

        # Mark target version as latest
        target_doc.is_latest = True
        target_doc.updated_at = utc_now()
        target_doc.updated_by = self.ctx.user_id

        await self.db.commit()

        return target_doc

    async def _get_versions(
        self,
        knowledge_id: str,
        doc_key: str,
    ) -> list[KnowledgeDocument]:
        """Get all versions of document.

        Args:
            knowledge_id: Knowledge ID.
            doc_key: Document key.

        Returns:
            List of KnowledgeDocument instances.
        """
        query = select(KnowledgeDocument).where(
            and_(
                KnowledgeDocument.tenant_id == self.ctx.tenant_id,
                KnowledgeDocument.workspace_id == self.ctx.workspace_id,
                KnowledgeDocument.knowledge_id == knowledge_id,
                KnowledgeDocument.doc_key == doc_key,
                KnowledgeDocument.deleted_at.is_(None),
            )
        ).order_by(KnowledgeDocument.version.desc())

        results = list((await self.db.exec(query)).scalars().all())
        return self.document_repo._unwrap_all(results)

