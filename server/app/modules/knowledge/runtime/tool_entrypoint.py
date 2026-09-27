"""Runtime composition entrypoint for the builtin knowledge query tool."""

from __future__ import annotations

from typing import Any

from app.infra.db.session import get_async_session_local
from app.kernel.contracts.context import RequestContext
from app.modules.knowledge.application.runtime_schemas import QueryRequest
from app.wiring.services import build_knowledge_runtime_service


async def knowledge_query(
    knowledge_id: str,
    query: str,
    top_k: int = 5,
    index_id: str | None = None,
    filter: dict[str, Any] | None = None,
    include_snippets: bool = True,
    strategy: str | None = None,
    *,
    ctx: RequestContext,
    parent_run_id: str | None = None,
) -> dict[str, Any]:
    """Build a scoped runtime service and return knowledge retrieval results.

    ``ctx`` is the caller's own request context, handed over whole by the
    tool router or the agent: its roles, scopes, API key and content capture
    govern the retrieval. Nothing in the tool's arguments can name a tenant,
    a workspace, a user or a role. ``parent_run_id`` is the run the
    retrieval serves, also set by the router or the agent, never by arguments.
    """
    if not isinstance(ctx, RequestContext):
        raise TypeError("knowledge_query runs under the caller's RequestContext")
    db = get_async_session_local()()
    try:
        service = build_knowledge_runtime_service(db=db, ctx=ctx)
        request = QueryRequest(
            query=query,
            top_k=top_k,
            index_id=index_id,
            filter=filter,
            include_snippets=include_snippets,
            strategy=strategy,
        )
        response = await service.query(knowledge_id, request, parent_run_id=parent_run_id)
        return response.model_dump()
    finally:
        await db.close()
