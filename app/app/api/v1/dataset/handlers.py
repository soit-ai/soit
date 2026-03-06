""" handlers

Dataset request handlers (thin orchestration).
"""

from typing import List, Optional
from datetime import datetime
from fastapi import HTTPException, status, UploadFile, File

from app.kernel.contracts.context import RequestContext
from app.modules.dataset.application.service import DatasetService
from app.modules.dataset.application.schemas import (
    DatasetCreate,
    DatasetUpdate,
    DatasetResponse,
    DocumentUpload,
    DocumentResponse,
    ChunkResponse,
    ChunkUpdate,
    QueryRequest,
    QueryResponse,
    IndexResponse,
    IndexCreate,
    IndexUpdate,
    IngestTaskResponse,
    DatasetApplicationUsageResponse,
)
from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.trace.schemas import (
    RunResponse,
    RunCostSummaryResponse,
    RunCostByModeResponse,
    RunCostByProviderResponse,
    RunCostByModelResponse,
)


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
        dataset = await self.service.create_dataset(dataset_in)
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
        dataset = await self.service.get_dataset(dataset_id)
        return DatasetResponse.model_validate(dataset)
    
    async def list_datasets(
        self,
        ctx: RequestContext,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[DatasetResponse]:
        """List datasets.
        
        Args:
            ctx: Request context.
            page_token: Optional page token.
            page_size: Page size.
            
        Returns:
            Paginated datasets.
        """
        from app.infra.db.pagination import parse_page_params
        
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        
        datasets = await self.service.list_datasets(limit=limit, offset=offset)
        
        items = [DatasetResponse.model_validate(ds) for ds in datasets]
        
        has_next = len(datasets) == limit
        next_offset = offset + len(datasets) if has_next else None
        
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )
    
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
        dataset = await self.service.update_dataset(dataset_id, dataset_in)
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
        await self.service.delete_dataset(dataset_id)
    
    async def upload_document(
        self,
        ctx: RequestContext,
        dataset_id: str,
        document_in: DocumentUpload,
        file: Optional[UploadFile] = None,
        async_ingest: bool = False,
        max_retries: int = 1,
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

        document = await self.service.upload_document(
            dataset_id,
            document_in,
            file_content,
            async_ingest=async_ingest,
            max_retries=max_retries,
        )
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
        documents = await self.service.list_documents(dataset_id, is_latest_only, limit, offset)
        return [DocumentResponse.model_validate(doc) for doc in documents]

    async def list_chunks(
        self,
        ctx: RequestContext,
        dataset_id: str,
        document_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ChunkResponse]:
        """List chunks for a document."""
        chunks = await self.service.list_chunks(dataset_id, document_id, limit, offset)
        return [ChunkResponse.model_validate(chunk) for chunk in chunks]

    async def update_chunk(
        self,
        ctx: RequestContext,
        dataset_id: str,
        document_id: str,
        chunk_id: str,
        chunk_in: ChunkUpdate,
    ) -> ChunkResponse:
        """Update chunk content or status."""
        chunk = await self.service.update_chunk(
            dataset_id=dataset_id,
            document_id=document_id,
            chunk_id=chunk_id,
            content=chunk_in.content,
            index_status=chunk_in.index_status,
        )
        return ChunkResponse.model_validate(chunk)
    
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
        document = await self.service.get_document(document_id)
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
        await self.service.delete_document(document_id)

    async def get_document_content(
        self,
        ctx: RequestContext,
        dataset_id: str,
        document_id: str,
    ) -> tuple[bytes, str]:
        """Get document content for preview."""
        return await self.service.get_document_content(dataset_id, document_id)

    async def download_document(
        self,
        ctx: RequestContext,
        dataset_id: str,
        document_id: str,
    ) -> tuple[bytes, str, str]:
        """Download document file."""
        return await self.service.download_document(dataset_id, document_id)
    
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

    async def create_index(
        self,
        ctx: RequestContext,
        dataset_id: str,
        index_in: IndexCreate,
    ) -> IndexResponse:
        """Create a new index.

        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            index_in: Index creation data.

        Returns:
            Created index.
        """
        index = await self.service.create_index(dataset_id, index_in)
        return IndexResponse.model_validate(index)

    async def list_indexes(
        self,
        ctx: RequestContext,
        dataset_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[IndexResponse]:
        """List indexes for dataset.

        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            limit: Max indexes.
            offset: Offset.

        Returns:
            List of indexes.
        """
        indexes = await self.service.list_indexes(dataset_id, limit=limit, offset=offset)
        return [IndexResponse.model_validate(item) for item in indexes]

    async def get_index(
        self,
        ctx: RequestContext,
        dataset_id: str,
        index_id: str,
    ) -> IndexResponse:
        """Get index by ID.

        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            index_id: Index ID.

        Returns:
            Index details.
        """
        index = await self.service.get_index(dataset_id, index_id)
        return IndexResponse.model_validate(index)

    async def update_index(
        self,
        ctx: RequestContext,
        dataset_id: str,
        index_id: str,
        index_in: IndexUpdate,
    ) -> IndexResponse:
        """Update index.

        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            index_id: Index ID.
            index_in: Index update data.

        Returns:
            Updated index.
        """
        index = await self.service.update_index(dataset_id, index_id, index_in)
        return IndexResponse.model_validate(index)

    async def delete_index(
        self,
        ctx: RequestContext,
        dataset_id: str,
        index_id: str,
    ) -> None:
        """Delete index.

        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            index_id: Index ID.
        """
        await self.service.delete_index(dataset_id, index_id)

    async def list_document_versions(
        self,
        ctx: RequestContext,
        dataset_id: str,
        doc_key: str,
    ) -> List[DocumentResponse]:
        """List document versions by doc_key.

        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            doc_key: Document key.

        Returns:
            List of document versions.
        """
        versions = await self.service.list_document_versions(dataset_id, doc_key)
        return [DocumentResponse.model_validate(item) for item in versions]

    async def rollback_document_version(
        self,
        ctx: RequestContext,
        dataset_id: str,
        doc_key: str,
        version: int,
    ) -> DocumentResponse:
        """Rollback document to a specific version.

        Args:
            ctx: Request context.
            dataset_id: Dataset ID.
            doc_key: Document key.
            version: Version number.

        Returns:
            Rolled back document.
        """
        document = await self.service.rollback_document_version(dataset_id, doc_key, version)
        return DocumentResponse.model_validate(document)

    async def list_ingest_tasks(
        self,
        ctx: RequestContext,
        dataset_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[IngestTaskResponse]:
        """List ingest tasks for a dataset."""
        tasks = await self.service.list_ingest_tasks(dataset_id, status=status, limit=limit, offset=offset)
        return [IngestTaskResponse.model_validate(item) for item in tasks]

    async def get_ingest_task(
        self,
        ctx: RequestContext,
        dataset_id: str,
        task_id: str,
    ) -> IngestTaskResponse:
        """Get ingest task by ID."""
        task = await self.service.get_ingest_task(dataset_id, task_id)
        return IngestTaskResponse.model_validate(task)

    async def retry_ingest_task(
        self,
        ctx: RequestContext,
        dataset_id: str,
        task_id: str,
    ) -> IngestTaskResponse:
        """Retry an ingest task."""
        task = await self.service.retry_ingest_task(dataset_id, task_id)
        return IngestTaskResponse.model_validate(task)

    async def retry_document_ingest(
        self,
        ctx: RequestContext,
        dataset_id: str,
        document_id: str,
        max_retries: int = 1,
    ) -> IngestTaskResponse:
        """Retry ingestion for a document."""
        task = await self.service.retry_document_ingest(dataset_id, document_id, max_retries=max_retries)
        return IngestTaskResponse.model_validate(task)

    async def cancel_ingest_task(
        self,
        ctx: RequestContext,
        dataset_id: str,
        task_id: str,
    ) -> IngestTaskResponse:
        """Cancel an ingest task."""
        task = await self.service.cancel_ingest_task(dataset_id, task_id)
        return IngestTaskResponse.model_validate(task)

    async def list_dataset_runs(
        self,
        ctx: RequestContext,
        dataset_id: str,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[RunResponse]:
        """List runs scoped to a dataset."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        limit_plus = limit + 1
        runs = await self.service.list_runs_for_dataset(
            dataset_id,
            mode=mode,
            kind=kind,
            status=status,
            started_after=started_after,
            started_before=started_before,
            limit=limit_plus,
            offset=offset,
        )
        has_next = len(runs) > limit
        items = runs[:limit]
        next_offset = offset + len(items) if has_next else None
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def summarize_dataset_run_costs(
        self,
        ctx: RequestContext,
        dataset_id: str,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> RunCostSummaryResponse:
        """Summarize run costs scoped to a dataset."""
        return await self.service.summarize_run_costs_for_dataset(
            dataset_id,
            mode=mode,
            kind=kind,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def summarize_dataset_run_costs_by_mode(
        self,
        ctx: RequestContext,
        dataset_id: str,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> List[RunCostByModeResponse]:
        """Summarize run costs by mode scoped to a dataset."""
        return await self.service.summarize_run_costs_by_mode_for_dataset(
            dataset_id,
            mode=mode,
            kind=kind,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def summarize_dataset_run_costs_by_provider(
        self,
        ctx: RequestContext,
        dataset_id: str,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> List[RunCostByProviderResponse]:
        """Summarize run costs by provider scoped to a dataset."""
        return await self.service.summarize_run_costs_by_provider_for_dataset(
            dataset_id,
            mode=mode,
            kind=kind,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def summarize_dataset_run_costs_by_model(
        self,
        ctx: RequestContext,
        dataset_id: str,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> List[RunCostByModelResponse]:
        """Summarize run costs by model scoped to a dataset."""
        return await self.service.summarize_run_costs_by_model_for_dataset(
            dataset_id,
            mode=mode,
            kind=kind,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def list_dataset_app_usages(
        self,
        ctx: RequestContext,
        dataset_id: str,
        limit: int = 100,
    ) -> List[DatasetApplicationUsageResponse]:
        """List app usages for a dataset."""
        return await self.service.list_dataset_app_usages(dataset_id, limit=limit)
