"""Scoped cross-module resource adapters for workflow execution."""

from __future__ import annotations

from typing import Any

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.modules.knowledge.application.runtime_schemas import QueryRequest
from app.modules.knowledge.application.runtime_service import KnowledgeRuntimeService


class KnowledgeRuntimeWorkflowQueryAdapter:
    """Expose scoped knowledge runtime queries to workflow retrieve nodes."""

    def __init__(
        self,
        *,
        runtime_service: KnowledgeRuntimeService,
        ctx: RequestContext,
    ) -> None:
        self._runtime_service = runtime_service
        self._ctx = ctx

    async def query(
        self,
        *,
        knowledge_ref: str,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None,
        rerank_model: str | None,
        ctx: RequestContext,
        run_id: str,
    ) -> dict[str, Any]:
        """Resolve a knowledge ref and return the retrieve-node result shape."""
        del run_id
        if (
            ctx.tenant_id != self._ctx.tenant_id
            or ctx.workspace_id != self._ctx.workspace_id
            or ctx.user_id != self._ctx.user_id
            or ctx.tenant_role != self._ctx.tenant_role
            or ctx.workspace_role != self._ctx.workspace_role
        ):
            raise ValidationError("Workflow knowledge query scope mismatch")

        prefix, separator, knowledge_id = knowledge_ref.partition(":")
        if prefix != "knowledge" or not separator or not knowledge_id:
            raise ValidationError("Workflow knowledge_ref must use the knowledge: prefix")

        response = await self._runtime_service.query(
            knowledge_id,
            QueryRequest(
                query=query,
                top_k=top_k,
                filter=filters,
                use_rerank=rerank_model is not None,
                reranker_ref=rerank_model,
            ),
        )
        payload = response.model_dump()
        documents = list(payload.get("results") or [])
        context_text = "\n\n".join(
            str(document.get("text") or "")
            for document in documents
            if isinstance(document, dict) and document.get("text")
        )
        return {
            "context": context_text,
            "documents": documents,
            "citations": list(payload.get("citations") or []),
            "count": int(payload.get("total", len(documents))),
        }
