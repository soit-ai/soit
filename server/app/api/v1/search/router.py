"""Workspace global search routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.v1.permissions import require_workspace_read_ctx
from app.api.v1.search.dependencies import get_global_search_service
from app.kernel.contracts.context import RequestContext
from app.modules.search.application.schemas import GlobalSearchResponse, SearchKind
from app.modules.search.application.service import GlobalSearchService

router = APIRouter()


@router.get("", response_model=GlobalSearchResponse)
async def global_search(
    q: Annotated[str, Query(min_length=2, max_length=100)],
    types: Annotated[list[SearchKind] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
    _ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: GlobalSearchService = Depends(get_global_search_service),
) -> GlobalSearchResponse:
    return service.search(query_text=q, kinds=types, limit=limit)
