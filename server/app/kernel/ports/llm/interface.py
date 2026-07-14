""" interface

LLM port interface (chat/embed/rerank).
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolDefinition:
    """Tool definition for LLM function calling."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class ToolCall:
    """Tool call returned by LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


class ChatMessage:
    """Chat message for LLM."""

    def __init__(
        self,
        role: str,
        content: str | None,
        *,
        tool_call_id: str | None = None,
        tool_calls: list[ToolCall] | None = None,
        name: str | None = None,
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
        text: str | None,
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
        model: str | None = None,
        finish_reason: str | None = None,
        tool_calls: list[ToolCall] | None = None,
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
        model: str | None = None,
        finish_reason: str | None = None,
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
        embeddings: list[list[float]],
        tokens_used: int = 0,
        model: str | None = None,
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
        results: list[dict[str, Any]],
        tokens_used: int = 0,
        model: str | None = None,
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
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
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
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatStreamChunk]:
        """Stream chat completion."""
        raise NotImplementedError("stream_chat not implemented")

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
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
        documents: list[str],
        model: str,
        top_n: int | None = None,
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
