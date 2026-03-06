""" router

Memory API routes (FastAPI).
"""

from typing import Optional
from fastapi import APIRouter, Depends, Body, status

from app.kernel.contracts.context import RequestContext
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.modules.memory.application.service import MemoryService
from app.modules.memory.application.schemas import MemoryCreate, MemoryQuery, MemoryResponse, MemorySearchResult
from app.infra.db.pagination import PaginatedResponse
from app.api.v1.memory.dependencies import get_memory_service
from app.api.v1.memory.handlers import MemoryHandlers


router = APIRouter()


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    data: MemoryCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: MemoryService = Depends(get_memory_service),
):
    handlers = MemoryHandlers(service)
    return await handlers.create_memory(ctx, data)


@router.get("", response_model=PaginatedResponse[MemoryResponse])
async def list_memories(
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: MemoryService = Depends(get_memory_service),
):
    handlers = MemoryHandlers(service)
    return await handlers.list_memories(ctx, page_token=page_token, page_size=page_size)


@router.post("/search", response_model=list[MemorySearchResult])
async def search_memory(
    data: MemoryQuery = Body(...),
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: MemoryService = Depends(get_memory_service),
):
    handlers = MemoryHandlers(service)
    return await handlers.search_memory(ctx, data)


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: MemoryService = Depends(get_memory_service),
):
    handlers = MemoryHandlers(service)
    return await handlers.get_memory(ctx, memory_id)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: MemoryService = Depends(get_memory_service),
):
    handlers = MemoryHandlers(service)
    await handlers.delete_memory(ctx, memory_id)
