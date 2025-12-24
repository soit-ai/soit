""" retrieve

Retrieve node executor.
"""

from typing import Dict, Any, List
from app.modules.domains.workflow.executors.base import NodeExecutor, ExecutionContext
from app.kernel.commons.errors import ValidationError


class RetrieveNodeExecutor(NodeExecutor):
    """Executor for retrieve nodes."""
    
    async def execute(
        self,
        node: Dict[str, Any],
        context: ExecutionContext,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute retrieve node.
        
        Args:
            node: Node definition.
            context: Execution context.
            inputs: Resolved inputs.
            
        Returns:
            Output dictionary with 'context' (list of documents) and 'citations'.
        """
        if not context.vector_gateway:
            raise ValidationError("Vector gateway not available")
        
        # Extract parameters
        query = inputs.get("query")
        if not query:
            raise ValidationError("Retrieve node requires 'query' input")
        
        collection = inputs.get("collection") or inputs.get("dataset")
        if not collection:
            raise ValidationError("Retrieve node requires 'collection' or 'dataset' input")
        
        top_k = inputs.get("top_k", 10)
        
        # Get embedding for query (if needed)
        # For now, assume query is already embedded or we need to embed it
        # In production, integrate with embedding gateway
        
        # Call vector gateway
        # Note: This is a placeholder - actual implementation needs embedding
        # For now, return empty results
        result = await context.vector_gateway.query(
            collection=collection,
            vector=[],  # Placeholder - should be query embedding
            top_k=top_k,
            run_id=context.run_id,
        )
        
        # Format output
        documents = []
        citations = []
        
        for i, doc_id in enumerate(result.ids):
            documents.append({
                "id": doc_id,
                "score": result.scores[i] if result.scores else 0.0,
                "metadata": result.metadata[i] if result.metadata else {},
            })
            citations.append({
                "id": doc_id,
                "rank": i + 1,
            })
        
        context_text = "\n\n".join([
            doc.get("text", "") or str(doc.get("metadata", {}))
            for doc in documents
        ])
        
        return {
            "context": context_text,
            "documents": documents,
            "citations": citations,
            "count": len(documents),
        }

