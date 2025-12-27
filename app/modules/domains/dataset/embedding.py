""" embedding

Embedding service for generating vector embeddings.
"""

from typing import List, Optional, Dict, Any
from app.kernel.gateways.llm.interface import LLMGateway


class EmbeddingService:
    """Service for generating embeddings."""
    
    def __init__(self, llm_gateway: LLMGateway):
        """Initialize embedding service.
        
        Args:
            llm_gateway: LLM gateway instance.
        """
        self.llm_gateway = llm_gateway
    
    async def embed_texts(
        self,
        texts: List[str],
        model_ref: str,
        **kwargs,
    ) -> List[List[float]]:
        """Generate embeddings for texts.
        
        Args:
            texts: List of texts to embed.
            model_ref: Embedding model reference.
            **kwargs: Additional arguments for embedding.
            
        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []
        
        # Call LLM gateway embed API
        embedding_response = await self.llm_gateway.embed(
            texts=texts,
            model=model_ref,
            **kwargs,
        )
        
        return embedding_response.embeddings
    
    async def embed_text(
        self,
        text: str,
        model_ref: str,
        **kwargs,
    ) -> List[float]:
        """Generate embedding for a single text.
        
        Args:
            text: Text to embed.
            model_ref: Embedding model reference.
            **kwargs: Additional arguments for embedding.
            
        Returns:
            Embedding vector.
        """
        embeddings = await self.embed_texts([text], model_ref, **kwargs)
        return embeddings[0] if embeddings else []
    
    async def embed_batch(
        self,
        texts: List[str],
        model_ref: str,
        batch_size: int = 100,
        **kwargs,
    ) -> List[List[float]]:
        """Generate embeddings in batches.
        
        Args:
            texts: List of texts to embed.
            model_ref: Embedding model reference.
            batch_size: Batch size for processing.
            **kwargs: Additional arguments for embedding.
            
        Returns:
            List of embedding vectors.
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await self.embed_texts(batch, model_ref, **kwargs)
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings

