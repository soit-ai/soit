"""Public workflow application contracts for other product modules."""

from __future__ import annotations

from typing import Any, Protocol

from app.kernel.contracts.context import RequestContext


class PublishedWorkflowUsagePort(Protocol):
    """Read published workflow specifications without exposing workflow ORM models."""

    def list_published_specs(self) -> list[dict]: ...


class WorkflowKnowledgeQueryPort(Protocol):
    """Run one scoped knowledge query for a workflow retrieve node."""

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
        """Return the canonical retrieve-node result payload."""
        raise NotImplementedError
