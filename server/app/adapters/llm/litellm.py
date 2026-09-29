"""LiteLLM SDK adapter implementing the existing LLM port contract."""

from __future__ import annotations

import functools
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Any, cast

from app.adapters.llm.content_parts import openai_chat_content
from app.adapters.llm.litellm_image_routes import (
    EDIT,
    EDIT_OPTIONS,
    GENERATE,
    GENERATE_OPTIONS,
    carried_options,
    image_route,
    is_listed,
    takes_openai_sizes,
)
from app.kernel.commons.errors import KernelError, ValidationError
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

logger = logging.getLogger(__name__)

# Provider settings LiteLLM does not take as parameters of its own. An image
# edit for OpenAI, Azure or a provider LiteLLM treats as OpenAI-compatible
# copies every keyword it does not know into its multipart form, and none of
# these is read on those routes: the cloud credentials are Bedrock's and
# Vertex AI's, and drop_params would reach the provider as a form field.
_SETTINGS_AN_OPENAI_EDIT_WOULD_SEND = frozenset(
    {
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "aws_region_name",
        "vertex_project",
        "vertex_location",
        "drop_params",
    }
)

# Vertex AI's project and location, which its image generation reads from
# LiteLLM's own parameters to build the endpoint URL.
_VERTEX_SETTINGS = ("vertex_project", "vertex_location")


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


def litellm_model_name(model: str, *, provider_kind: str, litellm_provider: str | None) -> str:
    """LiteLLM's ``prefix/model`` for a SOIT model ref served by this provider."""
    model_id = model
    if model.startswith("model:"):
        parts = model.split(":", 2)
        if len(parts) == 3:
            model_id = parts[2]
    prefix = litellm_provider or LITELLM_PROVIDER_PRESETS.get(provider_kind)
    if not prefix:
        raise ValidationError(f"LiteLLM provider kind is unsupported: {provider_kind}")
    if model_id.startswith(f"{prefix}/"):
        return model_id
    return f"{prefix}/{model_id}"


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
        return litellm_model_name(
            model, provider_kind=self.provider_kind, litellm_provider=self.litellm_provider
        )

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
        route, carried = self._check_image_route(
            model, model_name, operation=GENERATE, n=n, size=size, has_mask=False, options=kwargs
        )
        params: dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            **self._body_safe_connection_params(model_name, headers_param="headers"),
        }
        # LiteLLM's image generation copies each keyword it does not know
        # into the provider's parameters, Vertex AI's project and location
        # among them: Imagen's request carried both beside sampleCount. It
        # takes additional_drop_params as its own and leaves the names listed
        # there out of the request, while the parameters it builds the URL
        # from still hold them.
        dropped = [name for name in _VERTEX_SETTINGS if name in params]
        if dropped:
            params["additional_drop_params"] = dropped
        if "n" in carried:
            params["n"] = n
        # LiteLLM's generic image handler ignores the headers parameter and
        # sends only the extra_headers keyword as headers. Gemini and Stability
        # also keep that keyword out of the body; the others it serves, such as
        # OpenRouter, DashScope and Vertex AI, copy it in, so their generations
        # are sent no custom headers.
        if "headers" in params and model_name.split("/", 1)[0] in self._GENERATION_EXTRA_HEADERS_PROVIDERS:
            params["extra_headers"] = params["headers"]
        if self._sends_size(size, route, carried, GENERATE):
            params["size"] = size
        self._apply_response_format(
            params,
            kwargs.get("response_format"),
            operation=GENERATE,
            takes=self._takes_response_format(model_name, GENERATE, route),
        )
        # What the route does not carry was refused or, a png or an auto size
        # it cannot carry, is not sent.
        self._forward_image_options(
            params,
            kwargs,
            tuple(name for name in ("background", "output_format", "quality") if name in carried),
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
        An edit never sends extra_body: its OpenAI-style request copies each
        plain argument into its form under the argument's name, and its
        Bedrock, Stability and Black Forest Labs requests take plain
        arguments, each reading the ones it knows.
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
        """Refuse what this model's LiteLLM route cannot deliver, before any call."""
        model_name = self._model_name(model)
        route, _carried = self._check_image_route(
            model, model_name, operation=operation, n=n, size=size, has_mask=has_mask, options=options
        )
        self._refuse_unreturnable_url(
            model_name,
            options.get("response_format"),
            operation=operation,
            takes=self._takes_response_format(model_name, operation, route),
        )

    @staticmethod
    def _check_image_route(
        model: str,
        model_name: str,
        *,
        operation: str,
        n: int,
        size: str | None,
        has_mask: bool,
        options: Mapping[str, Any],
    ) -> tuple[str, frozenset[str]]:
        """Refuse an option LiteLLM's request for this route has no place for.

        LiteLLM drops such an option, or fails with an error of its own, and
        the call would answer and bill for an image that ignored it. What each
        route carries is recorded in ``litellm_image_routes``; a route it does
        not list carries none of the options. Two values ask for nothing a
        route could drop and are taken unsent where it carries no such
        option: a ``size`` of ``auto``, which leaves the size to the
        provider, and is sent only where the route reads OpenAI's sizes;
        and an ``output_format`` of png. The provider then answers
        in its own format, PNG on most routes though not on all (fal's
        default is JPEG), and the artifact is typed from the bytes that come
        back. ``response_format`` is not refused here: a route that does not
        carry it is not sent it. Returns the route and what it carries.
        """
        route = image_route(model_name, operation)
        if route is None:
            capability = "image_edit" if operation == EDIT else "image_generation"
            raise KernelError(
                "MODEL_CAPABILITY_UNAVAILABLE",
                f"LiteLLM has no image {operation} route for {model_name}",
                {"model": model, "capability": capability, "reason": "no_litellm_route"},
            )
        if not is_listed(route, operation):
            logger.warning(
                "LiteLLM image %s route %s is not in SOIT's route table; its options are refused",
                operation,
                route,
            )
        carried = carried_options(route, operation)
        for name in EDIT_OPTIONS if operation == EDIT else GENERATE_OPTIONS:
            if name == "response_format":
                continue
            if name == "n":
                requested = n > 1
            elif name == "mask":
                requested = has_mask
            elif name == "size":
                requested = size is not None and size != "auto"
            else:
                requested = options.get(name) is not None
            if not requested or name in carried:
                continue
            if name == "output_format" and options.get(name) == "png":
                continue
            what = "more than one image" if name == "n" else name
            details: dict[str, Any] = {
                "model": model,
                "capability": name,
                "param": name,
                "reason": "route_cannot_carry",
                "route": route,
            }
            if name == "n":
                details["max_n"] = 1
            raise KernelError(
                "MODEL_IMAGE_CAPABILITY_UNAVAILABLE",
                f"LiteLLM's image {operation} request for {model_name} has no place "
                f"for {what}, so the provider would never receive it; omit it or "
                "route the call to a model whose request carries it",
                details,
            )
        return route, carried

    @staticmethod
    def _sends_size(size: str | None, route: str, carried: frozenset[str], operation: str) -> bool:
        if size is None or "size" not in carried:
            return False
        return size != "auto" or takes_openai_sizes(route, operation)

    def _takes_response_format(self, model_name: str, operation: str, route: str) -> bool:
        """Whether this call is sent ``response_format``.

        A model's declared ``response_format_param`` decides. Otherwise a
        model the kernel knows refuses it, the gpt-image family, is not sent
        it, although LiteLLM would carry it; and any other model is sent it
        only where its route carries it, since LiteLLM refuses the parameter
        outright on many routes. A route the table does not list keeps the
        kernel's default.
        """
        if not image_takes_response_format(
            self.image_capabilities, model=model_name, operation=operation
        ):
            return False
        declared = (self.image_capabilities or {}).get("response_format_param")
        if isinstance(declared, Mapping) and isinstance(
            cast("Mapping[str, Any]", declared).get(operation), bool
        ):
            return True
        if is_listed(route, operation):
            return "response_format" in carried_options(route, operation)
        return True

    @staticmethod
    def _refuse_unreturnable_url(
        model_name: str, requested: str | None, *, operation: str, takes: bool
    ) -> None:
        if (requested or "b64_json") != "url" or takes:
            return
        raise ValidationError(
            f"Model {model_name} takes no response_format on image "
            f"{operation}s, so it cannot be asked for a URL; "
            "request response_format=b64_json",
            {"param": "response_format"},
        )

    def _apply_response_format(
        self,
        params: dict[str, Any],
        requested: str | None,
        *,
        operation: str,
        takes: bool,
    ) -> None:
        """Ask for inline bytes where the endpoint takes the parameter, and say so where not.

        An endpoint that is sent no response_format answers in its own
        format, bytes or a link, so a caller asking it for URLs is told
        rather than quietly handed base64, which would break the response
        shape they coded against.
        """
        resolved = requested or "b64_json"
        if takes:
            params["response_format"] = resolved
            return
        self._refuse_unreturnable_url(params["model"], resolved, operation=operation, takes=takes)

    @staticmethod
    def _reads_alpha_mask(model: str) -> bool:
        """Whether this model's edit mask reaches an endpoint that reads its alpha.

        LiteLLM routes on the model's prefix, not on the provider kind: an
        OpenAI-compatible provider configured with litellm_provider stability
        sends its edits to Stability. OpenAI, Azure and every provider whose
        LiteLLM edit request reuses the OpenAI one (Azure AI's FLUX, a LiteLLM
        proxy) pass the mask file untouched to an OpenAI-style endpoint,
        where transparent marks the region to replace. Stability, direct or
        on Bedrock, and Vertex's Imagen read the mask's luminance with white
        as the region to edit, SOIT's own convention, so they are sent the
        mask as it is. Black Forest Labs' edit carries no mask at all.
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
        route, carried = self._check_image_route(
            model, model_name, operation=EDIT, n=n, size=size, has_mask=mask is not None, options=kwargs
        )
        # An asynchronous edit drops the extra_headers keyword; every edit
        # route sends the headers parameter.
        connection = self._body_safe_connection_params(model_name, headers_param="headers")
        if self._merges_extra_body(model_name):
            for name in _SETTINGS_AN_OPENAI_EDIT_WOULD_SEND:
                connection.pop(name, None)
        params: dict[str, Any] = {
            "model": model_name,
            "image": image,
            "prompt": prompt,
            **connection,
        }
        if "n" in carried:
            params["n"] = n
        if mask is not None:
            params["mask"] = self._mask_for_provider(mask, params["model"])
        if self._sends_size(size, route, carried, EDIT):
            params["size"] = size
        self._apply_response_format(
            params,
            kwargs.get("response_format"),
            operation=EDIT,
            takes=self._takes_response_format(model_name, EDIT, route),
        )
        # What the route does not carry was refused or, a png or an auto size
        # it cannot carry, is not sent.
        self._forward_image_options(
            params,
            kwargs,
            tuple(
                name
                for name in ("background", "quality", "seed", "strength", "negative_prompt", "output_format")
                if name in carried
            ),
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
