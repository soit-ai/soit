""" openai_llm

OpenAI LLM gateway adapter implementation.
"""

from typing import List, Optional
import openai
from openai import AsyncOpenAI

from app.kernel.gateways.llm.interface import (
    LLMGateway,
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    RerankResponse,
)
from app.kernel.config.settings import settings


class OpenAIGateway(LLMGateway):
    """OpenAI LLM gateway adapter."""
    
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
        """Rerank documents via OpenAI (if supported)."""
        # OpenAI doesn't have native rerank, use embeddings + cosine similarity
        # For now, return placeholder
        # In production, implement proper reranking
        raise NotImplementedError("Rerank not implemented for OpenAI")
