"""providers

External provider catalog adapters.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.adapters.http.governed_client import governed_httpx_client
from app.adapters.llm.ollama import (
    OLLAMA_PLACEHOLDER_KEY,
    ollama_openai_base_url,
    ollama_root_url,
)
from app.kernel.contracts.context import RequestContext
from app.kernel.security.egress import GovernedEgressGuard

ANTHROPIC_API_VERSION = "2023-06-01"
ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com"
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
OLLAMA_SHOW_CONCURRENCY = 4
"""How many ``/api/show`` lookups a catalog refresh runs at once."""
OLLAMA_EMBEDDING_FAMILIES = frozenset({"bert", "nomic-bert"})
"""Families that only embed, for servers too old to report capabilities."""

ANTHROPIC_LATEST_MODEL_METADATA: dict[str, dict[str, Any]] = {
    "claude-opus-4-8": {
        "display_name": "Claude Opus 4.8",
        "context_window": 1_000_000,
        "max_output_tokens": 128_000,
        "generation": "4.8",
        "pricing_json": {
            "currency": "USD",
            "unit": "mtok",
            "input": 5.0,
            "output": 25.0,
        },
    },
    "claude-sonnet-4-6": {
        "display_name": "Claude Sonnet 4.6",
        "context_window": 1_000_000,
        "max_output_tokens": 64_000,
        "generation": "4.6",
        "pricing_json": {
            "currency": "USD",
            "unit": "mtok",
            "input": 3.0,
            "output": 15.0,
        },
    },
    "claude-haiku-4-5-20251001": {
        "display_name": "Claude Haiku 4.5",
        "context_window": 200_000,
        "max_output_tokens": 64_000,
        "generation": "4.5",
        "pricing_json": {
            "currency": "USD",
            "unit": "mtok",
            "input": 1.0,
            "output": 5.0,
        },
    },
}


class ProviderCatalogAdapter:
    """Adapter for fetching provider model catalogs and performing tests."""

    def __init__(self, egress_guard: GovernedEgressGuard | None = None) -> None:
        self.egress_guard = egress_guard or GovernedEgressGuard()

    @asynccontextmanager
    async def _http_client(
        self,
        ctx: RequestContext,
        resource_ref: str,
    ) -> AsyncIterator[httpx.AsyncClient]:
        async with governed_httpx_client(
            ctx=ctx,
            resource_ref=resource_ref,
            egress_guard=self.egress_guard,
            timeout=30.0,
        ) as client:
            yield client

    @asynccontextmanager
    async def _openai_client(
        self,
        *,
        ctx: RequestContext,
        api_key: str,
        base_url: str | None,
        resource_ref: str,
    ) -> AsyncIterator[AsyncOpenAI]:
        await self.egress_guard.authorize(
            ctx,
            resource_ref,
            base_url or OPENAI_DEFAULT_BASE_URL,
        )
        async with governed_httpx_client(
            ctx=ctx,
            resource_ref=resource_ref,
            egress_guard=self.egress_guard,
            timeout=30.0,
        ) as http_client:
            yield AsyncOpenAI(
                api_key=api_key,
                base_url=base_url or OPENAI_DEFAULT_BASE_URL,
                http_client=http_client,
            )

    @staticmethod
    def _provider_url(base_url: str | None, default_base_url: str, path: str) -> str:
        return f"{(base_url or default_base_url).rstrip('/')}{path}"

    @staticmethod
    def _anthropic_capabilities() -> dict[str, Any]:
        return {
            "model_type": "multimodal",
            "capabilities": ["chat", "vision"],
            "modalities": {
                "input": ["text", "image"],
                "output": ["text"],
            },
            "chat_supported": True,
            "vision_supported": True,
            "embeddings_supported": False,
        }

    @classmethod
    def _enrich_anthropic_model(cls, item: dict[str, Any]) -> dict[str, Any]:
        model_id = item.get("id")
        latest = ANTHROPIC_LATEST_MODEL_METADATA.get(str(model_id), {})
        display_name = item.get("display_name") or latest.get("display_name") or model_id
        capabilities_json = item.get("capabilities_json") or cls._anthropic_capabilities()
        context_window = item.get("context_window") or item.get("max_input_tokens") or latest.get("context_window")
        max_output_tokens = (
            item.get("max_output_tokens")
            or item.get("max_tokens")
            or latest.get("max_output_tokens")
        )
        generation = latest.get("generation")
        modelhub_meta = {
            "architecture_json": {
                "family": "claude",
                "provider": "anthropic",
                **({"generation": generation} if generation else {}),
            },
            "capability_matrix_json": {
                "chat": {
                    "catalog": True,
                    "diagnostics": None,
                    "runtime": None,
                    "merged": True,
                    "user_override": "auto",
                },
                "vision": {
                    "catalog": True,
                    "diagnostics": None,
                    "runtime": None,
                    "merged": True,
                    "user_override": "auto",
                },
                "embeddings": {
                    "catalog": False,
                    "diagnostics": None,
                    "runtime": None,
                    "merged": False,
                    "user_override": "auto",
                },
                "tool_calling": {
                    "catalog": False,
                    "diagnostics": None,
                    "runtime": None,
                    "merged": False,
                    "user_override": "auto",
                },
            },
            "parameter_config_json": {
                "defaults": {"max_tokens": min(max_output_tokens or 1024, 1024)},
                "limits": {
                    "context_window": context_window,
                    "max_output_tokens": max_output_tokens,
                },
            },
            "pricing_json": latest.get("pricing_json"),
            "diagnostics_json": {
                "test_chat_supported": True,
                "test_embeddings_supported": False,
            },
        }
        raw_meta = {**item, "modelhub": modelhub_meta}
        return {
            "model_id": model_id,
            "display_name": display_name,
            "capabilities_json": capabilities_json,
            "context_window": context_window,
            "max_output_tokens": max_output_tokens,
            "lifecycle_status": item.get("lifecycle_status") or item.get("status") or "stable",
            "raw_meta": raw_meta,
        }

    @staticmethod
    def _ollama_headers(api_key: str | None) -> dict[str, str]:
        # A bare Ollama needs no key; one behind an authenticating proxy does.
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}

    @staticmethod
    def _ollama_context_length(model_info: dict[str, Any]) -> int | None:
        # Keyed by architecture: "llama.context_length", "qwen3.context_length".
        for key, value in model_info.items():
            if key.endswith(".context_length") and isinstance(value, int) and value > 0:
                return value
        return None

    @classmethod
    def _ollama_model(cls, tag: dict[str, Any], show: dict[str, Any] | None) -> dict[str, Any]:
        """One catalog entry from ``/api/tags`` and, when it answered, ``/api/show``."""
        model_id = str(tag.get("model") or tag.get("name"))
        details = {**(tag.get("details") or {}), **((show or {}).get("details") or {})}
        reported = [str(item) for item in (show or {}).get("capabilities") or []]
        if reported:
            capabilities = reported
        else:
            families = {str(item).lower() for item in details.get("families") or []}
            families.add(str(details.get("family") or "").lower())
            capabilities = (
                ["embedding"] if families & OLLAMA_EMBEDDING_FAMILIES else ["completion"]
            )
        chat = "completion" in capabilities
        embeddings = "embedding" in capabilities
        tools = "tools" in capabilities
        vision = "vision" in capabilities
        context_window = cls._ollama_context_length((show or {}).get("model_info") or {})

        def entry(supported: bool) -> dict[str, Any]:
            return {
                "catalog": supported,
                "diagnostics": None,
                "runtime": None,
                "merged": supported,
                "user_override": "auto",
            }

        modelhub_meta = {
            "architecture_json": {
                "provider": "ollama",
                "family": details.get("family"),
                "parameter_size": details.get("parameter_size"),
                "quantization_level": details.get("quantization_level"),
            },
            "capability_matrix_json": {
                "chat": entry(chat),
                "embeddings": entry(embeddings),
                "tools": entry(tools),
                "vision": entry(vision),
            },
            "parameter_config_json": {"limits": {"context_window": context_window}},
            # Local models carry no price; their calls record usage, not spend.
            "pricing_json": None,
            "diagnostics_json": {
                "test_chat_supported": chat,
                "test_embeddings_supported": embeddings,
            },
        }
        return {
            "model_id": model_id,
            "display_name": model_id,
            "capabilities_json": {
                "model_type": (
                    "embedding" if embeddings and not chat else "multimodal" if vision else "llm"
                ),
                "capabilities": [
                    name
                    for name, supported in (
                        ("chat", chat),
                        ("embedding", embeddings),
                        ("tools", tools),
                        ("vision", vision),
                    )
                    if supported
                ],
                "chat_supported": chat,
                "embeddings_supported": embeddings,
                "vision_supported": vision,
                "tools_supported": tools,
            },
            "context_window": context_window,
            "max_output_tokens": None,
            "lifecycle_status": "stable",
            # The tag without the show payload: that carries the modelfile and
            # licence text, which the catalog has no use for.
            "raw_meta": {**tag, "capabilities": reported or None, "modelhub": modelhub_meta},
        }

    async def _list_ollama_models(
        self,
        *,
        ctx: RequestContext,
        api_key: str | None,
        base_url: str | None,
    ) -> list[dict[str, Any]]:
        root = ollama_root_url(base_url)
        headers = self._ollama_headers(api_key)
        async with self._http_client(ctx, "model-provider:ollama:catalog") as client:
            response = await client.get(f"{root}/api/tags", headers=headers)
            response.raise_for_status()
            tags = [
                item
                for item in (response.json().get("models") or [])
                if isinstance(item, dict) and (item.get("model") or item.get("name"))
            ]
            gate = asyncio.Semaphore(OLLAMA_SHOW_CONCURRENCY)

            async def show(tag: dict[str, Any]) -> dict[str, Any] | None:
                async with gate:
                    try:
                        detail = await client.post(
                            f"{root}/api/show",
                            headers=headers,
                            json={"model": tag.get("model") or tag.get("name")},
                        )
                        detail.raise_for_status()
                        payload = detail.json()
                    except (httpx.HTTPError, ValueError):
                        # A model that cannot be described still lists.
                        return None
                return payload if isinstance(payload, dict) else None

            shows = await asyncio.gather(*(show(tag) for tag in tags))
        return [self._ollama_model(tag, detail) for tag, detail in zip(tags, shows, strict=True)]

    @staticmethod
    def _extract_anthropic_text(payload: dict[str, Any]) -> str:
        contents = payload.get("content", []) or []
        parts: list[str] = []
        for item in contents:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_gemini_text(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates", []) or []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content") or {}
            parts = content.get("parts", []) or []
            texts: list[str] = []
            for part in parts:
                if isinstance(part, dict) and part.get("text"):
                    texts.append(str(part["text"]))
            if texts:
                return "\n".join(texts).strip()
        return ""

    async def list_models(
        self,
        *,
        ctx: RequestContext,
        provider_kind: str,
        api_key: str | None,
        base_url: str | None = None,
    ) -> list[dict[str, Any]]:
        """List models for a provider kind."""
        if provider_kind == "ollama":
            return await self._list_ollama_models(ctx=ctx, api_key=api_key, base_url=base_url)
        if provider_kind in {"openai", "openai_compatible"}:
            async with self._openai_client(
                ctx=ctx,
                api_key=api_key,
                base_url=base_url,
                resource_ref=f"model-provider:{provider_kind}:catalog",
            ) as client:
                response = await client.models.list()
            return [
                {
                    "model_id": item.id,
                    "display_name": getattr(item, "id", None),
                    "raw_meta": item.model_dump() if hasattr(item, "model_dump") else item.__dict__,
                }
                for item in response.data
            ]
        if provider_kind == "anthropic":
            headers = {
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
            }
            async with self._http_client(
                ctx,
                "model-provider:anthropic:catalog",
            ) as client:
                response = await client.get(
                    self._provider_url(base_url, ANTHROPIC_DEFAULT_BASE_URL, "/v1/models?limit=200"),
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
            items = payload.get("data", []) or []
            return [
                self._enrich_anthropic_model(item)
                for item in items
                if item.get("id")
            ]
        if provider_kind == "gemini":
            params = {"key": api_key}
            async with self._http_client(
                ctx,
                "model-provider:gemini:catalog",
            ) as client:
                response = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    params=params,
                )
                response.raise_for_status()
                payload = response.json()
            items = payload.get("models", []) or []
            results: list[dict[str, Any]] = []
            for item in items:
                name = item.get("name") or ""
                model_id = name.split("/")[-1] if "/" in name else name
                if not model_id:
                    continue
                results.append(
                    {
                        "model_id": model_id,
                        "display_name": item.get("displayName") or model_id,
                        "raw_meta": item,
                    }
                )
            return results
        raise ValueError(f"Unsupported provider kind: {provider_kind}")

    async def healthcheck(
        self,
        *,
        ctx: RequestContext,
        provider_kind: str,
        api_key: str | None,
        base_url: str | None = None,
    ) -> None:
        """Perform a lightweight healthcheck."""
        if provider_kind == "ollama":
            # The version probe answers without loading or listing any model.
            async with self._http_client(ctx, "model-provider:ollama:health") as client:
                response = await client.get(
                    f"{ollama_root_url(base_url)}/api/version",
                    headers=self._ollama_headers(api_key),
                )
                response.raise_for_status()
            return
        await self.list_models(
            ctx=ctx,
            provider_kind=provider_kind,
            api_key=api_key,
            base_url=base_url,
        )

    async def test_chat(
        self,
        *,
        ctx: RequestContext,
        provider_kind: str,
        api_key: str | None,
        base_url: str | None,
        model_id: str,
        input_text: str,
    ) -> dict[str, Any]:
        """Run a lightweight chat completion test."""
        if provider_kind == "ollama":
            api_key = api_key or OLLAMA_PLACEHOLDER_KEY
            base_url = ollama_openai_base_url(base_url)
        if provider_kind in {"openai", "openai_compatible", "ollama"}:
            token_limit_param = (
                "max_completion_tokens"
                if model_id.lower().startswith(("gpt-5", "o1", "o3", "o4"))
                else "max_tokens"
            )
            async with self._openai_client(
                ctx=ctx,
                api_key=api_key,
                base_url=base_url,
                resource_ref=f"model-provider:{provider_kind}:chat-test",
            ) as client:
                response = await client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": input_text}],
                    **{token_limit_param: 32},
                )
            choice = response.choices[0]
            return {
                "response": choice.message.content or "",
                "tokens_prompt": response.usage.prompt_tokens if response.usage else None,
                "tokens_completion": response.usage.completion_tokens if response.usage else None,
                "request_id": getattr(response, "id", None),
            }

        if provider_kind == "anthropic":
            headers = {
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
                "content-type": "application/json",
            }
            payload = {
                "model": model_id,
                "max_tokens": 64,
                "messages": [{"role": "user", "content": input_text}],
            }
            async with self._http_client(
                ctx,
                "model-provider:anthropic:chat-test",
            ) as client:
                response = await client.post(
                    self._provider_url(base_url, ANTHROPIC_DEFAULT_BASE_URL, "/v1/messages"),
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
            usage = body.get("usage") or {}
            return {
                "response": self._extract_anthropic_text(body),
                "tokens_prompt": usage.get("input_tokens"),
                "tokens_completion": usage.get("output_tokens"),
                "request_id": body.get("id"),
            }

        if provider_kind == "gemini":
            endpoint = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_id}:generateContent"
            )
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": input_text}],
                    }
                ],
                "generationConfig": {"maxOutputTokens": 64},
            }
            async with self._http_client(
                ctx,
                "model-provider:gemini:chat-test",
            ) as client:
                response = await client.post(
                    endpoint,
                    params={"key": api_key},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
            usage = body.get("usageMetadata") or {}
            return {
                "response": self._extract_gemini_text(body),
                "tokens_prompt": usage.get("promptTokenCount"),
                "tokens_completion": usage.get("candidatesTokenCount"),
                "request_id": body.get("responseId"),
            }

        raise ValueError(f"Chat test not supported for provider: {provider_kind}")

    async def test_embeddings(
        self,
        *,
        ctx: RequestContext,
        provider_kind: str,
        api_key: str | None,
        base_url: str | None,
        model_id: str,
        input_text: str,
    ) -> dict[str, Any]:
        """Run a lightweight embeddings test."""
        if provider_kind not in {"openai", "openai_compatible", "ollama"}:
            raise ValueError(f"Embedding test not supported for provider: {provider_kind}")
        if provider_kind == "ollama":
            api_key = api_key or OLLAMA_PLACEHOLDER_KEY
            base_url = ollama_openai_base_url(base_url)
        async with self._openai_client(
            ctx=ctx,
            api_key=api_key,
            base_url=base_url,
            resource_ref=f"model-provider:{provider_kind}:embedding-test",
        ) as client:
            response = await client.embeddings.create(model=model_id, input=input_text)
        return {
            "response": "ok",
            "tokens_prompt": response.usage.total_tokens if response.usage else None,
            "tokens_completion": None,
            "request_id": getattr(response, "id", None),
        }
