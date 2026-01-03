""" openai_llm

OpenAI LLM port adapter implementation.
"""

from typing import List, Optional, Dict, Any
import numpy as np
import openai
from openai import AsyncOpenAI

from app.kernel.ports.llm.interface import (
    LLMPort,
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    RerankResponse,
)
from app.settings.settings import settings


class OpenAILLMPort(LLMPort):
    """OpenAI LLM port adapter."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize OpenAI gateway.
        
        Args:
            api_key: OpenAI API key (if None, uses settings or env var).
        """
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> ChatResponse:
        """Chat completion via OpenAI."""
        # Parse model reference (e.g., "model:openai:gpt-4")
        model_name = model.split(":")[-1] if ":" in model else model
        
        # Convert messages
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Call OpenAI API
        response = await self.client.chat.completions.create(
            model=model_name,
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        choice = response.choices[0]
        return ChatResponse(
            text=choice.message.content or "",
            tokens_prompt=response.usage.prompt_tokens if response.usage else 0,
            tokens_completion=response.usage.completion_tokens if response.usage else 0,
            model=model_name,
            finish_reason=choice.finish_reason,
        )
    
    async def embed(
        self,
        texts: List[str],
        model: str,
        **kwargs,
    ) -> EmbeddingResponse:
        """Generate embeddings via OpenAI."""
        # Parse model reference
        model_name = model.split(":")[-1] if ":" in model else model
        
        # Call OpenAI API
        response = await self.client.embeddings.create(
            model=model_name,
            input=texts,
        )
        
        embeddings = [item.embedding for item in response.data]
        tokens_used = response.usage.total_tokens if response.usage else 0
        
        return EmbeddingResponse(
            embeddings=embeddings,
            tokens_used=tokens_used,
            model=model_name,
        )
    
    async def rerank(
        self,
        query: str,
        documents: List[str],
        model: str,
        top_n: Optional[int] = None,
        **kwargs,
    ) -> RerankResponse:
        """Rerank documents via OpenAI using embeddings + cosine similarity.
        
        Args:
            query: Query text.
            documents: List of document texts to rerank.
            model: Model reference (embedding model).
            top_n: Number of top results to return.
            **kwargs: Additional parameters.
            
        Returns:
            RerankResponse with reranked results.
        """
        if not documents:
            return RerankResponse(
                results=[],
                tokens_used=0,
                model=model,
            )
        
        # Parse model reference
        model_name = model.split(":")[-1] if ":" in model else model
        
        # Use embedding model (default to text-embedding-ada-002 if not specified)
        embedding_model = kwargs.get("embedding_model", "text-embedding-ada-002")
        if ":" in embedding_model:
            embedding_model = embedding_model.split(":")[-1]
        
        # Generate embeddings for query and documents
        all_texts = [query] + documents
        response = await self.client.embeddings.create(
            model=embedding_model,
            input=all_texts,
        )
        
        embeddings = [item.embedding for item in response.data]
        tokens_used = response.usage.total_tokens if response.usage else 0
        
        # Extract query embedding and document embeddings
        query_embedding = np.array(embeddings[0])
        doc_embeddings = np.array(embeddings[1:])
        
        # Calculate cosine similarity
        # Cosine similarity = dot product / (norm(query) * norm(doc))
        query_norm = np.linalg.norm(query_embedding)
        doc_norms = np.linalg.norm(doc_embeddings, axis=1)
        
        # Avoid division by zero
        query_norm = max(query_norm, 1e-8)
        doc_norms = np.maximum(doc_norms, 1e-8)
        
        # Calculate cosine similarities
        similarities = np.dot(doc_embeddings, query_embedding) / (query_norm * doc_norms)
        
        # Create results with scores
        results = []
        for i, (doc, score) in enumerate(zip(documents, similarities)):
            results.append({
                "index": i,
                "document": doc,
                "score": float(score),
            })
        
        # Sort by score (descending)
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Apply top_n if specified
        if top_n is not None and top_n > 0:
            results = results[:top_n]
        
        return RerankResponse(
            results=results,
            tokens_used=tokens_used,
            model=model_name,
        )
