""" router

Dataset API routes (FastAPI).
"""

from typing import Optional
from fastapi import APIRouter, Depends, status, Body, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.db.session import get_db
from app.middleware.auth import get_current_context
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
from app.modules.entrypoints.dataset.dependencies import get_dataset_service
from app.modules.entrypoints.dataset.handlers import DatasetHandlers


router = APIRouter()


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    dataset_in: DatasetCreate,
    ctx: RequestContext = Depends(get_current_context),
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


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(get_current_context),
    service: DatasetService = Depends(get_dataset_service),
):
    """List datasets.
    
    Args:
        page_token: Optional page token.
        page_size: Page size.
        ctx: Request context.
        service: DatasetService instance.
        
    Returns:
        List of datasets.
    """
    # TODO: Implement pagination
    return []


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    ctx: RequestContext = Depends(get_current_context),
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
    ctx: RequestContext = Depends(get_current_context),
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
    ctx: RequestContext = Depends(get_current_context),
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


@router.post("/{dataset_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    dataset_id: str,
    doc_key: str = Form(...),
    source_type: str = Form(...),
    file: Optional[UploadFile] = File(None),
    ctx: RequestContext = Depends(get_current_context),
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
    document_in = DocumentUpload(
        doc_key=doc_key,
        source_type=source_type,
    )
    handlers = DatasetHandlers(service)
    return await handlers.upload_document(ctx, dataset_id, document_in, file)


@router.get("/{dataset_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    dataset_id: str,
    is_latest_only: bool = True,
    limit: int = 20,
    offset: int = 0,
    ctx: RequestContext = Depends(get_current_context),
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


@router.get("/{dataset_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    dataset_id: str,
    document_id: str,
    ctx: RequestContext = Depends(get_current_context),
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


@router.delete("/{dataset_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    dataset_id: str,
    document_id: str,
    ctx: RequestContext = Depends(get_current_context),
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


@router.post("/{dataset_id}/query", response_model=QueryResponse)
async def query_dataset(
    dataset_id: str,
    query_request: QueryRequest,
    ctx: RequestContext = Depends(get_current_context),
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
    ctx: RequestContext = Depends(get_current_context),
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

