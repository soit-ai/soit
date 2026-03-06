"""tools

Dataset module tool entrypoints.
"""

from typing import Dict, Any, Optional

from app.infra.db.session import get_db_sync
from app.kernel.contracts.context import RequestContext
from app.modules.dataset.application.schemas import QueryRequest
from app.wiring.services import build_dataset_service


def _resolve_request_context(
    *,
    ctx: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> RequestContext:
    """Resolve RequestContext from explicit fields or ctx dict."""
    if ctx:
        tenant_id = ctx.get("tenant_id") or tenant_id
        workspace_id = ctx.get("workspace_id") or workspace_id
        user_id = ctx.get("user_id") or user_id
    if not tenant_id or not workspace_id or not user_id:
        raise ValueError("dataset_query requires tenant_id/workspace_id/user_id")
    return RequestContext(tenant_id=tenant_id, workspace_id=workspace_id, user_id=user_id)


async def dataset_query(
    dataset_id: str,
    query: str,
    top_k: int = 5,
    index_id: Optional[str] = None,
    filter: Optional[Dict[str, Any]] = None,
    include_snippets: bool = True,
    strategy: Optional[str] = None,
    ctx: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Query dataset for retrieval results (agent tool)."""
    request_context = _resolve_request_context(
        ctx=ctx,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    db = get_db_sync()
    try:
        service = build_dataset_service(db=db, ctx=request_context)
        query_request = QueryRequest(
            query=query,
            top_k=top_k,
            index_id=index_id,
            filter=filter,
            include_snippets=include_snippets,
            strategy=strategy,
        )
        response = await service.query(dataset_id, query_request)
        return response.model_dump()
    finally:
        db.close()
