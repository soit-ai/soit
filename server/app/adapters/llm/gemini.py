"""Gemini LLM port adapter, over the Gemini API's REST endpoints.

Chat goes to ``models/{model}:generateContent`` (``:streamGenerateContent``
with server-sent events for streams), embeddings to ``:batchEmbedContents``.
Tools are declared with their JSON Schema as it is
(``parametersJsonSchema``), and structured output likewise
(``responseJsonSchema``), so SOIT does not translate schemas into Gemini's
OpenAPI subset.

Gemini's thinking models sign each function call they make, and expect the
signature back with the call when the conversation continues. The adapter
keeps the signatures of the calls it received for a while, keyed by call id,
and sends each back with its call; a call whose signature it no longer has
(another process answered it, or the history came from elsewhere) is sent
with the placeholder Google documents for replayed history.

Images go inline, from ``data:`` URLs; Gemini does not fetch a web URL, so
one is refused. Gemini reports no token count for embeddings, so an
embedding call is counted at four characters a token.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import uuid4

import httpx

from app.adapters.llm.tool_names import tool_name_alias, tool_name_maps
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.interface import (
    ChatImage,
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

GEMINI_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"
GEMINI_API_VERSION = "v1beta"
REPLAYED_SIGNATURE = "skip_thought_signature_validator"
"""What Google documents to send for a function call whose signature is not at hand."""

_CONNECT_TIMEOUT_SECONDS = 10.0
_CHARACTERS_PER_TOKEN = 4
_SIGNATURES_KEPT = 4096

_FINISH_REASONS = {
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "content_filter",
    "RECITATION": "content_filter",
    "BLOCKLIST": "content_filter",
    "PROHIBITED_CONTENT": "content_filter",
    "SPII": "content_filter",
    "IMAGE_SAFETY": "content_filter",
}

# Signatures of the function calls this process received, by call id.
_signatures: OrderedDict[str, str] = OrderedDict()


def _remember_signature(call_id: str, signature: str | None) -> None:
    if not signature:
        return
    _signatures[call_id] = signature
    _signatures.move_to_end(call_id)
    while len(_signatures) > _SIGNATURES_KEPT:
        _signatures.popitem(last=False)


def _gemini_name(alias: str) -> str:
    # Gemini wants a function name to start with a letter or an underscore.
    return alias if alias[:1].isalpha() or alias[:1] == "_" else f"_{alias}"[:64]


def _finish_reason(raw: str | None, *, called_tools: bool) -> str | None:
    if raw is None:
        return "tool_calls" if called_tools else None
    if called_tools and raw == "STOP":
        return "tool_calls"
    return _FINISH_REASONS.get(raw, raw.lower())


def _usage(payload: dict[str, Any]) -> tuple[int, int]:
    """Input and output tokens; thinking is output the call is charged for."""
    usage: dict[str, Any] = payload.get("usageMetadata") or {}
    prompt = int(usage.get("promptTokenCount") or 0) + int(usage.get("toolUsePromptTokenCount") or 0)
    completion = int(usage.get("candidatesTokenCount") or 0) + int(usage.get("thoughtsTokenCount") or 0)
    return prompt, completion


def _image_part(image: ChatImage) -> dict[str, Any]:
    if not image.is_data_url:
        raise ValidationError(
            "Gemini takes images inline: send the image as a base64 data: URL, not a web address",
            {"param": "messages"},
        )
    header, _, data = image.url.partition(",")
    mime_type = header.removeprefix("data:").split(";")[0]
    if ";base64" not in header or not mime_type or not data:
        raise ValidationError("Image data URLs must be base64 encoded with a media type")
    return {"inlineData": {"mimeType": mime_type, "data": data}}


def _function_response(content: str | None) -> dict[str, Any]:
    """A tool result as the object Gemini's functionResponse carries."""
    try:
        parsed: Any = json.loads(content or "")
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed)
    return {"content": content or ""}


def _tool_config(tool_choice: Any, name_map: dict[str, str]) -> dict[str, Any] | None:
    if tool_choice is None:
        return None
    if isinstance(tool_choice, str):
        choice = tool_choice.strip().lower()
        if choice == "auto":
            return {"functionCallingConfig": {"mode": "AUTO"}}
        if choice in {"required", "any"}:
            return {"functionCallingConfig": {"mode": "ANY"}}
        if choice == "none":
            return {"functionCallingConfig": {"mode": "NONE"}}
        name = tool_choice
    elif isinstance(tool_choice, dict):
        choice_map = cast(dict[str, Any], tool_choice)
        function: Any = choice_map.get("function")
        name = (function.get("name") if isinstance(function, dict) else None) or choice_map.get("name")
        if not name:
            raise ValidationError("Unsupported tool_choice for Gemini")
    else:
        raise ValidationError("Unsupported tool_choice for Gemini")
    alias = _gemini_name(name_map.get(str(name), tool_name_alias(str(name))))
    return {"functionCallingConfig": {"mode": "ANY", "allowedFunctionNames": [alias]}}


class GeminiLLMPort(LLMPort):
    """Gemini API adapter for chat, streaming, tool calls and embeddings."""

    def __init__(self, api_key: str, base_url: str | None = None, timeout: float | None = None):
        self.api_key = api_key
        root = (base_url or GEMINI_DEFAULT_BASE_URL).rstrip("/")
        self.egress_base_url = root
        self.base_url = root if root.rsplit("/", 1)[-1] in {"v1", "v1beta", "v1alpha"} else f"{root}/{GEMINI_API_VERSION}"
        self.timeout = timeout

    def _http_timeout(self) -> httpx.Timeout:
        connect = min(self.timeout, _CONNECT_TIMEOUT_SECONDS) if self.timeout else _CONNECT_TIMEOUT_SECONDS
        return httpx.Timeout(self.timeout, connect=connect)

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self.api_key, "content-type": "application/json"}

    @staticmethod
    def _resolve_model_name(model: str) -> str:
        if model.startswith("model:"):
            parts = model.split(":")
            if len(parts) >= 3:
                model = ":".join(parts[2:])
        elif model.startswith("gemini:"):
            model = model.split(":", 1)[1]
        return model.removeprefix("models/")

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> ChatResponse:
        name_map, reverse_map = self._name_maps(tools)
        payload = self._payload(messages, temperature, max_tokens, tools, tool_choice, name_map, kwargs)
        model_name = self._resolve_model_name(model)
        async with httpx.AsyncClient(timeout=self._http_timeout()) as client:
            response = await client.post(
                f"{self.base_url}/models/{model_name}:generateContent",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        candidate = self._candidate(body)
        text, reasoning, calls = self._read_parts(candidate, reverse_map)
        prompt, completion = _usage(body)
        raw_finish = candidate.get("finishReason") if candidate else None
        if not candidate and (body.get("promptFeedback") or {}).get("blockReason"):
            raw_finish = "SAFETY"
        return ChatResponse(
            text=text,
            reasoning=reasoning,
            tokens_prompt=prompt,
            tokens_completion=completion,
            model=body.get("modelVersion") or model_name,
            finish_reason=_finish_reason(raw_finish, called_tools=bool(calls)),
            tool_calls=calls or None,
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatStreamChunk]:
        name_map, reverse_map = self._name_maps(tools)
        payload = self._payload(messages, temperature, max_tokens, tools, tool_choice, name_map, kwargs)
        model_name = self._resolve_model_name(model)
        prompt = completion = 0
        raw_finish: str | None = None
        calls: list[ToolCall] = []
        async with httpx.AsyncClient(timeout=self._http_timeout()) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/models/{model_name}:streamGenerateContent",
                params={"alt": "sse"},
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if not data:
                        continue
                    chunk = json.loads(data)
                    model_name = chunk.get("modelVersion") or model_name
                    if chunk.get("usageMetadata"):
                        prompt, completion = _usage(chunk)
                    if not chunk.get("candidates") and (chunk.get("promptFeedback") or {}).get("blockReason"):
                        raw_finish = "SAFETY"
                    candidate = self._candidate(chunk)
                    if not candidate:
                        continue
                    raw_finish = candidate.get("finishReason") or raw_finish
                    text, reasoning, new_calls = self._read_parts(candidate, reverse_map)
                    if reasoning:
                        yield ChatStreamChunk(reasoning_delta=reasoning, model=model_name)
                    if text:
                        yield ChatStreamChunk(delta=text, model=model_name)
                    if new_calls:
                        # Gemini sends a function call whole, never in pieces.
                        deltas = [
                            ToolCallDelta(
                                index=len(calls) + offset,
                                id=call.id,
                                name=call.name,
                                arguments_delta=json.dumps(call.arguments),
                            )
                            for offset, call in enumerate(new_calls)
                        ]
                        calls.extend(new_calls)
                        yield ChatStreamChunk(model=model_name, tool_call_deltas=deltas)
        yield ChatStreamChunk(
            delta="",
            done=True,
            tokens_prompt=prompt,
            tokens_completion=completion,
            model=model_name,
            finish_reason=_finish_reason(raw_finish, called_tools=bool(calls)),
            tool_calls=calls or None,
        )

    async def embed(self, texts: list[str], model: str, **kwargs: Any) -> EmbeddingResponse:
        model_name = self._resolve_model_name(model)
        request: dict[str, Any] = {"model": f"models/{model_name}"}
        dimensions = kwargs.get("dimensions")
        if dimensions:
            request["outputDimensionality"] = int(dimensions)
        payload = {"requests": [{**request, "content": {"parts": [{"text": text}]}} for text in texts]}
        async with httpx.AsyncClient(timeout=self._http_timeout()) as client:
            response = await client.post(
                f"{self.base_url}/models/{model_name}:batchEmbedContents",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        items: list[dict[str, Any]] = body.get("embeddings") or []
        embeddings: list[list[float]] = [[float(value) for value in item.get("values") or []] for item in items]
        if len(embeddings) != len(texts):
            raise ValidationError(f"Gemini returned {len(embeddings)} embeddings for {len(texts)} texts")
        tokens = sum(math.ceil(len(text) / _CHARACTERS_PER_TOKEN) for text in texts)
        return EmbeddingResponse(embeddings=embeddings, tokens_used=tokens, model=model_name)

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        raise ValidationError("Rerank is not supported for Gemini providers")

    @staticmethod
    def _name_maps(tools: list[ToolDefinition] | None) -> tuple[dict[str, str], dict[str, str]]:
        outbound, _ = tool_name_maps(tools)
        outbound = {name: _gemini_name(alias) for name, alias in outbound.items()}
        return outbound, {alias: name for name, alias in outbound.items()}

    def _payload(
        self,
        messages: list[ChatMessage],
        temperature: float | None,
        max_tokens: int | None,
        tools: list[ToolDefinition] | None,
        tool_choice: Any,
        name_map: dict[str, str],
        options: dict[str, Any],
    ) -> dict[str, Any]:
        system: list[str] = []
        contents: list[dict[str, Any]] = []
        call_names: dict[str, str] = {}
        for message in messages:
            if message.role == "system":
                if message.content:
                    system.append(str(message.content))
                continue
            if message.role == "tool":
                name = message.name or call_names.get(message.tool_call_id or "") or "tool"
                part: dict[str, Any] = {
                    "functionResponse": {
                        "name": _gemini_name(name_map.get(name, tool_name_alias(name))),
                        "response": _function_response(message.content),
                    }
                }
                if message.tool_call_id:
                    part["functionResponse"]["id"] = message.tool_call_id
                self._append(contents, "user", [part])
                continue
            if message.role not in {"user", "assistant"}:
                raise ValidationError(f"Gemini chat does not support message role: {message.role}")
            parts: list[dict[str, Any]] = []
            if message.content:
                parts.append({"text": str(message.content)})
            parts.extend(_image_part(image) for image in message.images)
            if message.role == "assistant":
                for call in message.tool_calls or []:
                    call_names[call.id] = call.name
                    parts.append(
                        {
                            "functionCall": {
                                "id": call.id,
                                "name": _gemini_name(name_map.get(call.name, tool_name_alias(call.name))),
                                "args": call.arguments or {},
                            },
                            "thoughtSignature": _signatures.get(call.id, REPLAYED_SIGNATURE),
                        }
                    )
            if not parts:
                parts = [{"text": ""}]
            self._append(contents, "model" if message.role == "assistant" else "user", parts)

        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system)}]}
        config: dict[str, Any] = {}
        if temperature is not None:
            config["temperature"] = temperature
        if max_tokens:
            config["maxOutputTokens"] = max_tokens
        if options.get("top_p") is not None:
            config["topP"] = options["top_p"]
        if options.get("seed") is not None:
            config["seed"] = options["seed"]
        stop = options.get("stop")
        if stop:
            config["stopSequences"] = [stop] if isinstance(stop, str) else list(stop)
        response_format = options.get("response_format")
        if isinstance(response_format, dict):
            format_spec = cast(dict[str, Any], response_format)
            if format_spec.get("type") in {"json_object", "json_schema"}:
                config["responseMimeType"] = "application/json"
            json_schema: Any = format_spec.get("json_schema")
            if isinstance(json_schema, dict) and isinstance(json_schema.get("schema"), dict):
                config["responseJsonSchema"] = json_schema["schema"]
        if config:
            payload["generationConfig"] = config
        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": name_map[tool.name],
                            "description": tool.description or "",
                            "parametersJsonSchema": tool.parameters or {"type": "object", "properties": {}},
                        }
                        for tool in tools
                    ]
                }
            ]
            tool_config = _tool_config(tool_choice, name_map)
            if tool_config is not None:
                payload["toolConfig"] = tool_config
        return payload

    @staticmethod
    def _append(contents: list[dict[str, Any]], role: str, parts: list[dict[str, Any]]) -> None:
        # Consecutive turns of one role merge: parallel tool results travel
        # together, as the calls they answer came together.
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].extend(parts)
            return
        contents.append({"role": role, "parts": list(parts)})

    @staticmethod
    def _candidate(payload: dict[str, Any]) -> dict[str, Any]:
        candidates: Any = payload.get("candidates") or []
        return cast(dict[str, Any], candidates[0]) if candidates else {}

    @staticmethod
    def _read_parts(
        candidate: dict[str, Any], reverse_map: dict[str, str]
    ) -> tuple[str, str | None, list[ToolCall]]:
        text: list[str] = []
        thoughts: list[str] = []
        calls: list[ToolCall] = []
        content: dict[str, Any] = candidate.get("content") or {}
        raw_parts: list[Any] = content.get("parts") or []
        for raw_part in raw_parts:
            if not isinstance(raw_part, dict):
                continue
            part = cast(dict[str, Any], raw_part)
            call = part.get("functionCall")
            if isinstance(call, dict):
                call_map = cast(dict[str, Any], call)
                call_id = str(call_map.get("id") or f"call_{uuid4().hex[:24]}")
                alias = str(call_map.get("name") or "")
                arguments: Any = call_map.get("args")
                _remember_signature(call_id, part.get("thoughtSignature"))
                calls.append(
                    ToolCall(
                        id=call_id,
                        name=reverse_map.get(alias, alias),
                        arguments=cast(dict[str, Any], arguments) if isinstance(arguments, dict) else {},
                    )
                )
                continue
            value = part.get("text")
            if not value:
                continue
            (thoughts if part.get("thought") else text).append(str(value))
        reasoning = "".join(thoughts).strip() or None
        return "".join(text), reasoning, calls
