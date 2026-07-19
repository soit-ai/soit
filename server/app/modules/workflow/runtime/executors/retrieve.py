""" retrieve

Retrieve node executor.
"""

from typing import Any

from app.kernel.commons.errors import ValidationError
from app.modules.workflow.runtime.executors.base import ExecutionContext, NodeExecutor


class RetrieveNodeExecutor(NodeExecutor):
    """Executor for retrieve nodes."""

    async def execute(
        self,
        node: dict[str, Any],
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute retrieve node.

        Args:
            node: Node definition.
            context: Execution context.
            inputs: Resolved inputs.

        Returns:
            Output dictionary with 'context' (list of documents) and 'citations'.
        """
        if not context.workflow_knowledge_query_port:
            raise ValidationError("Workflow knowledge query port not available")

        knowledge_ref = inputs.get("knowledge_ref")
        if not isinstance(knowledge_ref, str) or not knowledge_ref.strip():
            raise ValidationError("Retrieve node requires 'knowledge_ref' input")

        query = inputs.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValidationError("Retrieve node requires 'query' input")

        top_k = inputs.get("top_k", 10)
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 100:
            raise ValidationError("Retrieve node requires 'top_k' between 1 and 100")
        filters = inputs.get("filters")
        if filters is not None and not isinstance(filters, dict):
            raise ValidationError("Retrieve node 'filters' must be an object")
        rerank_model = inputs.get("rerank_model")
        if rerank_model is not None and (
            not isinstance(rerank_model, str) or not rerank_model.strip()
        ):
            raise ValidationError("Retrieve node 'rerank_model' must be a non-empty string")

        return await context.workflow_knowledge_query_port.query(
            knowledge_ref=knowledge_ref,
            query=query,
            top_k=top_k,
            filters=filters,
            rerank_model=rerank_model,
            ctx=context.ctx,
            run_id=context.run_id,
        )
