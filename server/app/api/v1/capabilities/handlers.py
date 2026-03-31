"""Handlers for capability registry APIs."""

from __future__ import annotations

from typing import Optional

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.modules.capability_registry.application.schemas import CapabilityResponse
from app.modules.capability_registry.application.service import CapabilityRegistryService


class CapabilityRegistryHandlers:
    """Thin handlers for runtime capability listing."""

    def __init__(self, service: CapabilityRegistryService) -> None:
        self.service = service

    async def list_capabilities(
        self,
        ctx: RequestContext,
        *,
        kind: Optional[str],
        source_kind: Optional[str],
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[CapabilityResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        items = await self.service.list_capabilities(kind=kind, source_kind=source_kind)
        window = items[offset : offset + limit]
        has_next = offset + len(window) < len(items)
        next_offset = offset + len(window) if has_next else None
        return PaginatedResponse.create(
            items=[CapabilityResponse.model_validate(item) for item in window],
            page_size=len(window),
            has_next=has_next,
            next_offset=next_offset,
        )
