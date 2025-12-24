""" versioning

Document versioning management.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.kernel.contracts.context import RequestContext
from app.modules.domains.dataset.models import DatasetDocument
from app.modules.domains.dataset.repository import DocumentRepository
from app.kernel.commons.time import utcnow as utc_now


class DocumentVersioning:
    """Service for managing document versions."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize versioning service.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
        self.document_repo = DocumentRepository(db, ctx)
    
    def create_version(
        self,
        dataset_id: str,
        doc_key: str,
        **kwargs,
    ) -> DatasetDocument:
        """Create a new document version.
        
        Args:
            dataset_id: Dataset ID.
            doc_key: Document key.
            **kwargs: Additional document fields.
            
        Returns:
            New DatasetDocument instance.
        """
        # Get next version number
        version = self.document_repo.get_next_version(dataset_id, doc_key)
        
        # Mark previous versions as not latest
        previous_versions = self._get_versions(dataset_id, doc_key)
        for prev_version in previous_versions:
            if prev_version.is_latest:
                prev_version.is_latest = False
                prev_version.updated_at = utc_now()
        
        # Create new version
        new_document = DatasetDocument(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            dataset_id=dataset_id,
            doc_key=doc_key,
            version=version,
            is_latest=True,
            status="uploaded",
            **kwargs,
        )
        
        self.db.add(new_document)
        self.db.commit()
        self.db.refresh(new_document)
        
        return new_document
    
    def get_latest_version(
        self,
        dataset_id: str,
        doc_key: str,
    ) -> Optional[DatasetDocument]:
        """Get latest version of document.
        
        Args:
            dataset_id: Dataset ID.
            doc_key: Document key.
            
        Returns:
            Latest DatasetDocument instance or None.
        """
        return self.document_repo.get_by_key(dataset_id, doc_key)
    
    def get_version(
        self,
        dataset_id: str,
        doc_key: str,
        version: int,
    ) -> Optional[DatasetDocument]:
        """Get specific version of document.
        
        Args:
            dataset_id: Dataset ID.
            doc_key: Document key.
            version: Version number.
            
        Returns:
            DatasetDocument instance or None.
        """
        return self.document_repo.get_by_key(dataset_id, doc_key, version=version)
    
    def list_versions(
        self,
        dataset_id: str,
        doc_key: str,
    ) -> List[DatasetDocument]:
        """List all versions of document.
        
        Args:
            dataset_id: Dataset ID.
            doc_key: Document key.
            
        Returns:
            List of DatasetDocument instances.
        """
        return self._get_versions(dataset_id, doc_key)
    
    def rollback_to_version(
        self,
        dataset_id: str,
        doc_key: str,
        target_version: int,
    ) -> DatasetDocument:
        """Rollback to a specific version.
        
        Args:
            dataset_id: Dataset ID.
            doc_key: Document key.
            target_version: Target version number.
            
        Returns:
            Rolled back DatasetDocument instance.
        """
        # Get target version
        target_doc = self.get_version(dataset_id, doc_key, target_version)
        if not target_doc:
            raise ValueError(f"Version {target_version} not found")
        
        # Mark all versions as not latest
        all_versions = self._get_versions(dataset_id, doc_key)
        for version_doc in all_versions:
            if version_doc.is_latest:
                version_doc.is_latest = False
                version_doc.updated_at = utc_now()
        
        # Mark target version as latest
        target_doc.is_latest = True
        target_doc.updated_at = utc_now()
        
        self.db.commit()
        self.db.refresh(target_doc)
        
        return target_doc
    
    def _get_versions(
        self,
        dataset_id: str,
        doc_key: str,
    ) -> List[DatasetDocument]:
        """Get all versions of document.
        
        Args:
            dataset_id: Dataset ID.
            doc_key: Document key.
            
        Returns:
            List of DatasetDocument instances.
        """
        query = select(DatasetDocument).where(
            and_(
                DatasetDocument.tenant_id == self.ctx.tenant_id,
                DatasetDocument.workspace_id == self.ctx.workspace_id,
                DatasetDocument.dataset_id == dataset_id,
                DatasetDocument.doc_key == doc_key,
            )
        ).order_by(DatasetDocument.version.desc())
        
        return list(self.db.exec(query).all())

