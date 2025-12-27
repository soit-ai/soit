""" service

Dataset domain services (ingestion, indexing, retrieval).
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import KernelError
from app.modules.domains.dataset.models import Dataset, DatasetDocument, DatasetIndex
from app.modules.domains.dataset.repository import (
    DatasetRepository,
    DocumentRepository,
    IndexRepository,
)
from app.modules.domains.dataset.schemas import (
    DatasetCreate,
    DatasetUpdate,
    DocumentUpload,
    QueryRequest,
    QueryResponse,
    QueryResult,
)
from app.modules.domains.dataset.pipeline import DocumentPipeline
from app.modules.domains.dataset.retrieval import RetrievalService
from app.modules.domains.dataset.versioning import DocumentVersioning
from app.modules.domains.dataset.index_builder import IndexBuilder
from app.kernel.commons.time import utcnow as utc_now


class DatasetService:
    """Service for managing datasets."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        pipeline: Optional[DocumentPipeline] = None,
        retrieval_service: Optional[RetrievalService] = None,
    ):
        """Initialize dataset service.
        
        Args:
            db: Database session.
            ctx: Request context.
            pipeline: Optional document pipeline (required for document processing).
            retrieval_service: Optional retrieval service (required for querying).
        """
        self.db = db
        self.ctx = ctx
        self.pipeline = pipeline
        self.retrieval_service = retrieval_service
        self.dataset_repo = DatasetRepository(db, ctx)
        self.document_repo = DocumentRepository(db, ctx)
        self.index_repo = IndexRepository(db, ctx)
        self.versioning = DocumentVersioning(db, ctx)
    
    def create_dataset(self, dataset_in: DatasetCreate) -> Dataset:
        """Create a new dataset.
        
        Args:
            dataset_in: Dataset creation schema.
            
        Returns:
            Created Dataset instance.
        """
        # Check if name already exists
        existing = self.dataset_repo.get_by_name(dataset_in.name)
        if existing:
            raise KernelError("DUPLICATE_NAME", f"Dataset '{dataset_in.name}' already exists")
        
        # Create dataset
        dataset = Dataset(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            name=dataset_in.name,
            type=dataset_in.type,
            description=dataset_in.description,
            visibility=dataset_in.visibility,
            settings_json=dataset_in.settings_json or {},
            chunking_json=dataset_in.chunking_json or {},
            retrieval_json=dataset_in.retrieval_json or {},
            default_embedding_model_ref=dataset_in.default_embedding_model_ref,
            default_reranker_ref=dataset_in.default_reranker_ref,
            tags=dataset_in.tags,
            created_by=self.ctx.user_id,
            updated_by=self.ctx.user_id,
        )
        
        dataset = self.dataset_repo.create(dataset)
        return dataset
    
    def get_dataset(self, dataset_id: str) -> Dataset:
        """Get dataset by ID.
        
        Args:
            dataset_id: Dataset ID.
            
        Returns:
            Dataset instance.
        """
        dataset = self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise KernelError("NOT_FOUND", f"Dataset {dataset_id} not found")
        return dataset
    
    def update_dataset(self, dataset_id: str, dataset_in: DatasetUpdate) -> Dataset:
        """Update dataset.
        
        Args:
            dataset_id: Dataset ID.
            dataset_in: Dataset update schema.
            
        Returns:
            Updated Dataset instance.
        """
        dataset = self.get_dataset(dataset_id)
        
        # Update fields
        if dataset_in.name is not None:
            # Check if new name conflicts
            existing = self.dataset_repo.get_by_name(dataset_in.name)
            if existing and existing.id != dataset_id:
                raise KernelError("DUPLICATE_NAME", f"Dataset '{dataset_in.name}' already exists")
            dataset.name = dataset_in.name
        
        if dataset_in.description is not None:
            dataset.description = dataset_in.description
        
        if dataset_in.status is not None:
            dataset.status = dataset_in.status
        
        if dataset_in.visibility is not None:
            dataset.visibility = dataset_in.visibility
        
        if dataset_in.settings_json is not None:
            dataset.settings_json = dataset_in.settings_json
        
        if dataset_in.chunking_json is not None:
            dataset.chunking_json = dataset_in.chunking_json
        
        if dataset_in.retrieval_json is not None:
            dataset.retrieval_json = dataset_in.retrieval_json
        
        if dataset_in.default_embedding_model_ref is not None:
            dataset.default_embedding_model_ref = dataset_in.default_embedding_model_ref
        
        if dataset_in.default_reranker_ref is not None:
            dataset.default_reranker_ref = dataset_in.default_reranker_ref
        
        if dataset_in.tags is not None:
            dataset.tags = dataset_in.tags
        
        dataset.updated_by = self.ctx.user_id
        dataset.updated_at = utc_now()
        
        self.db.commit()
        self.db.refresh(dataset)
        
        return dataset
    
    async def upload_document(
        self,
        dataset_id: str,
        document_in: DocumentUpload,
        file_content: Optional[bytes] = None,
    ) -> DatasetDocument:
        """Upload and process a document.
        
        Args:
            dataset_id: Dataset ID.
            document_in: Document upload schema.
            file_content: Optional file content.
            
        Returns:
            Created DatasetDocument instance.
            
        Raises:
            KernelError: If pipeline is not available.
        """
        if not self.pipeline:
            raise KernelError("PIPELINE_NOT_AVAILABLE", "Document pipeline is not configured")
        
        dataset = self.get_dataset(dataset_id)
        
        # Create new document version
        document = self.versioning.create_version(
            dataset_id=dataset_id,
            doc_key=document_in.doc_key,
            source_type=document_in.source_type,
            source_uri=document_in.source_uri,
            file_id=document_in.file_id,
            title=document_in.title,
            language=document_in.language,
            access_policy_json=document_in.access_policy_json or {},
        )
        
        # Process document through pipeline
        document = await self.pipeline.process_document(document, dataset, file_content)
        
        # Update dataset last_ingested_at
        dataset.last_ingested_at = utc_now()
        self.db.commit()
        
        return document
    
    def list_documents(
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
        return self.document_repo.list_by_dataset(
            dataset_id=dataset_id,
            is_latest_only=is_latest_only,
            limit=limit,
            offset=offset,
        )
    
    def get_document(self, document_id: str) -> DatasetDocument:
        """Get document by ID.
        
        Args:
            document_id: Document ID.
            
        Returns:
            DatasetDocument instance.
        """
        document = self.document_repo.get_by_id(document_id)
        if not document:
            raise KernelError("NOT_FOUND", f"Document {document_id} not found")
        return document
    
    def delete_document(self, document_id: str) -> None:
        """Delete document (soft delete).
        
        Args:
            document_id: Document ID.
        """
        document = self.get_document(document_id)
        
        # Soft delete
        from datetime import datetime, timezone
        document.deleted_at = datetime.now(timezone.utc)
        document.status = "deleted"
        document.updated_at = utc_now()
        
        self.db.commit()
    
    async def rebuild_index(self, dataset_id: str, index_id: Optional[str] = None) -> DatasetIndex:
        """Rebuild index.
        
        Args:
            dataset_id: Dataset ID.
            index_id: Optional index ID (use primary if not specified).
            
        Returns:
            Updated DatasetIndex instance.
        """
        dataset = self.get_dataset(dataset_id)
        
        # Get index
        if index_id:
            index = self.index_repo.get_by_id(index_id)
        else:
            index = self.index_repo.get_primary(dataset_id)
        
        if not index:
            raise KernelError("NOT_FOUND", "No index found for dataset")
        
        # Rebuild index
        from app.modules.domains.dataset.index_builder import IndexBuilder
        # Note: IndexBuilder needs to be initialized with proper dependencies
        # For now, this is a placeholder
        # await index_builder.rebuild_index(index)
        
        index.status = "ready"
        index.updated_at = utc_now()
        self.db.commit()
        
        return index
    
    async def query(
        self,
        dataset_id: str,
        query_request: QueryRequest,
    ) -> QueryResponse:
        """Query dataset for relevant documents.
        
        Args:
            dataset_id: Dataset ID.
            query_request: Query request schema.
            
        Returns:
            QueryResponse instance.
            
        Raises:
            KernelError: If retrieval service is not available.
        """
        if not self.retrieval_service:
            raise KernelError("RETRIEVAL_NOT_AVAILABLE", "Retrieval service is not configured")
        
        results = await self.retrieval_service.query(
            dataset_id=dataset_id,
            query_text=query_request.query,
            top_k=query_request.top_k,
            index_id=query_request.index_id,
            filter=query_request.filter,
            use_rerank=query_request.use_rerank,
            reranker_ref=query_request.reranker_ref,
        )
        
        return QueryResponse(
            results=results,
            total=len(results),
        )
    
    def list_datasets(
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
        return self.dataset_repo.list(limit=limit, offset=offset)
    
    def delete_dataset(self, dataset_id: str) -> None:
        """Delete a dataset (soft delete).
        
        Args:
            dataset_id: Dataset ID.
            
        Raises:
            KernelError: If dataset not found.
        """
        dataset = self.get_dataset(dataset_id)
        
        # Soft delete dataset
        from datetime import datetime, timezone
        dataset.deleted_at = datetime.now(timezone.utc)
        dataset.status = "deleted"
        dataset.updated_at = utc_now()
        
        # Also soft delete associated documents
        documents = self.document_repo.list_by_dataset(
            dataset_id=dataset_id,
            is_latest_only=False,
            limit=10000,  # Large limit to get all documents
            offset=0,
        )
        for doc in documents:
            doc.deleted_at = datetime.now(timezone.utc)
            doc.status = "deleted"
            doc.updated_at = utc_now()
        
        self.db.commit()