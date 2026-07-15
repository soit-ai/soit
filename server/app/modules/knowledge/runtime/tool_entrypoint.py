"""Runtime composition entrypoint for the builtin knowledge query tool."""

from __future__ import annotations

from typing import Any

from app.infra.db.session import get_db_sync
from app.kernel.contracts.context import RequestContext
from app.modules.knowledge.application.runtime_schemas import QueryRequest
from app.wiring.services import build_knowledge_runtime_service


def _resolve_request_context(
    *,
    ctx: dict[str, Any] | None = None,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    user_id: str | None = None,
    tenant_role: str | None = None,
    workspace_role: str | None = None,
) -> RequestContext:
    if ctx:
        tenant_id = ctx.get("tenant_id") or tenant_id
        workspace_id = ctx.get("workspace_id") or workspace_id
        user_id = ctx.get("user_id") or user_id
        tenant_role = ctx.get("tenant_role") or tenant_role
        workspace_role = ctx.get("workspace_role") or workspace_role
    if not tenant_id or not workspace_id or not user_id:
        raise ValueError("knowledge_query requires tenant_id/workspace_id/user_id")
    return RequestContext(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
        tenant_role=tenant_role,
        workspace_role=workspace_role,
    )


async def knowledge_query(
    knowledge_id: str,
    query: str,
    top_k: int = 5,
    index_id: str | None = None,
    filter: dict[str, Any] | None = None,
    include_snippets: bool = True,
    strategy: str | None = None,
    ctx: dict[str, Any] | None = None,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    user_id: str | None = None,
    tenant_role: str | None = None,
    workspace_role: str | None = None,
) -> dict[str, Any]:
    """Build a scoped runtime service and return knowledge retrieval results."""
    request_context = _resolve_request_context(
        ctx=ctx,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
        tenant_role=tenant_role,
        workspace_role=workspace_role,
    )
    db = get_db_sync()
    try:
        service = build_knowledge_runtime_service(db=db, ctx=request_context)
        request = QueryRequest(
            query=query,
            top_k=top_k,
            index_id=index_id,
            filter=filter,
            include_snippets=include_snippets,
            strategy=strategy,
        )
        response = await service.query(knowledge_id, request)
        return response.model_dump()
    finally:
        db.close()
