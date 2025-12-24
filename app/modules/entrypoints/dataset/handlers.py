""" handlers

Dataset request handlers (thin orchestration).
"""

from typing import List, Optional
from fastapi import HTTPException, status, UploadFile, File

from app.kernel.contracts.context import RequestContext
from app.modules.domains.dataset.service import DatasetService
from app.modules.domains.dataset.schemas import (
    DatasetCreate,
    DatasetUpdate,
    DatasetResponse,
    DocumentUpload,
    DocumentResponse,
    QueryRequest,
    QueryResponse,
    IndexResponse,
)
from app.kernel.db.pagination import PaginatedResponse


class DatasetHandlers:
    """Handlers for dataset API endpoints."""
    
    def __init__(self, service: DatasetService):
        """Initialize dataset handlers.
        
        Args:
            service: DatasetService instance.
        """
        self.service = service
    
    async def create_dataset(
        self,
        ctx: RequestContext,
        dataset_in: DatasetCreate,
    ) -> DatasetResponse:
        """Create a new dataset.
        
        Args:
            ctx: Request context.
            dataset_in: Dataset creation schema.
            
        Returns:
            Created dataset.
        """
        dataset = self.service.create_dataset(dataset_in)
        return DatasetResponse.model_validate(dataset)
    
    async def get_dataset(
        self,
        ctx: RequestContext,
        dataset_id: str,
    ) -> DatasetResponse:
        """Get dataset by ID.
        
        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            
        Returns:
            Dataset details.
        """
        dataset = self.service.get_dataset(dataset_id)
        return DatasetResponse.model_validate(dataset)
    
    async def update_dataset(
        self,
        ctx: RequestContext,
        dataset_id: str,
        dataset_in: DatasetUpdate,
    ) -> DatasetResponse:
        """Update dataset.
        
        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            dataset_in: Dataset update schema.
            
        Returns:
            Updated dataset.
        """
        dataset = self.service.update_dataset(dataset_id, dataset_in)
        return DatasetResponse.model_validate(dataset)
    
    async def delete_dataset(
        self,
        ctx: RequestContext,
        dataset_id: str,
    ) -> None:
        """Delete dataset.
        
        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
        """
        self.service.delete_dataset(dataset_id)
    
    async def upload_document(
        self,
        ctx: RequestContext,
        dataset_id: str,
        document_in: DocumentUpload,
        file: Optional[UploadFile] = None,
    ) -> DocumentResponse:
        """Upload and process a document.
        
        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            document_in: Document upload schema.
            file: Optional uploaded file.
            
        Returns:
            Created document.
        """
        file_content = None
        if file:
            file_content = await file.read()
        
        document = await self.service.upload_document(dataset_id, document_in, file_content)
        return DocumentResponse.model_validate(document)
    
    async def list_documents(
        self,
        ctx: RequestContext,
        dataset_id: str,
        is_latest_only: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> List[DocumentResponse]:
        """List documents in dataset.
        
        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            is_latest_only: Only return latest versions.
            limit: Maximum number of documents.
            offset: Offset for pagination.
            
        Returns:
            List of documents.
        """
        documents = self.service.list_documents(dataset_id, is_latest_only, limit, offset)
        return [DocumentResponse.model_validate(doc) for doc in documents]
    
    async def get_document(
        self,
        ctx: RequestContext,
        document_id: str,
    ) -> DocumentResponse:
        """Get document by ID.
        
        Args:
            ctx: Request context.
            document_id: Document ID.
            
        Returns:
            Document details.
        """
        document = self.service.get_document(document_id)
        return DocumentResponse.model_validate(document)
    
    async def delete_document(
        self,
        ctx: RequestContext,
        document_id: str,
    ) -> None:
        """Delete document.
        
        Args:
            ctx: Request context.
            document_id: Document ID.
        """
        self.service.delete_document(document_id)
    
    async def query_dataset(
        self,
        ctx: RequestContext,
        dataset_id: str,
        query_request: QueryRequest,
    ) -> QueryResponse:
        """Query dataset for relevant documents.
        
        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            query_request: Query request schema.
            
        Returns:
            Query results.
        """
        return await self.service.query(dataset_id, query_request)
    
    async def rebuild_index(
        self,
        ctx: RequestContext,
        dataset_id: str,
        index_id: Optional[str] = None,
    ) -> IndexResponse:
        """Rebuild index.
        
        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            index_id: Optional index ID.
            
        Returns:
            Updated index.
        """
        index = await self.service.rebuild_index(dataset_id, index_id)
        return IndexResponse.model_validate(index)

