""" repository

Dataset repositories using scope-aware base.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.dataset.domain.models import (
    Dataset,
    DatasetDocument,
    DatasetChunk,
    DatasetIndex,
)


class DatasetRepository(Repository[Dataset]):
    """Repository for Dataset model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize dataset repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Dataset, db, ctx)
    
    def get_by_name(self, name: str) -> Optional[Dataset]:
        """Get dataset by name.
        
        Args:
            ctx: Request context.
            name: Dataset name.
            
        Returns:
            Dataset instance or None if not found.
        """
        query = select(Dataset).where(
            and_(
                Dataset.tenant_id == self.ctx.tenant_id,
                Dataset.workspace_id == self.ctx.workspace_id,
                Dataset.name == name,
            )
        )
        return self.db.exec(query).first()
    
    def list(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dataset]:
        """List datasets.
        
        Args:
            limit: Maximum number of datasets.
            offset: Offset for pagination.
            
        Returns:
            List of Dataset instances.
        """
        query = select(Dataset).where(
            and_(
                Dataset.tenant_id == self.ctx.tenant_id,
                Dataset.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(Dataset.created_at.desc()).offset(offset).limit(limit)
        
        return list(self.db.exec(query).all())
    
    def update_stats(
        self,
        dataset_id: str,
        doc_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
    ) -> Dataset:
        """Update dataset statistics.
        
        Args:
            dataset_id: Dataset ID.
            doc_count: Optional document count to set.
            chunk_count: Optional chunk count to set.
            
        Returns:
            Updated Dataset instance.
        """
        dataset = self.get_by_id(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")
        
        if doc_count is not None:
            dataset.doc_count = doc_count
        if chunk_count is not None:
            dataset.chunk_count = chunk_count
        
        from app.kernel.commons.time import utc_now
        dataset.updated_at = utc_now()
        
        self.db.commit()
        self.db.refresh(dataset)
        return dataset


class DocumentRepository(Repository[DatasetDocument]):
    """Repository for DatasetDocument model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize document repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(DatasetDocument, db, ctx)
    
    def get_by_key(
        self,
        dataset_id: str,
        doc_key: str,
        version: Optional[int] = None,
    ) -> Optional[DatasetDocument]:
        """Get document by key and optional version.
        
        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            doc_key: Document key.
            version: Optional version number (if None, get latest).
            
        Returns:
            DatasetDocument instance or None if not found.
        """
        query = select(DatasetDocument).where(
            and_(
                DatasetDocument.tenant_id == self.ctx.tenant_id,
                DatasetDocument.workspace_id == self.ctx.workspace_id,
                DatasetDocument.dataset_id == dataset_id,
                DatasetDocument.doc_key == doc_key,
            )
        )
        
        if version:
            query = query.where(DatasetDocument.version == version)
        else:
            query = query.where(DatasetDocument.is_latest == True)
        
        return self.db.exec(query).first()
    
    def list_by_dataset(
        self,
        dataset_id: str,
        is_latest_only: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> List[DatasetDocument]:
        """List documents in dataset.
        
        Args:
            dataset_id: Dataset ID.
            is_latest_only: Only return latest versions.
            limit: Maximum number of documents.
            offset: Offset for pagination.
            
        Returns:
            List of DatasetDocument instances.
        """
        query = select(DatasetDocument).where(
            and_(
                DatasetDocument.tenant_id == self.ctx.tenant_id,
                DatasetDocument.workspace_id == self.ctx.workspace_id,
                DatasetDocument.dataset_id == dataset_id,
            )
        )
        
        if is_latest_only:
            query = query.where(DatasetDocument.is_latest == True)
        
        query = query.order_by(DatasetDocument.created_at.desc()).offset(offset).limit(limit)
        
        return list(self.db.exec(query).all())
    
    def get_next_version(self, dataset_id: str, doc_key: str) -> int:
        """Get next version number for document key.
        
        Args:
            dataset_id: Dataset ID.
            doc_key: Document key.
            
        Returns:
            Next version number.
        """
        query = select(func.max(DatasetDocument.version)).where(
            and_(
                DatasetDocument.tenant_id == self.ctx.tenant_id,
                DatasetDocument.workspace_id == self.ctx.workspace_id,
                DatasetDocument.dataset_id == dataset_id,
                DatasetDocument.doc_key == doc_key,
            )
        )
        max_version = self.db.exec(query).one()
        return (max_version or 0) + 1
    
    def count_by_dataset(self, dataset_id: str) -> int:
        """Count documents in dataset (latest versions only).
        
        Args:
            dataset_id: Dataset ID.
            
        Returns:
            Document count.
        """
        query = select(func.count()).select_from(DatasetDocument).where(
            and_(
                DatasetDocument.tenant_id == self.ctx.tenant_id,
                DatasetDocument.workspace_id == self.ctx.workspace_id,
                DatasetDocument.dataset_id == dataset_id,
                DatasetDocument.is_latest == True,
            )
        )
        return self.db.exec(query).one()


class ChunkRepository(Repository[DatasetChunk]):
    """Repository for DatasetChunk model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize chunk repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(DatasetChunk, db, ctx)
    
    def list_by_document(
        self,
        document_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[DatasetChunk]:
        """List chunks for a document.
        
        Args:
            document_id: Document ID.
            limit: Maximum number of chunks.
            offset: Offset for pagination.
            
        Returns:
            List of DatasetChunk instances.
        """
        query = select(DatasetChunk).where(
            and_(
                DatasetChunk.tenant_id == self.ctx.tenant_id,
                DatasetChunk.workspace_id == self.ctx.workspace_id,
                DatasetChunk.document_id == document_id,
            )
        ).order_by(DatasetChunk.chunk_no).offset(offset).limit(limit)
        
        return list(self.db.exec(query).all())
    
    def list_by_dataset(
        self,
        dataset_id: str,
        index_status: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[DatasetChunk]:
        """List chunks in dataset.
        
        Args:
            dataset_id: Dataset ID.
            index_status: Optional filter by index_status.
            limit: Maximum number of chunks.
            offset: Offset for pagination.
            
        Returns:
            List of DatasetChunk instances.
        """
        query = select(DatasetChunk).where(
            and_(
                DatasetChunk.tenant_id == self.ctx.tenant_id,
                DatasetChunk.workspace_id == self.ctx.workspace_id,
                DatasetChunk.dataset_id == dataset_id,
            )
        )
        
        if index_status:
            query = query.where(DatasetChunk.index_status == index_status)
        
        query = query.order_by(DatasetChunk.created_at.desc()).offset(offset).limit(limit)
        
        return list(self.db.exec(query).all())
    
    def count_by_dataset(self, dataset_id: str) -> int:
        """Count chunks in dataset.
        
        Args:
            dataset_id: Dataset ID.
            
        Returns:
            Chunk count.
        """
        query = select(func.count()).select_from(DatasetChunk).where(
            and_(
                DatasetChunk.tenant_id == self.ctx.tenant_id,
                DatasetChunk.workspace_id == self.ctx.workspace_id,
                DatasetChunk.dataset_id == dataset_id,
            )
        )
        return self.db.exec(query).one()


class IndexRepository(Repository[DatasetIndex]):
    """Repository for DatasetIndex model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize index repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(DatasetIndex, db, ctx)
    
    def get_by_name(self, dataset_id: str, name: str) -> Optional[DatasetIndex]:
        """Get index by name.
        
        Args:
            dataset_id: Dataset ID.
            name: Index name.
            
        Returns:
            DatasetIndex instance or None if not found.
        """
        query = select(DatasetIndex).where(
            and_(
                DatasetIndex.tenant_id == self.ctx.tenant_id,
                DatasetIndex.workspace_id == self.ctx.workspace_id,
                DatasetIndex.dataset_id == dataset_id,
                DatasetIndex.name == name,
            )
        )
        return self.db.exec(query).first()
    
    def get_primary(self, dataset_id: str) -> Optional[DatasetIndex]:
        """Get primary index for dataset.
        
        Args:
            dataset_id: Dataset ID.
            
        Returns:
            Primary DatasetIndex instance or None if not found.
        """
        query = select(DatasetIndex).where(
            and_(
                DatasetIndex.tenant_id == self.ctx.tenant_id,
                DatasetIndex.workspace_id == self.ctx.workspace_id,
                DatasetIndex.dataset_id == dataset_id,
                DatasetIndex.is_primary == True,
            )
        )
        return self.db.exec(query).first()
    
    def list_by_dataset(
        self,
        dataset_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[DatasetIndex]:
        """List indexes for dataset.
        
        Args:
            dataset_id: Dataset ID.
            limit: Maximum number of indexes.
            offset: Offset for pagination.
            
        Returns:
            List of DatasetIndex instances.
        """
        query = select(DatasetIndex).where(
            and_(
                DatasetIndex.tenant_id == self.ctx.tenant_id,
                DatasetIndex.workspace_id == self.ctx.workspace_id,
                DatasetIndex.dataset_id == dataset_id,
            )
        ).order_by(DatasetIndex.created_at.desc()).offset(offset).limit(limit)
        
        return list(self.db.exec(query).all())
