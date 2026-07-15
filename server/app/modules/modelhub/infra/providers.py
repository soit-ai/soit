"""providers

External provider catalog adapters.
"""

from __future__ import annotations

from typing import Any

import httpx
from openai import AsyncOpenAI

ANTHROPIC_API_VERSION = "2023-06-01"
ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com"

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
                "chat": True,
                "vision": True,
                "embeddings": False,
                "tool_calling": False,
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
        provider_kind: str,
        api_key: str,
        base_url: str | None = None,
    ) -> list[dict[str, Any]]:
        """List models for a provider kind."""
        if provider_kind in {"openai", "openai_compat", "openai_compatible"}:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
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
            async with httpx.AsyncClient(timeout=30.0) as client:
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
            async with httpx.AsyncClient(timeout=30.0) as client:
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
        provider_kind: str,
        api_key: str,
        base_url: str | None = None,
    ) -> None:
        """Perform a lightweight healthcheck."""
        await self.list_models(provider_kind=provider_kind, api_key=api_key, base_url=base_url)

    async def test_chat(
        self,
        *,
        provider_kind: str,
        api_key: str,
        base_url: str | None,
        model_id: str,
        input_text: str,
    ) -> dict[str, Any]:
        """Run a lightweight chat completion test."""
        if provider_kind in {"openai", "openai_compat", "openai_compatible"}:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            token_limit_param = (
                "max_completion_tokens"
                if model_id.lower().startswith(("gpt-5", "o1", "o3", "o4"))
                else "max_tokens"
            )
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
            async with httpx.AsyncClient(timeout=30.0) as client:
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
            async with httpx.AsyncClient(timeout=30.0) as client:
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
        provider_kind: str,
        api_key: str,
        base_url: str | None,
        model_id: str,
        input_text: str,
    ) -> dict[str, Any]:
        """Run a lightweight embeddings test."""
        if provider_kind not in {"openai", "openai_compat", "openai_compatible"}:
            raise ValueError(f"Embedding test not supported for provider: {provider_kind}")
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.embeddings.create(model=model_id, input=input_text)
        return {
            "response": "ok",
            "tokens_prompt": response.usage.total_tokens if response.usage else None,
            "tokens_completion": None,
            "request_id": getattr(response, "id", None),
        }
