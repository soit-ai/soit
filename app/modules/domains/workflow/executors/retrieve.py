""" retrieve

Retrieve node executor.
"""

from typing import Dict, Any, List, Optional
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
        
        if not context.llm_gateway:
            raise ValidationError("LLM gateway not available for embedding")
        
        # Extract parameters
        query = inputs.get("query")
        if not query:
            raise ValidationError("Retrieve node requires 'query' input")
        
        collection = inputs.get("collection") or inputs.get("dataset")
        if not collection:
            raise ValidationError("Retrieve node requires 'collection' or 'dataset' input")
        
        top_k = inputs.get("top_k", 10)
        embedding_model = inputs.get("embedding_model") or inputs.get("model")
        
        # Generate embedding for query
        if isinstance(query, str):
            # Query is text, need to embed it
            if not embedding_model:
                raise ValidationError("Retrieve node requires 'embedding_model' input for text queries")
            
            # Generate embedding using LLM gateway
            embedding_response = await context.llm_gateway.embed(
                texts=[query],
                model=embedding_model,
            )
            
            if not embedding_response.embeddings or len(embedding_response.embeddings) == 0:
                raise ValidationError("Failed to generate query embedding")
            
            query_vector = embedding_response.embeddings[0]
        elif isinstance(query, list) and all(isinstance(x, (int, float)) for x in query):
            # Query is already a vector
            query_vector = query
        else:
            raise ValidationError("Query must be a string or a vector list")
        
        # Call vector gateway
        result = await context.vector_gateway.query(
            collection=collection,
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
        )
        
        # Format output
        documents = []
        citations = []
        
        for i, doc_id in enumerate(result.ids):
            doc_metadata = result.metadata[i] if result.metadata and i < len(result.metadata) else {}
            score = result.scores[i] if result.scores and i < len(result.scores) else 0.0
            
            documents.append({
                "id": doc_id,
                "score": score,
                "metadata": doc_metadata,
                "text": doc_metadata.get("text", "") or doc_metadata.get("text_preview", ""),
            })
            citations.append({
                "id": doc_id,
                "rank": i + 1,
                "score": score,
            })
        
        # Build context text from documents
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

