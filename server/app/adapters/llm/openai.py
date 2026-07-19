""" openai_llm

OpenAI LLM port adapter implementation.
"""

import hashlib as _hashlib
import json as _json
import mimetypes as _mimetypes
import re as _re
from typing import Any

import numpy as np
from openai import AsyncOpenAI

from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    HostedArtifact,
    HostedToolCall,
    LLMPort,
    RerankResponse,
    ToolCall,
    ToolCallDelta,
    ToolDefinition,
)


class OpenAILLMPort(LLMPort):
    """OpenAI LLM port adapter."""

    _TOOL_NAME_PATTERN = _re.compile(r"^[A-Za-z0-9_-]{1,64}$")

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        use_responses_api: bool | None = None,
    ):
        """Initialize OpenAI gateway.

        Args:
            api_key: OpenAI API key (if None, uses settings or env var).
            base_url: Optional OpenAI-compatible API base URL.
        """
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._use_responses_api = (
            base_url is None if use_responses_api is None else use_responses_api
        )

    @classmethod
    def _tool_name_alias(cls, name: str) -> str:
        if cls._TOOL_NAME_PATTERN.fullmatch(name):
            return name
        normalized = _re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_-") or "tool"
        digest = _hashlib.sha256(name.encode("utf-8")).hexdigest()[:10]
        return f"{normalized[:53]}_{digest}"

    @classmethod
    def _tool_name_maps(
        cls,
        tools: list[ToolDefinition] | None,
    ) -> tuple[dict[str, str], dict[str, str]]:
        outbound = {
            tool.name: cls._tool_name_alias(tool.name)
            for tool in tools or []
        }
        return outbound, {alias: original for original, alias in outbound.items()}

    @classmethod
    def _convert_messages(
        cls,
        messages: list[ChatMessage],
        tool_name_map: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Convert ChatMessage list to OpenAI message format."""
        tool_name_map = tool_name_map or {}
        openai_messages = []
        for msg in messages:
            m: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.role == "assistant" and msg.tool_calls:
                m["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tool_name_map.get(tc.name, cls._tool_name_alias(tc.name)),
                            "arguments": _json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            if msg.role == "tool" and msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.name:
                m["name"] = tool_name_map.get(msg.name, cls._tool_name_alias(msg.name))
            openai_messages.append(m)
        return openai_messages

    @classmethod
    def _convert_responses_input(
        cls,
        messages: list[ChatMessage],
        tool_name_map: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Convert normalized messages to Responses API input items."""

        tool_name_map = tool_name_map or {}
        items: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "tool" and message.tool_call_id:
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": message.tool_call_id,
                        "output": message.content or "",
                    }
                )
                continue
            if message.content is not None:
                items.append({"role": message.role, "content": message.content})
            if message.role == "assistant" and message.tool_calls:
                items.extend(
                    {
                        "type": "function_call",
                        "call_id": call.id,
                        "name": tool_name_map.get(
                            call.name,
                            cls._tool_name_alias(call.name),
                        ),
                        "arguments": _json.dumps(call.arguments),
                    }
                    for call in message.tool_calls
                )
        return items

    def _should_use_responses_api(self, model_name: str) -> bool:
        """Use Responses only for supported official OpenAI model families."""

        return self._use_responses_api and model_name.lower().startswith("gpt-5.5")

    @staticmethod
    def _responses_tools(
        tools: list[ToolDefinition] | None,
        tool_name_map: dict[str, str],
    ) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": tool_name_map[tool.name],
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in tools or []
        ]

    @staticmethod
    def _validate_hosted_tools(tools: list[dict[str, Any]]) -> None:
        supported = {"web_search", "code_interpreter"}
        for tool in tools:
            if not isinstance(tool, dict) or tool.get("type") not in supported:
                raise ValidationError("Unsupported OpenAI hosted tool")

    @classmethod
    def _jsonable(cls, value: Any) -> Any:
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, dict):
            return {str(key): cls._jsonable(item) for key, item in value.items()}
        if isinstance(value, list | tuple):
            return [cls._jsonable(item) for item in value]
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return cls._jsonable(model_dump(exclude_none=True))
        if hasattr(value, "__dict__"):
            return cls._jsonable(
                {
                    key: item
                    for key, item in vars(value).items()
                    if not key.startswith("_")
                }
            )
        return str(value)

    @classmethod
    def _parse_responses_hosted_tool_calls(cls, response: Any) -> list[HostedToolCall]:
        calls: list[HostedToolCall] = []
        for item in getattr(response, "output", []) or []:
            item_type = getattr(item, "type", None)
            if item_type == "web_search_call":
                action = getattr(item, "action", None)
                action_data = cls._jsonable(action)
                calls.append(
                    HostedToolCall(
                        id=str(getattr(item, "id", "") or ""),
                        name="openai.web_search",
                        status=str(getattr(item, "status", "completed") or "completed"),
                        arguments={
                            "action": action_data.get("type")
                            if isinstance(action_data, dict)
                            else None,
                            "query": action_data.get("query")
                            if isinstance(action_data, dict)
                            else None,
                        },
                        result={
                            "status": str(
                                getattr(item, "status", "completed") or "completed"
                            ),
                            "sources": action_data.get("sources", [])
                            if isinstance(action_data, dict)
                            else [],
                        },
                    )
                )
            elif item_type == "code_interpreter_call":
                calls.append(
                    HostedToolCall(
                        id=str(getattr(item, "id", "") or ""),
                        name="openai.code_interpreter",
                        status=str(getattr(item, "status", "completed") or "completed"),
                        arguments={
                            "container_id": str(
                                getattr(item, "container_id", "") or ""
                            ),
                            "code": str(getattr(item, "code", "") or ""),
                        },
                        result={
                            "status": str(
                                getattr(item, "status", "completed") or "completed"
                            ),
                            "outputs": cls._jsonable(getattr(item, "outputs", []) or []),
                        },
                    )
                )
        return calls

    async def _parse_responses_annotations(
        self,
        response: Any,
    ) -> tuple[list[dict[str, Any]], list[HostedArtifact]]:
        citations: list[dict[str, Any]] = []
        artifacts: list[HostedArtifact] = []
        seen_files: set[tuple[str, str]] = set()
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "message":
                continue
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", None) != "output_text":
                    continue
                for annotation in getattr(content, "annotations", []) or []:
                    annotation_type = getattr(annotation, "type", None)
                    if annotation_type == "url_citation":
                        url = str(getattr(annotation, "url", "") or "")
                        citations.append(
                            {
                                "type": "url",
                                "title": str(
                                    getattr(annotation, "title", "") or url
                                ),
                                "url": url,
                                "source_uri": url,
                                "start_index": getattr(annotation, "start_index", None),
                                "end_index": getattr(annotation, "end_index", None),
                            }
                        )
                    elif annotation_type == "container_file_citation":
                        container_id = str(
                            getattr(annotation, "container_id", "") or ""
                        )
                        file_id = str(getattr(annotation, "file_id", "") or "")
                        if not container_id or not file_id:
                            continue
                        identity = (container_id, file_id)
                        if identity in seen_files:
                            continue
                        seen_files.add(identity)
                        filename = str(
                            getattr(annotation, "filename", "") or file_id
                        )
                        binary = await self.client.containers.files.content.retrieve(
                            file_id,
                            container_id=container_id,
                        )
                        artifacts.append(
                            HostedArtifact(
                                container_id=container_id,
                                file_id=file_id,
                                filename=filename,
                                content=await binary.aread(),
                                mime=_mimetypes.guess_type(filename)[0],
                            )
                        )
        return citations, artifacts

    @staticmethod
    def _responses_reasoning(response: Any) -> str | None:
        parts = [
            str(getattr(summary, "text", "") or "")
            for item in getattr(response, "output", []) or []
            if getattr(item, "type", None) == "reasoning"
            for summary in getattr(item, "summary", []) or []
        ]
        value = "\n\n".join(part for part in parts if part)
        return value or None

    @staticmethod
    def _responses_text(response: Any) -> str | None:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text:
            return output_text
        parts = [
            str(getattr(content, "text", "") or "")
            for item in getattr(response, "output", []) or []
            if getattr(item, "type", None) == "message"
            for content in getattr(item, "content", []) or []
            if getattr(content, "type", None) == "output_text"
        ]
        value = "".join(part for part in parts if part)
        return value or None

    @staticmethod
    def _responses_finish_reason(response: Any, *, has_tool_calls: bool) -> str:
        if has_tool_calls:
            return "tool_calls"
        if getattr(response, "status", None) == "incomplete":
            reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
            return "length" if reason == "max_output_tokens" else str(reason or "incomplete")
        return "stop"

    @classmethod
    def _parse_responses_tool_calls(
        cls,
        response: Any,
        reverse_tool_name_map: dict[str, str],
    ) -> list[ToolCall] | None:
        calls: list[ToolCall] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "function_call":
                continue
            raw_arguments = getattr(item, "arguments", "{}") or "{}"
            try:
                arguments = _json.loads(raw_arguments)
            except (TypeError, ValueError):
                arguments = {}
            provider_name = str(getattr(item, "name", "") or "")
            calls.append(
                ToolCall(
                    id=str(
                        getattr(item, "call_id", None)
                        or getattr(item, "id", None)
                        or ""
                    ),
                    name=reverse_tool_name_map.get(provider_name, provider_name),
                    arguments=arguments,
                )
            )
        return calls or None

    async def _chat_responses(
        self,
        *,
        messages: list[ChatMessage],
        model_name: str,
        temperature: float | None,
        max_tokens: int | None,
        tools: list[ToolDefinition] | None,
        tool_choice: str | None,
        kwargs: dict[str, Any],
    ) -> ChatResponse:
        tool_name_map, reverse_tool_name_map = self._tool_name_maps(tools)
        hosted_tools = list(kwargs.get("hosted_tools") or [])
        self._validate_hosted_tools(hosted_tools)
        params: dict[str, Any] = {
            "model": model_name,
            "input": self._convert_responses_input(messages, tool_name_map),
        }
        response_tools = [
            *self._responses_tools(tools, tool_name_map),
            *hosted_tools,
        ]
        if response_tools:
            params["tools"] = response_tools
        if any(tool.get("type") == "web_search" for tool in hosted_tools):
            params["include"] = ["web_search_call.action.sources"]
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        reasoning_effort = kwargs.get("reasoning_effort")
        if reasoning_effort:
            params["reasoning"] = {
                "effort": reasoning_effort,
                "summary": "auto",
            }
        resolved_temperature = self._resolve_temperature_param(model_name, temperature)
        if resolved_temperature is not None:
            params["temperature"] = resolved_temperature
        if max_tokens is not None:
            params["max_output_tokens"] = max_tokens
        top_p = kwargs.get("top_p")
        if top_p is not None:
            params["top_p"] = top_p

        response = await self.client.responses.create(**params)
        parsed_tool_calls = self._parse_responses_tool_calls(
            response,
            reverse_tool_name_map,
        )
        hosted_tool_calls = self._parse_responses_hosted_tool_calls(response)
        citations, hosted_artifacts = await self._parse_responses_annotations(response)
        usage = getattr(response, "usage", None)
        return ChatResponse(
            text=None if parsed_tool_calls else self._responses_text(response),
            reasoning=self._responses_reasoning(response),
            tokens_prompt=int(getattr(usage, "input_tokens", 0) or 0),
            tokens_completion=int(getattr(usage, "output_tokens", 0) or 0),
            model=str(getattr(response, "model", None) or model_name),
            finish_reason=self._responses_finish_reason(
                response,
                has_tool_calls=bool(parsed_tool_calls),
            ),
            tool_calls=parsed_tool_calls,
            hosted_tool_calls=hosted_tool_calls,
            citations=citations,
            hosted_artifacts=hosted_artifacts,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> ChatResponse:
        """Chat completion via OpenAI."""
        model_name = self._resolve_model_name(model)
        hosted_tools = list(kwargs.get("hosted_tools") or [])
        if hosted_tools and not self._should_use_responses_api(model_name):
            raise ValidationError(
                "Hosted tools require official OpenAI GPT-5.5 Responses API"
            )
        if self._should_use_responses_api(model_name):
            return await self._chat_responses(
                messages=messages,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                kwargs=kwargs,
            )
        tool_name_map, reverse_tool_name_map = self._tool_name_maps(tools)
        openai_messages = self._convert_messages(messages, tool_name_map)

        params: dict[str, Any] = {
            "model": model_name,
            "messages": openai_messages,
        }
        resolved_temperature = self._resolve_temperature_param(model_name, temperature)
        if resolved_temperature is not None:
            params["temperature"] = resolved_temperature
        if max_tokens is not None:
            params[self._token_limit_param(model_name)] = max_tokens

        # Function calling parameters
        if tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool_name_map[td.name],
                        "description": td.description,
                        "parameters": td.parameters,
                    },
                }
                for td in tools
            ]
        if tool_choice is not None:
            params["tool_choice"] = tool_choice

        reasoning_effort = kwargs.get("reasoning_effort")
        if reasoning_effort and self._supports_reasoning_effort(model_name):
            params["reasoning_effort"] = reasoning_effort
        top_p = kwargs.get("top_p")
        if top_p is not None:
            params["top_p"] = top_p

        response = await self.client.chat.completions.create(**params)

        choice = response.choices[0]

        # Parse tool_calls from response
        parsed_tool_calls = None
        if choice.message.tool_calls:
            parsed_tool_calls = []
            for tc in choice.message.tool_calls:
                try:
                    arguments = _json.loads(tc.function.arguments)
                except (ValueError, TypeError):
                    arguments = {}
                parsed_tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=reverse_tool_name_map.get(tc.function.name, tc.function.name),
                        arguments=arguments,
                    )
                )

        return ChatResponse(
            text=choice.message.content if not parsed_tool_calls else None,
            reasoning=self._reasoning_text(choice.message),
            tokens_prompt=response.usage.prompt_tokens if response.usage else 0,
            tokens_completion=response.usage.completion_tokens if response.usage else 0,
            model=model_name,
            finish_reason=choice.finish_reason,
            tool_calls=parsed_tool_calls,
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
        **kwargs,
    ):
        """Stream chat completion via OpenAI."""
        model_name = self._resolve_model_name(model)
        hosted_tools = list(kwargs.get("hosted_tools") or [])
        if hosted_tools and not self._should_use_responses_api(model_name):
            raise ValidationError(
                "Hosted tools require official OpenAI GPT-5.5 Responses API"
            )
        if self._should_use_responses_api(model_name):
            async for chunk in self._stream_chat_responses(
                messages=messages,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                kwargs=kwargs,
            ):
                yield chunk
            return
        tool_name_map, reverse_tool_name_map = self._tool_name_maps(tools)
        openai_messages = self._convert_messages(messages, tool_name_map)

        params: dict[str, Any] = {
            "model": model_name,
            "messages": openai_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        resolved_temperature = self._resolve_temperature_param(model_name, temperature)
        if resolved_temperature is not None:
            params["temperature"] = resolved_temperature
        if max_tokens is not None:
            params[self._token_limit_param(model_name)] = max_tokens
        if tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool_name_map[tool.name],
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        reasoning_effort = kwargs.get("reasoning_effort")
        if reasoning_effort and self._supports_reasoning_effort(model_name):
            params["reasoning_effort"] = reasoning_effort
        top_p = kwargs.get("top_p")
        if top_p is not None:
            params["top_p"] = top_p

        stream = await self.client.chat.completions.create(**params)
        assembled_calls: dict[int, dict[str, str]] = {}
        async for event in stream:
            if not event.choices:
                usage = getattr(event, "usage", None)
                if usage:
                    yield ChatStreamChunk(
                        delta="",
                        done=True,
                        tokens_prompt=usage.prompt_tokens or 0,
                        tokens_completion=usage.completion_tokens or 0,
                        model=model_name,
                        finish_reason=None,
                    )
                continue

            choice = event.choices[0]
            delta = ""
            if choice.delta and choice.delta.content:
                delta = choice.delta.content
            reasoning_delta = self._reasoning_text(choice.delta) if choice.delta else None
            tool_call_deltas: list[ToolCallDelta] = []
            for position, raw_call in enumerate(
                getattr(choice.delta, "tool_calls", None) or []
            ):
                index = int(getattr(raw_call, "index", position) or 0)
                function = getattr(raw_call, "function", None)
                call_id = getattr(raw_call, "id", None)
                name_delta = getattr(function, "name", None)
                arguments_delta = getattr(function, "arguments", "") or ""
                state = assembled_calls.setdefault(
                    index,
                    {"id": "", "name": "", "arguments": ""},
                )
                if call_id:
                    state["id"] = str(call_id)
                if name_delta:
                    state["name"] += str(name_delta)
                state["arguments"] += str(arguments_delta)
                emitted_name = None
                if name_delta:
                    emitted_name = reverse_tool_name_map.get(
                        state["name"],
                        str(name_delta),
                    )
                tool_call_deltas.append(
                    ToolCallDelta(
                        index=index,
                        id=str(call_id) if call_id else None,
                        name=emitted_name,
                        arguments_delta=str(arguments_delta),
                    )
                )

            done = choice.finish_reason is not None
            usage = getattr(event, "usage", None)
            tokens_prompt = usage.prompt_tokens if usage else 0
            tokens_completion = usage.completion_tokens if usage else 0
            completed_calls: list[ToolCall] | None = None
            if done and assembled_calls:
                completed_calls = []
                for index in sorted(assembled_calls):
                    state = assembled_calls[index]
                    try:
                        arguments = _json.loads(state["arguments"])
                    except (ValueError, TypeError):
                        arguments = {}
                    completed_calls.append(
                        ToolCall(
                            id=state["id"],
                            name=reverse_tool_name_map.get(
                                state["name"],
                                state["name"],
                            ),
                            arguments=arguments,
                        )
                    )

            yield ChatStreamChunk(
                delta=delta,
                reasoning_delta=reasoning_delta or "",
                done=done,
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
                model=model_name,
                finish_reason=choice.finish_reason,
                tool_call_deltas=tool_call_deltas or None,
                tool_calls=completed_calls,
            )

    async def _stream_chat_responses(
        self,
        *,
        messages: list[ChatMessage],
        model_name: str,
        temperature: float | None,
        max_tokens: int | None,
        tools: list[ToolDefinition] | None,
        tool_choice: str | None,
        kwargs: dict[str, Any],
    ):
        tool_name_map, reverse_tool_name_map = self._tool_name_maps(tools)
        hosted_tools = list(kwargs.get("hosted_tools") or [])
        self._validate_hosted_tools(hosted_tools)
        params: dict[str, Any] = {
            "model": model_name,
            "input": self._convert_responses_input(messages, tool_name_map),
            "stream": True,
        }
        response_tools = [
            *self._responses_tools(tools, tool_name_map),
            *hosted_tools,
        ]
        if response_tools:
            params["tools"] = response_tools
        if any(tool.get("type") == "web_search" for tool in hosted_tools):
            params["include"] = ["web_search_call.action.sources"]
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        reasoning_effort = kwargs.get("reasoning_effort")
        if reasoning_effort:
            params["reasoning"] = {
                "effort": reasoning_effort,
                "summary": "auto",
            }
        resolved_temperature = self._resolve_temperature_param(model_name, temperature)
        if resolved_temperature is not None:
            params["temperature"] = resolved_temperature
        if max_tokens is not None:
            params["max_output_tokens"] = max_tokens
        top_p = kwargs.get("top_p")
        if top_p is not None:
            params["top_p"] = top_p

        stream = await self.client.responses.create(**params)
        stream_calls: dict[int, tuple[str | None, str | None]] = {}
        async for event in stream:
            event_type = str(getattr(event, "type", "") or "")
            output_index = int(getattr(event, "output_index", 0) or 0)
            if event_type == "response.output_item.added":
                item = getattr(event, "item", None)
                if getattr(item, "type", None) != "function_call":
                    continue
                call_id = str(
                    getattr(item, "call_id", None)
                    or getattr(item, "id", None)
                    or ""
                )
                provider_name = str(getattr(item, "name", "") or "")
                tool_name = reverse_tool_name_map.get(provider_name, provider_name)
                stream_calls[output_index] = (call_id or None, tool_name or None)
                yield ChatStreamChunk(
                    model=model_name,
                    tool_call_deltas=[
                        ToolCallDelta(
                            index=output_index,
                            id=call_id or None,
                            name=tool_name or None,
                        )
                    ],
                )
                continue
            if event_type == "response.function_call_arguments.delta":
                call_id, tool_name = stream_calls.get(output_index, (None, None))
                yield ChatStreamChunk(
                    model=model_name,
                    tool_call_deltas=[
                        ToolCallDelta(
                            index=output_index,
                            id=call_id,
                            name=tool_name,
                            arguments_delta=str(getattr(event, "delta", "") or ""),
                        )
                    ],
                )
                continue
            if event_type == "response.output_text.delta":
                yield ChatStreamChunk(
                    delta=str(getattr(event, "delta", "") or ""),
                    model=model_name,
                )
                continue
            if event_type in {
                "response.reasoning_summary_text.delta",
                "response.reasoning_text.delta",
            }:
                yield ChatStreamChunk(
                    reasoning_delta=str(getattr(event, "delta", "") or ""),
                    model=model_name,
                )
                continue
            if event_type == "response.failed":
                response = getattr(event, "response", None)
                provider_error = getattr(response, "error", None)
                raise KernelError(
                    "LLM_PROVIDER_ERROR",
                    "OpenAI Responses stream failed",
                    details={
                        "provider": "openai",
                        "provider_error_code": str(
                            getattr(provider_error, "code", "") or "response_failed"
                        ),
                    },
                )
            if event_type not in {"response.completed", "response.incomplete"}:
                continue
            response = getattr(event, "response", None)
            parsed_tool_calls = self._parse_responses_tool_calls(
                response,
                reverse_tool_name_map,
            )
            hosted_tool_calls = self._parse_responses_hosted_tool_calls(response)
            citations, hosted_artifacts = await self._parse_responses_annotations(
                response
            )
            usage = getattr(response, "usage", None)
            yield ChatStreamChunk(
                done=True,
                tokens_prompt=int(getattr(usage, "input_tokens", 0) or 0),
                tokens_completion=int(getattr(usage, "output_tokens", 0) or 0),
                model=str(getattr(response, "model", None) or model_name),
                finish_reason=self._responses_finish_reason(
                    response,
                    has_tool_calls=bool(parsed_tool_calls),
                ),
                tool_calls=parsed_tool_calls,
                hosted_tool_calls=hosted_tool_calls,
                citations=citations,
                hosted_artifacts=hosted_artifacts,
            )

    @staticmethod
    def _reasoning_text(message: Any) -> str | None:
        """Return only reasoning content explicitly exposed by the provider."""

        value = getattr(message, "reasoning_content", None)
        if not isinstance(value, str):
            value = getattr(message, "reasoning", None)
        return value if isinstance(value, str) and value else None

    async def embed(
        self,
        texts: list[str],
        model: str,
        **kwargs,
    ) -> EmbeddingResponse:
        """Generate embeddings via OpenAI."""
        model_name = self._resolve_model_name(model)

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
        documents: list[str],
        model: str,
        top_n: int | None = None,
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

        model_name = self._resolve_model_name(model)

        # Use embedding model (default to text-embedding-ada-002 if not specified)
        embedding_model = self._resolve_model_name(kwargs.get("embedding_model", "text-embedding-ada-002"))

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
        for i, (doc, score) in enumerate(zip(documents, similarities, strict=False)):
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

    @staticmethod
    def _token_limit_param(model_name: str) -> str:
        """Map token-limit param based on model family."""
        normalized = model_name.lower()
        if normalized.startswith(("gpt-5", "o1", "o3", "o4")):
            return "max_completion_tokens"
        return "max_tokens"

    @staticmethod
    def _resolve_model_name(model: str) -> str:
        """Resolve provider-qualified model refs to provider-native model ids."""
        if model.startswith("model:"):
            parts = model.split(":")
            if len(parts) >= 3:
                return ":".join(parts[2:])
        if model.startswith("openai:"):
            return model.split(":", 1)[1]
        return model

    @staticmethod
    def _supports_reasoning_effort(model_name: str) -> bool:
        """Whether model supports reasoning_effort param."""
        normalized = model_name.lower()
        return normalized.startswith(("gpt-5", "o1", "o3", "o4"))

    @staticmethod
    def _resolve_temperature_param(
        model_name: str,
        temperature: float | None,
    ) -> float | None:
        """Normalize temperature by model capabilities."""
        if temperature is None:
            return None
        normalized = model_name.lower()
        # Some reasoning-focused models only accept the default temperature.
        if normalized.startswith(("gpt-5", "o1", "o3", "o4")):
            return 1.0 if abs(temperature - 1.0) < 1e-9 else None
        return temperature
