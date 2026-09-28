"""LiteLLM SDK adapter implementing the existing LLM port contract."""

from __future__ import annotations

import functools
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Any, cast

from app.adapters.llm.content_parts import openai_chat_content
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.image_mask import mask_to_openai_alpha
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    GeneratedImage,
    ImageGenerationResponse,
    LLMPort,
    RerankResponse,
    ToolCall,
    ToolCallDelta,
    ToolDefinition,
)
from app.kernel.ports.llm.runtime_config import (
    LITELLM_PROVIDER_PRESETS,
    image_takes_response_format,
    validate_litellm_params,
    validate_litellm_provider_prefix,
)

SDKCall = Callable[..., Awaitable[Any]]


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _reasoning_value(obj: Any) -> str | None:
    """Return only reasoning content explicitly exposed by LiteLLM."""

    value = _value(obj, "reasoning_content")
    if not isinstance(value, str):
        value = _value(obj, "reasoning")
    return value if isinstance(value, str) and value else None


@functools.lru_cache(maxsize=64)
def _azure_ad_token_provider(token: str) -> Callable[[], str]:
    """A provider that hands LiteLLM one configured Azure AD token.

    The same token always gets the same provider: LiteLLM keys the Azure
    clients it caches on the provider's identity, so a new one per call would
    build and keep a new client every time.
    """

    def provide() -> str:
        return token

    return provide


class LiteLLMPort(LLMPort):
    """Provider-scoped LiteLLM adapter without process-global environment mutation."""

    _PROVIDER_PREFIXES = LITELLM_PROVIDER_PRESETS

    # Image generation routes whose only header channel is the extra_headers
    # keyword, and which keep it out of the request body.
    _GENERATION_EXTRA_HEADERS_PROVIDERS = frozenset({"gemini", "stability"})

    def __init__(
        self,
        *,
        provider_kind: str,
        litellm_provider: str | None = None,
        litellm_params: dict[str, Any] | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: float | None = 60.0,
        max_retries: int = 3,
        completion_fn: SDKCall | None = None,
        embedding_fn: SDKCall | None = None,
        rerank_fn: SDKCall | None = None,
        image_generation_fn: SDKCall | None = None,
        image_edit_fn: SDKCall | None = None,
        load_sdk_defaults: bool = True,
        image_capabilities: dict[str, Any] | None = None,
    ) -> None:
        self.provider_kind = provider_kind
        self.litellm_provider = (
            validate_litellm_provider_prefix(litellm_provider)
            if litellm_provider
            else None
        )
        self.litellm_params = validate_litellm_params(
            litellm_params,
            allow_secret_values=True,
        )
        self.api_key = api_key
        self.api_base = api_base
        self.timeout = timeout
        self.max_retries = max_retries
        # The routed model's declared image traits, which decide whether an
        # image endpoint is sent response_format.
        self.image_capabilities = image_capabilities or {}

        if load_sdk_defaults and (
            completion_fn is None
            or embedding_fn is None
            or image_generation_fn is None
            or image_edit_fn is None
        ):
            import litellm

            completion_fn = completion_fn or litellm.acompletion
            embedding_fn = embedding_fn or litellm.aembedding
            rerank_fn = rerank_fn or getattr(litellm, "arerank", None)
            image_generation_fn = image_generation_fn or getattr(
                litellm, "aimage_generation", None
            )
            image_edit_fn = image_edit_fn or getattr(litellm, "aimage_edit", None)

        if completion_fn is None or embedding_fn is None:
            raise ValueError("LiteLLM completion and embedding callables are required")
        self._completion = completion_fn
        self._embedding = embedding_fn
        self._rerank = rerank_fn
        self._image_generation = image_generation_fn
        self._image_edit = image_edit_fn

    def _model_name(self, model: str) -> str:
        model_id = model
        if model.startswith("model:"):
            parts = model.split(":", 2)
            if len(parts) == 3:
                model_id = parts[2]
        prefix = self.litellm_provider or self._PROVIDER_PREFIXES.get(self.provider_kind)
        if not prefix:
            raise ValidationError(f"LiteLLM provider kind is unsupported: {self.provider_kind}")
        if model_id.startswith(f"{prefix}/"):
            return model_id
        return f"{prefix}/{model_id}"

    def _connection_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            **self.litellm_params,
            "num_retries": 0,
        }
        # Without a provider timeout the SDK keeps its own, longer default and
        # the gateway's per-call-type deadline is what ends a slow call.
        if self.timeout is not None:
            params["timeout"] = self.timeout
        if self.api_key:
            params["api_key"] = self.api_key
        if self.api_base:
            params["api_base"] = self.api_base
        return params

    def _body_safe_connection_params(self, model: str, *, headers_param: str) -> dict[str, Any]:
        """Connection settings handed over so that none can become a body field.

        LiteLLM takes a keyword as a connection setting only when it is one of
        the call's own parameters or LiteLLM's; an image generation or an
        embedding copies any other into the provider request, for OpenAI, Azure
        and the providers LiteLLM treats as OpenAI-compatible into the JSON
        body. An extra_headers, project or azure_ad_token passed as it is
        therefore reached the provider as a body field, the Azure AD token in
        clear, while an image edit dropped the headers.

        So the headers go in ``headers_param``, the parameter the call sends as
        request headers, with OpenAI's organization and project as its
        OpenAI-Organization and OpenAI-Project headers on the routes that speak
        OpenAI's API. An Azure AD token goes as a token provider, from which
        LiteLLM builds the Authorization header when no API key is set. Both
        are LiteLLM's own parameters. The organization is passed as well, as
        LiteLLM applies it itself where it can.
        """
        params = self._connection_params()
        project = params.pop("project", None)
        extra_headers = params.pop("extra_headers", None)
        if extra_headers is not None and not isinstance(extra_headers, Mapping):
            raise ValidationError(
                "Provider litellm_params.extra_headers must be an object",
                {"param": "litellm_params.extra_headers"},
            )
        headers: dict[str, Any] = {}
        if self._merges_extra_body(model):
            if params.get("organization"):
                headers["OpenAI-Organization"] = params["organization"]
            if project:
                headers["OpenAI-Project"] = project
        if extra_headers:
            headers.update(cast("Mapping[str, Any]", extra_headers))
        if headers:
            params[headers_param] = headers
        token = params.pop("azure_ad_token", None)
        if token:
            params["azure_ad_token_provider"] = _azure_ad_token_provider(str(token))
        return params

    @staticmethod
    def _messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for message in messages:
            item: dict[str, Any] = {"role": message.role, "content": openai_chat_content(message)}
            if message.tool_call_id:
                item["tool_call_id"] = message.tool_call_id
            if message.name:
                item["name"] = message.name
            if message.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        },
                    }
                    for call in message.tool_calls
                ]
            converted.append(item)
        return converted

    @staticmethod
    def _tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    @staticmethod
    def _parse_tool_arguments(raw_arguments: Any, *, tool_name: str) -> dict[str, Any]:
        try:
            arguments = (
                json.loads(raw_arguments)
                if isinstance(raw_arguments, str)
                else raw_arguments
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"LiteLLM returned invalid tool arguments for {tool_name or 'unknown tool'}"
            ) from exc
        if arguments is None or arguments == "":
            return {}
        if not isinstance(arguments, dict):
            raise ValidationError(
                f"LiteLLM returned invalid tool arguments for {tool_name or 'unknown tool'}"
            )
        return arguments

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
        params: dict[str, Any] = {
            "model": self._model_name(model),
            "messages": self._messages(messages),
            **self._connection_params(),
        }
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if tools:
            params["tools"] = self._tools(tools)
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        for key in ("top_p", "reasoning_effort", "response_format", "seed", "stop"):
            if kwargs.get(key) is not None:
                params[key] = kwargs[key]

        response = await self._completion(**params)
        choice = _value(response, "choices")[0]
        message = _value(choice, "message")
        parsed_calls: list[ToolCall] = []
        for raw_call in _value(message, "tool_calls", []) or []:
            function = _value(raw_call, "function")
            raw_arguments = _value(function, "arguments", "{}")
            tool_name = str(_value(function, "name", ""))
            arguments = self._parse_tool_arguments(raw_arguments, tool_name=tool_name)
            parsed_calls.append(
                ToolCall(
                    id=str(_value(raw_call, "id", "")),
                    name=tool_name,
                    arguments=arguments,
                )
            )
        usage = _value(response, "usage")
        return ChatResponse(
            text=None if parsed_calls else _value(message, "content"),
            reasoning=_reasoning_value(message),
            tokens_prompt=int(_value(usage, "prompt_tokens", 0) or 0),
            tokens_completion=int(_value(usage, "completion_tokens", 0) or 0),
            model=_value(response, "model", params["model"]),
            finish_reason=_value(choice, "finish_reason"),
            tool_calls=parsed_calls or None,
        )

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
        params: dict[str, Any] = {
            "model": self._model_name(model),
            "messages": self._messages(messages),
            "stream": True,
            "stream_options": {"include_usage": True},
            **self._connection_params(),
        }
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if tools:
            params["tools"] = self._tools(tools)
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        for key in ("top_p", "reasoning_effort", "response_format", "seed", "stop"):
            if kwargs.get(key) is not None:
                params[key] = kwargs[key]
        stream = await self._completion(**params)
        assembled_calls: dict[int, dict[str, str]] = {}
        async for event in stream:
            choices = _value(event, "choices", []) or []
            usage = _value(event, "usage")
            choice = choices[0] if choices else None
            raw_delta = _value(choice, "delta") if choice else None
            delta = _value(raw_delta, "content", "") if raw_delta else ""
            reasoning_delta = _reasoning_value(raw_delta) if raw_delta else None
            tool_call_deltas: list[ToolCallDelta] = []
            for position, raw_call in enumerate(
                _value(raw_delta, "tool_calls", []) or []
            ):
                index = int(_value(raw_call, "index", position) or 0)
                function = _value(raw_call, "function")
                call_id = _value(raw_call, "id")
                name_delta = _value(function, "name")
                arguments_delta = _value(function, "arguments", "") or ""
                state = assembled_calls.setdefault(
                    index,
                    {"id": "", "name": "", "arguments": ""},
                )
                if call_id:
                    state["id"] = str(call_id)
                if name_delta:
                    state["name"] += str(name_delta)
                state["arguments"] += str(arguments_delta)
                tool_call_deltas.append(
                    ToolCallDelta(
                        index=index,
                        id=str(call_id) if call_id else None,
                        name=str(name_delta) if name_delta else None,
                        arguments_delta=str(arguments_delta),
                    )
                )
            finish_reason = _value(choice, "finish_reason") if choice else None
            completed_calls: list[ToolCall] | None = None
            if finish_reason is not None and assembled_calls:
                completed_calls = []
                for index in sorted(assembled_calls):
                    state = assembled_calls[index]
                    completed_calls.append(
                        ToolCall(
                            id=state["id"],
                            name=state["name"],
                            arguments=self._parse_tool_arguments(
                                state["arguments"],
                                tool_name=state["name"],
                            ),
                        )
                    )
            yield ChatStreamChunk(
                delta=delta or "",
                reasoning_delta=reasoning_delta or "",
                done=finish_reason is not None or (not choices and usage is not None),
                tokens_prompt=int(_value(usage, "prompt_tokens", 0) or 0),
                tokens_completion=int(_value(usage, "completion_tokens", 0) or 0),
                model=_value(event, "model", params["model"]),
                finish_reason=finish_reason,
                tool_call_deltas=tool_call_deltas or None,
                tool_calls=completed_calls,
            )

    async def embed(self, texts: list[str], model: str, **kwargs: Any) -> EmbeddingResponse:
        model_name = self._model_name(model)
        response = await self._embedding(
            model=model_name,
            input=texts,
            # LiteLLM's embedding counts the extra_headers keyword among its own
            # parameters, so it never copies it into the body.
            **self._body_safe_connection_params(model_name, headers_param="extra_headers"),
        )
        data = _value(response, "data", []) or []
        usage = _value(response, "usage")
        return EmbeddingResponse(
            embeddings=[list(_value(item, "embedding", [])) for item in data],
            tokens_used=int(_value(usage, "total_tokens", 0) or 0),
            model=_value(response, "model", model_name),
        )

    async def generate_image(
        self,
        prompt: str,
        model: str,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> ImageGenerationResponse:
        if self._image_generation is None:
            raise ValidationError("LiteLLM image generation capability is unavailable")
        model_name = self._model_name(model)
        params: dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "n": n,
            **self._body_safe_connection_params(model_name, headers_param="headers"),
        }
        # LiteLLM's generic image handler ignores the headers parameter and
        # sends only the extra_headers keyword as headers. Gemini and Stability
        # also keep that keyword out of the body; the others it serves, such as
        # OpenRouter, DashScope and Vertex AI, copy it in, so their generations
        # are sent no custom headers.
        if "headers" in params and model_name.split("/", 1)[0] in self._GENERATION_EXTRA_HEADERS_PROVIDERS:
            params["extra_headers"] = params["headers"]
        if size is not None:
            params["size"] = size
        # Prefer inline bytes so callers own storage; providers without
        # b64 support ignore the hint and return URLs instead.
        self._apply_response_format(params, kwargs.get("response_format"), operation="generate")
        self._forward_image_options(
            params,
            kwargs,
            ("background", "output_format"),
            in_extra_body=self._merges_extra_body(params["model"]),
        )
        response = await self._image_generation(**params)
        images: list[GeneratedImage] = []
        for item in _value(response, "data", []) or []:
            images.append(
                GeneratedImage(
                    b64_json=_value(item, "b64_json"),
                    url=_value(item, "url"),
                )
            )
        return ImageGenerationResponse(
            images=images,
            model=_value(response, "model", params["model"]),
        )

    @staticmethod
    def _merges_extra_body(model: str) -> bool:
        """Whether LiteLLM merges extra_body into this model's request body.

        It does for OpenAI, Azure and the providers it treats as
        OpenAI-compatible; any other is sent a literal field named extra_body.
        """
        prefix = model.split("/", 1)[0]
        if prefix in ("openai", "azure"):
            return True
        try:
            import litellm
        except ImportError:
            return False
        return prefix in getattr(litellm, "openai_compatible_providers", ())

    @staticmethod
    def _forward_image_options(
        params: dict[str, Any],
        kwargs: dict[str, Any],
        names: tuple[str, ...],
        *,
        in_extra_body: bool,
    ) -> None:
        """Place image options where LiteLLM carries them to the provider.

        LiteLLM drops what it does not map without a word. A generation for
        OpenAI, Azure or a provider LiteLLM treats as OpenAI-compatible keeps
        only a handful of OpenAI keys, so a background passed to gpt-image as
        a plain argument never reaches the wire, while extra_body is merged
        into the body; other providers take the options as plain arguments.
        An edit never sends extra_body: its OpenAI-style request keeps a fixed
        field list, background among them, and its Bedrock, Stability and
        Black Forest Labs requests take plain arguments, each reading the ones
        it knows.
        """
        body = dict(kwargs.get("extra_body") or {})
        for name in names:
            value = kwargs.get(name)
            if value is None:
                continue
            if in_extra_body:
                body[name] = value
            else:
                params[name] = value
        if body:
            params["extra_body"] = body

    def _apply_response_format(
        self,
        params: dict[str, Any],
        requested: str | None,
        *,
        operation: str,
    ) -> None:
        """Ask for inline bytes where the endpoint takes the parameter, and say so where not.

        Whether it does is the routed model's declared trait, per endpoint,
        or the kernel's default for models known to refuse it. An endpoint
        that is sent no response_format answers in its own format, so a
        caller asking it for URLs is told rather than quietly handed base64,
        which would break the response shape they coded against.
        """
        resolved = requested or "b64_json"
        if image_takes_response_format(
            self.image_capabilities, model=params["model"], operation=operation
        ):
            params["response_format"] = resolved
            return
        if resolved == "url":
            raise ValidationError(
                f"Model {params['model']} takes no response_format on image "
                f"{operation}s, so it cannot be asked for a URL; "
                "request response_format=b64_json",
                {"param": "response_format"},
            )

    @staticmethod
    def _reads_alpha_mask(model: str) -> bool:
        """Whether this model's edit mask reaches an endpoint that reads its alpha.

        LiteLLM routes on the model's prefix, not on the provider kind: an
        OpenAI-compatible provider configured with litellm_provider stability
        sends its edits to Stability. OpenAI, Azure and every provider whose
        LiteLLM edit request reuses the OpenAI one (Azure AI's FLUX, a LiteLLM
        proxy) pass the mask file untouched to an OpenAI-style endpoint,
        where transparent marks the region to replace. Stability, direct or
        on Bedrock, Black Forest Labs and Vertex's Imagen read the mask's
        luminance with white as the region to edit, SOIT's own convention,
        so they are sent the mask as it is.
        """
        prefix, _, name = model.partition("/")
        if prefix in ("openai", "azure"):
            return True
        try:
            from litellm.llms.openai.image_edit.transformation import (
                OpenAIImageEditConfig,
            )
            from litellm.types.utils import LlmProviders
            from litellm.utils import ProviderConfigManager

            config = ProviderConfigManager.get_provider_image_edit_config(
                model=name,
                provider=LlmProviders(prefix),
            )
        except (ImportError, ValueError):
            # Not a LiteLLM provider, or not a model it can edit with.
            return False
        return isinstance(config, OpenAIImageEditConfig)

    @classmethod
    def _mask_for_provider(cls, mask: bytes, model: str) -> bytes:
        if cls._reads_alpha_mask(model):
            return mask_to_openai_alpha(mask)
        return mask

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
        if self._image_edit is None:
            raise ValidationError("LiteLLM image editing capability is unavailable")
        model_name = self._model_name(model)
        params: dict[str, Any] = {
            "model": model_name,
            "image": image,
            "prompt": prompt,
            "n": n,
            # An asynchronous edit drops the extra_headers keyword; every edit
            # route sends the headers parameter.
            **self._body_safe_connection_params(model_name, headers_param="headers"),
        }
        if mask is not None:
            params["mask"] = self._mask_for_provider(mask, params["model"])
        if size is not None:
            params["size"] = size
        self._apply_response_format(params, kwargs.get("response_format"), operation="edit")
        # OpenAI-style providers receive only background of these: LiteLLM's
        # edit request there has no field for the rest.
        self._forward_image_options(
            params,
            kwargs,
            ("background", "seed", "strength", "negative_prompt", "output_format"),
            in_extra_body=False,
        )

        response = await self._image_edit(**params)
        images: list[GeneratedImage] = []
        for item in _value(response, "data", []) or []:
            images.append(
                GeneratedImage(
                    b64_json=_value(item, "b64_json"),
                    url=_value(item, "url"),
                )
            )
        return ImageGenerationResponse(
            images=images,
            model=_value(response, "model", params["model"]),
        )

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        if self._rerank is None:
            raise ValidationError("LiteLLM rerank capability is unavailable")
        params: dict[str, Any] = {
            "model": self._model_name(model),
            "query": query,
            "documents": documents,
            **self._connection_params(),
        }
        if top_n is not None:
            params["top_n"] = top_n
        response = await self._rerank(**params)
        usage = _value(response, "usage")
        results = []
        for item in _value(response, "results", []) or []:
            results.append(
                {
                    "index": _value(item, "index"),
                    "score": _value(item, "relevance_score", _value(item, "score")),
                    "document": _value(item, "document"),
                }
            )
        return RerankResponse(
            results=results,
            tokens_used=int(_value(usage, "total_tokens", 0) or 0),
            model=_value(response, "model", params["model"]),
        )
