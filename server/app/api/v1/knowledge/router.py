"""Knowledge API routes."""

from typing import Optional

import json
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app.api.v1.knowledge.dependencies import get_knowledge_service
from app.api.v1.knowledge.handlers import KnowledgeHandlers
from app.api.v1.permissions import require_workspace_read_ctx, require_workspace_write_ctx
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.kernel.trace.schemas import (
    RunCostByModeResponse,
    RunCostSummaryResponse,
    RunResponse,
)
from app.modules.knowledge.application.schemas import (
    KnowledgeUsageResponse,
    KnowledgeChunkResponse,
    KnowledgeChunkUpdate,
    KnowledgeCreateRequest,
    KnowledgeDocumentResponse,
    KnowledgeDocumentUpload,
    KnowledgeIndexCreate,
    KnowledgeIndexResponse,
    KnowledgeIndexUpdate,
    KnowledgeIngestTaskResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    KnowledgeResponse,
    KnowledgeUpdateRequest,
    KnowledgeWorkbenchItemsResponse,
    KnowledgeWorkbenchResponse,
)
from app.modules.knowledge.application.service import KnowledgeService


router = APIRouter()


@router.post("", response_model=KnowledgeResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    payload: KnowledgeCreateRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Create a knowledge base."""

    handlers = KnowledgeHandlers(service)
    return await handlers.create_knowledge(ctx, payload)


@router.get("", response_model=PaginatedResponse[KnowledgeResponse])
async def list_knowledge(
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """List knowledge bases."""

    handlers = KnowledgeHandlers(service)
    return await handlers.list_knowledge(ctx, page_token, page_size)


@router.get("/workbench", response_model=KnowledgeWorkbenchResponse)
async def get_knowledge_workbench(
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Get Knowledge workbench aggregate data."""

    handlers = KnowledgeHandlers(service)
    return await handlers.get_workbench(ctx, page_token, page_size)


@router.get("/workbench/items", response_model=KnowledgeWorkbenchItemsResponse)
async def list_knowledge_workbench_items(
    tab: Optional[str] = None,
    keyword: Optional[str] = None,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Get Knowledge workbench table rows."""

    handlers = KnowledgeHandlers(service)
    return await handlers.get_workbench_items(
        ctx,
        page_token=page_token,
        page_size=page_size,
        tab=tab,
        keyword=keyword,
    )


@router.get("/{knowledge_id}", response_model=KnowledgeResponse)
async def get_knowledge(
    knowledge_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Get knowledge base detail."""

    handlers = KnowledgeHandlers(service)
    return await handlers.get_knowledge(ctx, knowledge_id)


@router.put("/{knowledge_id}", response_model=KnowledgeResponse)
async def update_knowledge(
    knowledge_id: str,
    payload: KnowledgeUpdateRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Update a knowledge base."""

    handlers = KnowledgeHandlers(service)
    return await handlers.update_knowledge(ctx, knowledge_id, payload)


@router.delete("/{knowledge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge(
    knowledge_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Delete a knowledge base."""

    handlers = KnowledgeHandlers(service)
    await handlers.delete_knowledge(ctx, knowledge_id)


@router.get("/{knowledge_id}/documents", response_model=list[KnowledgeDocumentResponse])
async def list_knowledge_documents(
    knowledge_id: str,
    limit: int = 100,
    offset: int = 0,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """List knowledge base documents."""

    handlers = KnowledgeHandlers(service)
    return await handlers.list_documents(ctx, knowledge_id, limit=limit, offset=offset)


@router.get("/{knowledge_id}/runs", response_model=PaginatedResponse[RunResponse])
async def list_knowledge_runs(
    knowledge_id: str,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """List runs associated with a knowledge base."""

    handlers = KnowledgeHandlers(service)
    return await handlers.list_runs(ctx, knowledge_id, page_token=page_token, page_size=page_size)


@router.get("/{knowledge_id}/runs/costs/summary", response_model=RunCostSummaryResponse)
async def summarize_knowledge_costs(
    knowledge_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Summarize knowledge base runtime costs."""

    handlers = KnowledgeHandlers(service)
    return await handlers.summarize_costs(ctx, knowledge_id)


@router.get("/{knowledge_id}/runs/costs/by-mode", response_model=list[RunCostByModeResponse])
async def summarize_knowledge_costs_by_mode(
    knowledge_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Summarize knowledge base runtime costs by mode."""

    handlers = KnowledgeHandlers(service)
    return await handlers.summarize_costs_by_mode(ctx, knowledge_id)


@router.get("/{knowledge_id}/usages", response_model=list[KnowledgeUsageResponse])
async def list_knowledge_usages(
    knowledge_id: str,
    limit: int = 100,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """List agent/workflow usages of a knowledge base."""

    handlers = KnowledgeHandlers(service)
    return await handlers.list_usages(ctx, knowledge_id, limit=limit)


@router.post("/{knowledge_id}/indexes", response_model=KnowledgeIndexResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_index(
    knowledge_id: str,
    payload: KnowledgeIndexCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.create_index(ctx, knowledge_id, payload)


@router.get("/{knowledge_id}/indexes", response_model=list[KnowledgeIndexResponse])
async def list_knowledge_indexes(
    knowledge_id: str,
    limit: int = 20,
    offset: int = 0,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.list_indexes(ctx, knowledge_id, limit, offset)


@router.patch("/{knowledge_id}/indexes/{index_id}", response_model=KnowledgeIndexResponse)
async def update_knowledge_index(
    knowledge_id: str,
    index_id: str,
    payload: KnowledgeIndexUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.update_index(ctx, knowledge_id, index_id, payload)


@router.delete("/{knowledge_id}/indexes/{index_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_index(
    knowledge_id: str,
    index_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    await handlers.delete_index(ctx, knowledge_id, index_id)


@router.post("/{knowledge_id}/indexes/{index_id}/rebuild", response_model=KnowledgeIndexResponse)
async def rebuild_knowledge_index(
    knowledge_id: str,
    index_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.rebuild_index(ctx, knowledge_id, index_id)


@router.post("/{knowledge_id}/documents", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    knowledge_id: str,
    doc_key: str = Form(...),
    source_kind: str = Form(...),
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
    service: KnowledgeService = Depends(get_knowledge_service),
):
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

    payload = KnowledgeDocumentUpload(
        doc_key=doc_key,
        source_kind=source_kind,
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
    handlers = KnowledgeHandlers(service)
    return await handlers.upload_document(
        ctx,
        knowledge_id,
        payload,
        file,
        async_ingest=async_ingest,
        max_retries=max_retries,
    )


@router.get("/{knowledge_id}/documents/{document_id}", response_model=KnowledgeDocumentResponse)
async def get_knowledge_document(
    knowledge_id: str,
    document_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.get_document(ctx, document_id)


@router.get("/{knowledge_id}/documents/{document_id}/chunks", response_model=list[KnowledgeChunkResponse])
async def list_knowledge_chunks(
    knowledge_id: str,
    document_id: str,
    limit: int = 100,
    offset: int = 0,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.list_chunks(ctx, knowledge_id, document_id, limit, offset)


@router.patch("/{knowledge_id}/documents/{document_id}/chunks/{chunk_id}", response_model=KnowledgeChunkResponse)
async def update_knowledge_chunk(
    knowledge_id: str,
    document_id: str,
    chunk_id: str,
    payload: KnowledgeChunkUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.update_chunk(ctx, knowledge_id, document_id, chunk_id, payload)


@router.get("/{knowledge_id}/documents/{document_id}/content")
async def get_knowledge_document_content(
    knowledge_id: str,
    document_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    content, media_type = await service.get_document_content(knowledge_id, document_id)
    return Response(content=content, media_type=media_type)


@router.get("/{knowledge_id}/documents/{document_id}/download")
async def download_knowledge_document(
    knowledge_id: str,
    document_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    content, media_type, filename = await service.download_document(knowledge_id, document_id)
    headers = {"Content-Disposition": f'attachment; filename=\"{filename}\"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{knowledge_id}/documents/{doc_key}/versions", response_model=list[KnowledgeDocumentResponse])
async def list_knowledge_document_versions(
    knowledge_id: str,
    doc_key: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.list_document_versions(ctx, knowledge_id, doc_key)


@router.post("/{knowledge_id}/documents/{doc_key}/versions/{version}/rollback", response_model=KnowledgeDocumentResponse)
async def rollback_knowledge_document_version(
    knowledge_id: str,
    doc_key: str,
    version: int,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.rollback_document_version(ctx, knowledge_id, doc_key, version)


@router.delete("/{knowledge_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_document(
    knowledge_id: str,
    document_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    await handlers.delete_document(ctx, document_id)


@router.get("/{knowledge_id}/ingest-tasks", response_model=list[KnowledgeIngestTaskResponse])
async def list_knowledge_ingest_tasks(
    knowledge_id: str,
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.list_ingest_tasks(ctx, knowledge_id, status_filter, limit, offset)


@router.get("/{knowledge_id}/ingest-tasks/{task_id}", response_model=KnowledgeIngestTaskResponse)
async def get_knowledge_ingest_task(
    knowledge_id: str,
    task_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.get_ingest_task(ctx, knowledge_id, task_id)


@router.post("/{knowledge_id}/ingest-tasks/{task_id}/retry", response_model=KnowledgeIngestTaskResponse)
async def retry_knowledge_ingest_task(
    knowledge_id: str,
    task_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.retry_ingest_task(ctx, knowledge_id, task_id)


@router.post("/{knowledge_id}/ingest-tasks/{task_id}/cancel", response_model=KnowledgeIngestTaskResponse)
async def cancel_knowledge_ingest_task(
    knowledge_id: str,
    task_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.cancel_ingest_task(ctx, knowledge_id, task_id)


@router.post("/{knowledge_id}/documents/{document_id}/retry-ingest", response_model=KnowledgeIngestTaskResponse)
async def retry_knowledge_document_ingest(
    knowledge_id: str,
    document_id: str,
    max_retries: int = 1,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.retry_document_ingest(ctx, knowledge_id, document_id, max_retries)


@router.post("/{knowledge_id}/query", response_model=KnowledgeQueryResponse)
async def query_knowledge(
    knowledge_id: str,
    payload: KnowledgeQueryRequest,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    handlers = KnowledgeHandlers(service)
    return await handlers.query(ctx, knowledge_id, payload)
