""" interface

LLM port interface (chat/embed/rerank).
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, AsyncIterator
from abc import ABC, abstractmethod


@dataclass
class ToolDefinition:
    """Tool definition for LLM function calling."""

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema


@dataclass
class ToolCall:
    """Tool call returned by LLM."""

    id: str
    name: str
    arguments: Dict[str, Any]


class ChatMessage:
    """Chat message for LLM."""

    def __init__(
        self,
        role: str,
        content: Optional[str],
        *,
        tool_call_id: Optional[str] = None,
        tool_calls: Optional[List[ToolCall]] = None,
        name: Optional[str] = None,
    ):
        """Initialize chat message.

        Args:
            role: Message role (system, user, assistant, tool).
            content: Message content.
            tool_call_id: ID of the tool call this message answers (role=tool).
            tool_calls: Tool calls made by assistant (role=assistant).
            name: Tool name for tool result messages.
        """
        self.role = role
        self.content = content
        self.tool_call_id = tool_call_id
        self.tool_calls = tool_calls
        self.name = name


class ChatResponse:
    """Chat response from LLM."""

    def __init__(
        self,
        text: Optional[str],
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
        model: Optional[str] = None,
        finish_reason: Optional[str] = None,
        tool_calls: Optional[List[ToolCall]] = None,
    ):
        """Initialize chat response.

        Args:
            text: Generated text (may be None when tool_calls present).
            tokens_prompt: Prompt tokens used.
            tokens_completion: Completion tokens used.
            model: Model used.
            finish_reason: Finish reason (stop, length, tool_calls, etc.).
            tool_calls: Tool calls returned by the LLM.
        """
        self.text = text
        self.tokens_prompt = tokens_prompt
        self.tokens_completion = tokens_completion
        self.model = model
        self.finish_reason = finish_reason
        self.tool_calls = tool_calls


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
        *,
        tools: Optional[List[ToolDefinition]] = None,
        tool_choice: Optional[str] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Chat completion.

        Args:
            messages: List of chat messages.
            model: Model reference (e.g., "model:openai:gpt-4").
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            tools: Optional list of tool definitions for function calling.
            tool_choice: Tool selection strategy ("auto", "required", "none").
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
