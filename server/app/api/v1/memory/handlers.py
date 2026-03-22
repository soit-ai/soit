""" handlers

Memory handlers (thin orchestration).
"""

from typing import Optional

from app.kernel.contracts.context import RequestContext
from app.modules.memory.application.service import MemoryService
from app.modules.memory.application.schemas import MemoryCreate, MemoryQuery, MemoryResponse, MemorySearchResult
from app.infra.db.pagination import PaginatedResponse, parse_page_params


class MemoryHandlers:
    """Handlers for memory API endpoints."""

    def __init__(self, service: MemoryService):
        self.service = service

    async def create_memory(self, ctx: RequestContext, data: MemoryCreate) -> MemoryResponse:
        memory = await self.service.create_memory(data)
        return MemoryResponse.model_validate(memory)

    async def list_memories(
        self,
        ctx: RequestContext,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[MemoryResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        items = await self.service.list_memories(limit=limit, offset=offset)
        results = [MemoryResponse.model_validate(item) for item in items]
        has_next = len(items) == limit
        next_offset = offset + len(items) if has_next else None
        return PaginatedResponse.create(results, page_size=len(results), has_next=has_next, next_offset=next_offset)

    async def search_memory(self, ctx: RequestContext, data: MemoryQuery) -> list[MemorySearchResult]:
        return await self.service.query_memory(data)

    async def get_memory(self, ctx: RequestContext, memory_id: str) -> MemoryResponse:
        memory = await self.service.get_memory(memory_id)
        return MemoryResponse.model_validate(memory)

    async def delete_memory(self, ctx: RequestContext, memory_id: str) -> None:
        await self.service.delete_memory(memory_id)
