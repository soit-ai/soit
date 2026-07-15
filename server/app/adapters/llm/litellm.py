"""LiteLLM SDK adapter implementing the existing LLM port contract."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
    ToolCall,
    ToolCallDelta,
    ToolDefinition,
)
from app.kernel.ports.llm.runtime_config import (
    LITELLM_PROVIDER_PRESETS,
    validate_litellm_params,
    validate_litellm_provider_prefix,
)

SDKCall = Callable[..., Awaitable[Any]]


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class LiteLLMPort(LLMPort):
    """Provider-scoped LiteLLM adapter without process-global environment mutation."""

    _PROVIDER_PREFIXES = LITELLM_PROVIDER_PRESETS

    def __init__(
        self,
        *,
        provider_kind: str,
        litellm_provider: str | None = None,
        litellm_params: dict[str, Any] | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        completion_fn: SDKCall | None = None,
        embedding_fn: SDKCall | None = None,
        rerank_fn: SDKCall | None = None,
        load_sdk_defaults: bool = True,
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

        if load_sdk_defaults and (completion_fn is None or embedding_fn is None):
            try:
                import litellm
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "LiteLLM adapter requires the llm-litellm optional dependency"
                ) from exc
            completion_fn = completion_fn or litellm.acompletion
            embedding_fn = embedding_fn or litellm.aembedding
            rerank_fn = rerank_fn or getattr(litellm, "arerank", None)

        if completion_fn is None or embedding_fn is None:
            raise ValueError("LiteLLM completion and embedding callables are required")
        self._completion = completion_fn
        self._embedding = embedding_fn
        self._rerank = rerank_fn

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
            "timeout": self.timeout,
            "num_retries": 0,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.api_base:
            params["api_base"] = self.api_base
        return params

    @staticmethod
    def _messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for message in messages:
            item: dict[str, Any] = {"role": message.role, "content": message.content}
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
                done=finish_reason is not None or (not choices and usage is not None),
                tokens_prompt=int(_value(usage, "prompt_tokens", 0) or 0),
                tokens_completion=int(_value(usage, "completion_tokens", 0) or 0),
                model=_value(event, "model", params["model"]),
                finish_reason=finish_reason,
                tool_call_deltas=tool_call_deltas or None,
                tool_calls=completed_calls,
            )

    async def embed(self, texts: list[str], model: str, **kwargs: Any) -> EmbeddingResponse:
        response = await self._embedding(
            model=self._model_name(model),
            input=texts,
            **self._connection_params(),
        )
        data = _value(response, "data", []) or []
        usage = _value(response, "usage")
        return EmbeddingResponse(
            embeddings=[list(_value(item, "embedding", [])) for item in data],
            tokens_used=int(_value(usage, "total_tokens", 0) or 0),
            model=_value(response, "model", self._model_name(model)),
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
