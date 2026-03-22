""" interface

LLM port interface (chat/embed/rerank).
"""

from typing import List, Optional, Dict, Any, AsyncIterator
from abc import ABC, abstractmethod


class ChatMessage:
    """Chat message for LLM."""
    
    def __init__(self, role: str, content: str):
        """Initialize chat message.
        
        Args:
            role: Message role (system, user, assistant).
            content: Message content.
        """
        self.role = role
        self.content = content


class ChatResponse:
    """Chat response from LLM."""
    
    def __init__(
        self,
        text: str,
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
        model: Optional[str] = None,
        finish_reason: Optional[str] = None,
    ):
        """Initialize chat response.
        
        Args:
            text: Generated text.
            tokens_prompt: Prompt tokens used.
            tokens_completion: Completion tokens used.
            model: Model used.
            finish_reason: Finish reason (stop, length, etc.).
        """
        self.text = text
        self.tokens_prompt = tokens_prompt
        self.tokens_completion = tokens_completion
        self.model = model
        self.finish_reason = finish_reason


class ChatStreamChunk:
    """Streaming chat chunk."""

    def __init__(
        self,
        delta: str = "",
        done: bool = False,
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
        model: Optional[str] = None,
        finish_reason: Optional[str] = None,
    ):
        """Initialize stream chunk."""
        self.delta = delta
        self.done = done
        self.tokens_prompt = tokens_prompt
        self.tokens_completion = tokens_completion
        self.model = model
        self.finish_reason = finish_reason


class EmbeddingResponse:
    """Embedding response from LLM."""
    
    def __init__(
        self,
        embeddings: List[List[float]],
        tokens_used: int = 0,
        model: Optional[str] = None,
    ):
        """Initialize embedding response.
        
        Args:
            embeddings: List of embedding vectors.
            tokens_used: Tokens used.
            model: Model used.
        """
        self.embeddings = embeddings
        self.tokens_used = tokens_used
        self.model = model


class RerankResponse:
    """Rerank response from LLM."""
    
    def __init__(
        self,
        results: List[Dict[str, Any]],
        tokens_used: int = 0,
        model: Optional[str] = None,
    ):
        """Initialize rerank response.
        
        Args:
            results: List of reranked results with scores.
            tokens_used: Tokens used.
            model: Model used.
        """
        self.results = results
        self.tokens_used = tokens_used
        self.model = model


class LLMPort(ABC):
    """LLM port interface."""
    
    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Chat completion.
        
        Args:
            messages: List of chat messages.
            model: Model reference (e.g., "model:openai:gpt-4").
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional model-specific parameters.
            
        Returns:
            ChatResponse instance.
        """
        pass

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatStreamChunk]:
        """Stream chat completion."""
        raise NotImplementedError("stream_chat not implemented")
    
    @abstractmethod
    async def embed(
        self,
        texts: List[str],
        model: str,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate embeddings.
        
        Args:
            texts: List of texts to embed.
            model: Model reference (e.g., "model:openai:text-embedding-ada-002").
            **kwargs: Additional model-specific parameters.
            
        Returns:
            EmbeddingResponse instance.
        """
        pass
    
    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: List[str],
        model: str,
        top_n: Optional[int] = None,
        **kwargs: Any,
    ) -> RerankResponse:
        """Rerank documents.
        
        Args:
            query: Query text.
            documents: List of document texts.
            model: Model reference.
            top_n: Number of top results to return.
            **kwargs: Additional model-specific parameters.
            
        Returns:
            RerankResponse instance.
        """
        pass
