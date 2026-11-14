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
    policy: dict[str, Any] | None = None


@dataclass
class ToolCall:
    """Tool call returned by LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolCallDelta:
    """One streaming fragment of an LLM tool call."""

    index: int
    id: str | None = None
    name: str | None = None
    arguments_delta: str = ""


@dataclass(frozen=True)
class HostedToolCall:
    """Provider-executed hosted tool call returned by an LLM gateway."""

    id: str
    name: str
    status: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass(frozen=True)
class HostedArtifact:
    """Generated provider file that must be copied into governed storage."""

    container_id: str
    file_id: str
    filename: str
    content: bytes
    mime: str | None = None


@dataclass(frozen=True)
class LLMRuntimeTarget:
    """Resolved SOIT identity for one model invocation."""

    provider_id: str | None
    provider_slug: str
    provider_kind: str
    adapter_backend: str
    model_ref: str
    model_id: str
    provider_model_id: str | None = None


@dataclass(frozen=True)
class ChatImage:
    """An image a message shows the model, by URL or `data:` URL."""

    url: str
    detail: str | None = None
    """Resolution hint (`low`, `high`, `auto`) for providers that take one."""

    @property
    def is_data_url(self) -> bool:
        return self.url.startswith("data:")


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
        images: list[ChatImage] | None = None,
    ):
        """Initialize chat message.

        Args:
            role: Message role (system, user, assistant, tool).
            content: Message text. Content safety, truncation and the thread
                ledger read this; images travel beside it.
            tool_call_id: ID of the tool call this message answers (role=tool).
            tool_calls: Tool calls made by assistant (role=assistant).
            name: Tool name for tool result messages.
            images: Images shown with the text, for vision-capable models.
                Adapters that cannot send images ignore them.
        """
        self.role = role
        self.content = content
        self.tool_call_id = tool_call_id
        self.tool_calls = tool_calls
        self.name = name
        self.images = images or []


class ChatResponse:
    """Chat response from LLM."""

    def __init__(
        self,
        text: str | None,
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
        model: str | None = None,
        finish_reason: str | None = None,
        runtime_target: LLMRuntimeTarget | None = None,
        tool_calls: list[ToolCall] | None = None,
        reasoning: str | None = None,
        hosted_tool_calls: list[HostedToolCall] | None = None,
        citations: list[dict[str, Any]] | None = None,
        hosted_artifacts: list[HostedArtifact] | None = None,
        upstream_id: str | None = None,
        upstream_request_id: str | None = None,
    ):
        """Initialize chat response.

        Args:
            text: Generated text (may be None when tool_calls present).
            reasoning: Provider-visible reasoning text, when explicitly returned.
            tokens_prompt: Prompt tokens used.
            tokens_completion: Completion tokens used.
            model: Model used.
            finish_reason: Finish reason (stop, length, tool_calls, etc.).
            tool_calls: Tool calls returned by the LLM.
            upstream_id: The provider's own id for the response (``chatcmpl-…``,
                ``msg_…``), when it gave one. Never an id an SDK made up.
            upstream_request_id: The provider's request id from its response
                headers (``x-request-id``, ``request-id``), when it sent one.
        """
        self.text = text
        self.reasoning = reasoning
        self.tokens_prompt = tokens_prompt
        self.tokens_completion = tokens_completion
        self.model = model
        self.finish_reason = finish_reason
        self.runtime_target = runtime_target
        self.tool_calls = tool_calls
        self.hosted_tool_calls = hosted_tool_calls or []
        self.citations = citations or []
        self.hosted_artifacts = hosted_artifacts or []
        self.upstream_id = upstream_id
        self.upstream_request_id = upstream_request_id


class ChatStreamChunk:
    """Streaming chat chunk."""

    def __init__(
        self,
        delta: str = "",
        done: bool = False,
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
        model: str | None = None,
        runtime_target: LLMRuntimeTarget | None = None,
        finish_reason: str | None = None,
        tool_call_deltas: list[ToolCallDelta] | None = None,
        tool_calls: list[ToolCall] | None = None,
        reasoning_delta: str = "",
        hosted_tool_calls: list[HostedToolCall] | None = None,
        citations: list[dict[str, Any]] | None = None,
        hosted_artifacts: list[HostedArtifact] | None = None,
        upstream_id: str | None = None,
        upstream_request_id: str | None = None,
    ):
        """Initialize stream chunk.

        ``upstream_id`` and ``upstream_request_id`` are as on ``ChatResponse``;
        a stream carries them on any chunk, at least once.
        """
        self.delta = delta
        self.reasoning_delta = reasoning_delta
        self.done = done
        self.tokens_prompt = tokens_prompt
        self.tokens_completion = tokens_completion
        self.model = model
        self.runtime_target = runtime_target
        self.finish_reason = finish_reason
        self.tool_call_deltas = tool_call_deltas
        self.tool_calls = tool_calls
        self.hosted_tool_calls = hosted_tool_calls or []
        self.citations = citations or []
        self.hosted_artifacts = hosted_artifacts or []
        self.upstream_id = upstream_id
        self.upstream_request_id = upstream_request_id


class EmbeddingResponse:
    """Embedding response from LLM."""

    def __init__(
        self,
        embeddings: list[list[float]],
        tokens_used: int = 0,
        model: str | None = None,
        runtime_target: LLMRuntimeTarget | None = None,
        upstream_id: str | None = None,
        upstream_request_id: str | None = None,
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
        self.runtime_target = runtime_target
        self.upstream_id = upstream_id
        self.upstream_request_id = upstream_request_id


class GeneratedImage:
    """One generated image, either inline base64 bytes or a provider URL."""

    def __init__(self, b64_json: str | None = None, url: str | None = None):
        """Initialize generated image.

        Args:
            b64_json: Base64-encoded image bytes (preferred; self-contained).
            url: Provider-hosted URL (short-lived on most providers; callers
                that need durable storage must download and re-store it).
        """
        self.b64_json = b64_json
        self.url = url


class ImageGenerationResponse:
    """Image generation response from LLM."""

    def __init__(
        self,
        images: list[GeneratedImage],
        model: str | None = None,
        runtime_target: LLMRuntimeTarget | None = None,
        upstream_id: str | None = None,
        upstream_request_id: str | None = None,
    ):
        """Initialize image generation response.

        Args:
            images: Generated images.
            model: Model used.
        """
        self.images = images
        self.model = model
        self.runtime_target = runtime_target
        self.upstream_id = upstream_id
        self.upstream_request_id = upstream_request_id


@dataclass
class TextStyle:
    """How a run of recognized text looks, as closely as the provider can tell."""

    font_family: str | None = None
    """The closest known font family, not necessarily the one used."""
    color: str | None = None
    """``#RRGGBB``."""
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strikethrough: bool | None = None
    shadow: bool | None = None
    translucent: bool | None = None


@dataclass
class TextRun:
    text: str
    style: TextStyle


class ProviderCallError(Exception):
    """The provider failed a call, or could not be reached, and SOIT wrote the call itself.

    An adapter that speaks a provider's own request (no SDK in between) raises
    this for a failure asking again may cure: a rate limit, a server error, a
    lost connection. ``status_code`` is what the gateway's retry policy reads,
    ``None`` when no answer came. Once retries are spent the gateway reports it
    as ``MODEL_PROVIDER_FAILED``, so the caller can tell the provider's trouble
    from a fault in SOIT.
    """

    def __init__(self, status_code: int | None, code: str | None, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


@dataclass
class TextLine:
    text: str
    bounding_box: tuple[int, int, int, int] | None
    """On the same canvas as the layer boxes."""
    runs: list[TextRun]


@dataclass
class DecomposedLayer:
    """One element a layer decomposition lifted out of the source image.

    ``bounding_box`` is where the element sits, as ``(left, top, right,
    bottom)`` in the pixels of the base image, which the provider may return
    larger than the source: the base's ``size`` is the canvas the boxes are
    measured on. The layer image need not match its box either, since
    providers return layers at their own output scale; a caller placing a
    layer resizes it to the box.
    """

    image: GeneratedImage
    z_index: int
    """Stacking order; 1 is the lowest layer above the base image."""
    bounding_box: tuple[int, int, int, int] | None = None
    name: str | None = None
    description: str | None = None
    size: str | None = None
    """The returned image's dimensions as ``WIDTHxHEIGHT``, when the provider says."""
    text: str | None = None
    """The text this layer shows, when text recognition was asked for and found some."""
    text_lines: list[TextLine] | None = None
    """The recognized text line by line, with each line's box and styled runs."""


class ImageDecompositionResponse:
    """A source image split into a base image and stacked layers.

    The base is the source with the lifted elements removed and the area
    behind them filled in; the layers are the elements, transparent around
    their edges. ``images`` lists every returned image, the base first, which
    is what the call is billed for.
    """

    def __init__(
        self,
        base: GeneratedImage,
        layers: list[DecomposedLayer],
        base_size: str | None = None,
        model: str | None = None,
        runtime_target: LLMRuntimeTarget | None = None,
        upstream_id: str | None = None,
        upstream_request_id: str | None = None,
    ):
        self.base = base
        self.layers = layers
        self.base_size = base_size
        """The base image's ``WIDTHxHEIGHT``: the canvas every box is measured on."""
        self.model = model
        self.runtime_target = runtime_target
        self.upstream_id = upstream_id
        self.upstream_request_id = upstream_request_id

    @property
    def images(self) -> list[GeneratedImage]:
        return [self.base, *(layer.image for layer in self.layers)]


class RerankResponse:
    """Rerank response from LLM."""

    def __init__(
        self,
        results: list[dict[str, Any]],
        tokens_used: int = 0,
        model: str | None = None,
        runtime_target: LLMRuntimeTarget | None = None,
        upstream_id: str | None = None,
        upstream_request_id: str | None = None,
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
        self.runtime_target = runtime_target
        self.upstream_id = upstream_id
        self.upstream_request_id = upstream_request_id


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
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatStreamChunk]:
        """Stream chat completion."""
        if False:
            yield ChatStreamChunk()
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

    async def generate_image(
        self,
        prompt: str,
        model: str,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> ImageGenerationResponse:
        """Generate images from a text prompt.

        Not abstract on purpose: only gateways with an image-capable backend
        (LiteLLM channel) implement it; chat-only native adapters keep working
        without changes and fail loudly if ever routed an image request.

        Args:
            prompt: Text prompt describing the image.
            model: Model reference (e.g., "model:volcengine:doubao-seedream").
            n: Number of images to generate.
            size: Optional image size hint (e.g., "1024x1024").
            **kwargs: Additional model-specific parameters.

        Returns:
            ImageGenerationResponse instance.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support image generation"
        )

    async def edit_image(
        self,
        image: bytes,
        prompt: str,
        model: str,
        mask: bytes | None = None,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> ImageGenerationResponse:
        """Edit an existing image under a text instruction.

        One method covers the three shapes the same provider call serves:
        inpainting (image + mask), outpainting (a pre-expanded canvas whose new
        margin is masked), and reference editing (image, no mask).

        Not abstract, for the same reason as ``generate_image``: chat-only
        adapters keep working and fail loudly if ever routed an edit.

        Args:
            image: Source image bytes.
            prompt: What the edited region should become.
            mask: Optional selection. SOIT's convention is **white marks the
                region to edit**; adapters convert to whatever their provider
                reads, so callers never see the difference.
            model: Model reference.
            n: Number of images to return.
            size: Optional output size; None follows the input image.
            **kwargs: Additional provider parameters.

        Returns:
            ImageGenerationResponse instance.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support image editing"
        )

    async def decompose_image(
        self,
        image: bytes,
        model: str,
        prompt: str | None = None,
        max_layers: int | None = None,
        text_recognition: bool = False,
        size: str | None = None,
        **kwargs: Any,
    ) -> ImageDecompositionResponse:
        """Split an image into a base image and stacked transparent layers.

        Not abstract, for the same reason as ``generate_image``: only a
        provider with a layer decomposition model implements it.

        Args:
            image: Source image bytes.
            model: Model reference.
            prompt: Optional instruction naming which elements to lift out;
                without one the model picks the main elements itself.
            max_layers: Upper bound on returned layers, the base excluded;
                None leaves it to the provider.
            text_recognition: Also return the text the model recognized,
                line by line with its approximate style.
            size: Output resolution tier as the provider names it.
            **kwargs: Additional provider parameters.

        Returns:
            ImageDecompositionResponse instance.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support image layer decomposition"
        )

    async def check_image_request(
        self,
        model: str,
        *,
        operation: str,
        n: int = 1,
        size: str | None = None,
        has_mask: bool = False,
        **options: Any,
    ) -> None:
        """Refuse an image request this port could not serve as asked.

        Called before a run opens, so a request that could never be served
        as asked is refused without anything being opened, admitted or
        billed. ``operation`` is ``generate`` or ``edit``; ``options`` are
        the image options the call would be given, such as ``background``,
        ``output_format`` or ``seed``. The default refuses nothing: a port
        that cannot tell leaves it to the call.
        """
        del model, operation, n, size, has_mask, options

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
