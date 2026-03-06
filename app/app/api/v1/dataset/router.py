""" router

Dataset API routes (FastAPI).
"""

from typing import Optional
from datetime import datetime
import json
from fastapi import APIRouter, Depends, status, Body, UploadFile, File, Form, HTTPException, Response
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.infra.db.pagination import PaginatedResponse
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
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
from app.kernel.trace.schemas import (
    RunResponse,
    RunCostSummaryResponse,
    RunCostByModeResponse,
    RunCostByProviderResponse,
    RunCostByModelResponse,
)
from app.api.v1.dataset.dependencies import get_dataset_service
from app.api.v1.dataset.handlers import DatasetHandlers


router = APIRouter()


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    dataset_in: DatasetCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Create a new dataset.
    
    Args:
        dataset_in: Dataset creation data.
        ctx: Request context.
        service: DatasetService instance.
        
    Returns:
        Created dataset.
    """
    handlers = DatasetHandlers(service)
    return await handlers.create_dataset(ctx, dataset_in)


@router.get("", response_model=PaginatedResponse[DatasetResponse])
async def list_datasets(
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """List datasets.
    
    Args:
        page_token: Optional page token.
        page_size: Page size.
        ctx: Request context.
        service: DatasetService instance.
        
    Returns:
        Paginated datasets.
    """
    handlers = DatasetHandlers(service)
    return await handlers.list_datasets(ctx, page_token, page_size)


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Get dataset by ID.
    
    Args:
        dataset_id: Dataset ID.
        ctx: Request context.
        service: DatasetService instance.
        
    Returns:
        Dataset details.
    """
    handlers = DatasetHandlers(service)
    return await handlers.get_dataset(ctx, dataset_id)


@router.put("/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: str,
    dataset_in: DatasetUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Update dataset.
    
    Args:
        dataset_id: Dataset ID.
        dataset_in: Dataset update data.
        ctx: Request context.
        service: DatasetService instance.
        
    Returns:
        Updated dataset.
    """
    handlers = DatasetHandlers(service)
    return await handlers.update_dataset(ctx, dataset_id, dataset_in)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Delete dataset.
    
    Args:
        dataset_id: Dataset ID.
        ctx: Request context.
        service: DatasetService instance.
    """
    handlers = DatasetHandlers(service)
    await handlers.delete_dataset(ctx, dataset_id)


@router.post("/{dataset_id}/indexes", response_model=IndexResponse, status_code=status.HTTP_201_CREATED)
async def create_index(
    dataset_id: str,
    index_in: IndexCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Create a new index.

    Args:
        dataset_id: Dataset ID.
        index_in: Index creation data.
        ctx: Request context.
        service: DatasetService instance.

    Returns:
        Created index.
    """
    handlers = DatasetHandlers(service)
    return await handlers.create_index(ctx, dataset_id, index_in)


@router.get("/{dataset_id}/indexes", response_model=list[IndexResponse])
async def list_indexes(
    dataset_id: str,
    limit: int = 20,
    offset: int = 0,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """List indexes for dataset.

    Args:
        dataset_id: Dataset ID.
        limit: Max indexes.
        offset: Offset.
        ctx: Request context.
        service: DatasetService instance.

    Returns:
        List of indexes.
    """
    handlers = DatasetHandlers(service)
    return await handlers.list_indexes(ctx, dataset_id, limit, offset)


@router.get("/{dataset_id}/indexes/{index_id}", response_model=IndexResponse)
async def get_index(
    dataset_id: str,
    index_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Get index by ID.

    Args:
        dataset_id: Dataset ID.
        index_id: Index ID.
        ctx: Request context.
        service: DatasetService instance.

    Returns:
        Index details.
    """
    handlers = DatasetHandlers(service)
    return await handlers.get_index(ctx, dataset_id, index_id)


@router.patch("/{dataset_id}/indexes/{index_id}", response_model=IndexResponse)
async def update_index(
    dataset_id: str,
    index_id: str,
    index_in: IndexUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Update index.

    Args:
        dataset_id: Dataset ID.
        index_id: Index ID.
        index_in: Index update data.
        ctx: Request context.
        service: DatasetService instance.

    Returns:
        Updated index.
    """
    handlers = DatasetHandlers(service)
    return await handlers.update_index(ctx, dataset_id, index_id, index_in)


@router.delete("/{dataset_id}/indexes/{index_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_index(
    dataset_id: str,
    index_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Delete index.

    Args:
        dataset_id: Dataset ID.
        index_id: Index ID.
        ctx: Request context.
        service: DatasetService instance.
    """
    handlers = DatasetHandlers(service)
    await handlers.delete_index(ctx, dataset_id, index_id)


@router.post("/{dataset_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    dataset_id: str,
    doc_key: str = Form(...),
    source_type: str = Form(...),
    source_uri: Optional[str] = Form(None),
    file_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    mime_type: Optional[str] = Form(None),
    filename: Optional[str] = Form(None),
    size_bytes: Optional[int] = Form(None),
    checksum: Optional[str] = Form(None),
    content_hash: Optional[str] = Form(None),
    access_policy_json: Optional[str] = Form(None),
    async_ingest: bool = Form(True),
    max_retries: int = Form(1),
    file: Optional[UploadFile] = File(None),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Upload and process a document.
    
    Args:
        dataset_id: Dataset ID.
        doc_key: Document key.
        source_type: Source type.
        file: Optional uploaded file.
        ctx: Request context.
        service: DatasetService instance.
        
    Returns:
        Created document.
    """
    if file and not filename:
        filename = file.filename
    if file and not mime_type:
        mime_type = file.content_type

    access_policy = {}
    if access_policy_json:
        try:
            access_policy = json.loads(access_policy_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid access_policy_json",
            ) from exc

    document_in = DocumentUpload(
        doc_key=doc_key,
        source_type=source_type,
        source_uri=source_uri,
        file_id=file_id,
        title=title,
        language=language,
        mime_type=mime_type,
        filename=filename,
        size_bytes=size_bytes,
        checksum=checksum,
        content_hash=content_hash,
        access_policy_json=access_policy,
    )
    handlers = DatasetHandlers(service)
    return await handlers.upload_document(
        ctx,
        dataset_id,
        document_in,
        file,
        async_ingest=async_ingest,
        max_retries=max_retries,
    )


@router.get("/{dataset_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    dataset_id: str,
    is_latest_only: bool = True,
    limit: int = 20,
    offset: int = 0,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """List documents in dataset.
    
    Args:
        dataset_id: Dataset ID.
        is_latest_only: Only return latest versions.
        limit: Maximum number of documents.
        offset: Offset for pagination.
        ctx: Request context.
        service: DatasetService instance.
        
    Returns:
        List of documents.
    """
    handlers = DatasetHandlers(service)
    return await handlers.list_documents(ctx, dataset_id, is_latest_only, limit, offset)


@router.get("/{dataset_id}/documents/{document_id}/chunks", response_model=list[ChunkResponse])
async def list_document_chunks(
    dataset_id: str,
    document_id: str,
    limit: int = 100,
    offset: int = 0,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """List chunks for a document."""
    handlers = DatasetHandlers(service)
    return await handlers.list_chunks(ctx, dataset_id, document_id, limit, offset)


@router.patch("/{dataset_id}/documents/{document_id}/chunks/{chunk_id}", response_model=ChunkResponse)
async def update_document_chunk(
    dataset_id: str,
    document_id: str,
    chunk_id: str,
    chunk_in: ChunkUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Update chunk content or status."""
    handlers = DatasetHandlers(service)
    return await handlers.update_chunk(ctx, dataset_id, document_id, chunk_id, chunk_in)


@router.get("/{dataset_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    dataset_id: str,
    document_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Get document by ID.
    
    Args:
        dataset_id: Dataset ID.
        document_id: Document ID.
        ctx: Request context.
        service: DatasetService instance.
        
    Returns:
        Document details.
    """
    handlers = DatasetHandlers(service)
    return await handlers.get_document(ctx, document_id)


@router.get("/{dataset_id}/documents/{document_id}/content")
async def get_document_content(
    dataset_id: str,
    document_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Get document content for preview."""
    handlers = DatasetHandlers(service)
    content, media_type = await handlers.get_document_content(ctx, dataset_id, document_id)
    return Response(content=content, media_type=media_type)


@router.get("/{dataset_id}/documents/{document_id}/download")
async def download_document(
    dataset_id: str,
    document_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Download document file."""
    handlers = DatasetHandlers(service)
    content, media_type, filename = await handlers.download_document(ctx, dataset_id, document_id)
    headers = {"Content-Disposition": f'attachment; filename=\"{filename}\"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{dataset_id}/documents/{doc_key}/versions", response_model=list[DocumentResponse])
async def list_document_versions(
    dataset_id: str,
    doc_key: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """List document versions by doc_key.

    Args:
        dataset_id: Dataset ID.
        doc_key: Document key.
        ctx: Request context.
        service: DatasetService instance.

    Returns:
        List of document versions.
    """
    handlers = DatasetHandlers(service)
    return await handlers.list_document_versions(ctx, dataset_id, doc_key)


@router.post(
    "/{dataset_id}/documents/{doc_key}/versions/{version}/rollback",
    response_model=DocumentResponse,
)
async def rollback_document_version(
    dataset_id: str,
    doc_key: str,
    version: int,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Rollback document to a specific version.

    Args:
        dataset_id: Dataset ID.
        doc_key: Document key.
        version: Version number.
        ctx: Request context.
        service: DatasetService instance.

    Returns:
        Rolled back document.
    """
    handlers = DatasetHandlers(service)
    return await handlers.rollback_document_version(ctx, dataset_id, doc_key, version)


@router.delete("/{dataset_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    dataset_id: str,
    document_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Delete document.
    
    Args:
        dataset_id: Dataset ID.
        document_id: Document ID.
        ctx: Request context.
        service: DatasetService instance.
    """
    handlers = DatasetHandlers(service)
    await handlers.delete_document(ctx, document_id)


@router.get("/{dataset_id}/ingest-tasks", response_model=list[IngestTaskResponse])
async def list_ingest_tasks(
    dataset_id: str,
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """List ingest tasks for dataset."""
    handlers = DatasetHandlers(service)
    return await handlers.list_ingest_tasks(
        ctx,
        dataset_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/{dataset_id}/ingest-tasks/{task_id}", response_model=IngestTaskResponse)
async def get_ingest_task(
    dataset_id: str,
    task_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Get ingest task by ID."""
    handlers = DatasetHandlers(service)
    return await handlers.get_ingest_task(ctx, dataset_id, task_id)


@router.post("/{dataset_id}/ingest-tasks/{task_id}/retry", response_model=IngestTaskResponse)
async def retry_ingest_task(
    dataset_id: str,
    task_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Retry ingest task by ID."""
    handlers = DatasetHandlers(service)
    return await handlers.retry_ingest_task(ctx, dataset_id, task_id)


@router.post("/{dataset_id}/ingest-tasks/{task_id}/cancel", response_model=IngestTaskResponse)
async def cancel_ingest_task(
    dataset_id: str,
    task_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Cancel ingest task by ID."""
    handlers = DatasetHandlers(service)
    return await handlers.cancel_ingest_task(ctx, dataset_id, task_id)


@router.post("/{dataset_id}/documents/{document_id}/retry-ingest", response_model=IngestTaskResponse)
async def retry_document_ingest(
    dataset_id: str,
    document_id: str,
    max_retries: int = 1,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Retry ingestion for a document."""
    handlers = DatasetHandlers(service)
    return await handlers.retry_document_ingest(ctx, dataset_id, document_id, max_retries=max_retries)


@router.get("/{dataset_id}/runs", response_model=PaginatedResponse[RunResponse])
async def list_dataset_runs(
    dataset_id: str,
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """List runs scoped to a dataset."""
    handlers = DatasetHandlers(service)
    return await handlers.list_dataset_runs(
        ctx,
        dataset_id,
        mode=mode,
        kind=kind,
        status=status,
        started_after=started_after,
        started_before=started_before,
        page_token=page_token,
        page_size=page_size,
    )


@router.get("/{dataset_id}/runs/costs/summary", response_model=RunCostSummaryResponse)
async def summarize_dataset_run_costs(
    dataset_id: str,
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Summarize run costs scoped to a dataset."""
    handlers = DatasetHandlers(service)
    return await handlers.summarize_dataset_run_costs(
        ctx,
        dataset_id,
        mode=mode,
        kind=kind,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/{dataset_id}/runs/costs/by-mode", response_model=list[RunCostByModeResponse])
async def summarize_dataset_run_costs_by_mode(
    dataset_id: str,
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Summarize run costs by mode scoped to a dataset."""
    handlers = DatasetHandlers(service)
    return await handlers.summarize_dataset_run_costs_by_mode(
        ctx,
        dataset_id,
        mode=mode,
        kind=kind,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/{dataset_id}/runs/costs/by-provider", response_model=list[RunCostByProviderResponse])
async def summarize_dataset_run_costs_by_provider(
    dataset_id: str,
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Summarize run costs by provider scoped to a dataset."""
    handlers = DatasetHandlers(service)
    return await handlers.summarize_dataset_run_costs_by_provider(
        ctx,
        dataset_id,
        mode=mode,
        kind=kind,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/{dataset_id}/runs/costs/by-model", response_model=list[RunCostByModelResponse])
async def summarize_dataset_run_costs_by_model(
    dataset_id: str,
    mode: Optional[str] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Summarize run costs by model scoped to a dataset."""
    handlers = DatasetHandlers(service)
    return await handlers.summarize_dataset_run_costs_by_model(
        ctx,
        dataset_id,
        mode=mode,
        kind=kind,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/{dataset_id}/applications", response_model=list[DatasetApplicationUsageResponse])
async def list_dataset_app_usages(
    dataset_id: str,
    limit: int = 100,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """List app usages for a dataset."""
    handlers = DatasetHandlers(service)
    return await handlers.list_dataset_app_usages(ctx, dataset_id, limit=limit)


@router.post("/{dataset_id}/query", response_model=QueryResponse)
async def query_dataset(
    dataset_id: str,
    query_request: QueryRequest,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Query dataset for relevant documents.
    
    Args:
        dataset_id: Dataset ID.
        query_request: Query request data.
        ctx: Request context.
        service: DatasetService instance.
        
    Returns:
        Query results.
    """
    handlers = DatasetHandlers(service)
    return await handlers.query_dataset(ctx, dataset_id, query_request)


@router.post("/{dataset_id}/indexes/{index_id}/rebuild", response_model=IndexResponse)
async def rebuild_index(
    dataset_id: str,
    index_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: DatasetService = Depends(get_dataset_service),
):
    """Rebuild index.
    
    Args:
        dataset_id: Dataset ID.
        index_id: Index ID.
        ctx: Request context.
        service: DatasetService instance.
        
    Returns:
        Updated index.
    """
    handlers = DatasetHandlers(service)
    return await handlers.rebuild_index(ctx, dataset_id, index_id)
