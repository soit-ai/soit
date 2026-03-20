"""providers

External provider catalog adapters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from openai import AsyncOpenAI


class ProviderCatalogAdapter:
    """Adapter for fetching provider model catalogs and performing tests."""

    @staticmethod
    def _extract_anthropic_text(payload: Dict[str, Any]) -> str:
        contents = payload.get("content", []) or []
        parts: List[str] = []
        for item in contents:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_gemini_text(payload: Dict[str, Any]) -> str:
        candidates = payload.get("candidates", []) or []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content") or {}
            parts = content.get("parts", []) or []
            texts: List[str] = []
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
        base_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List models for a provider kind."""
        if provider_kind in {"openai", "openai_compat"}:
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
                "anthropic-version": "2023-06-01",
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get("https://api.anthropic.com/v1/models?limit=200", headers=headers)
                response.raise_for_status()
                payload = response.json()
            items = payload.get("data", []) or []
            return [
                {
                    "model_id": item.get("id"),
                    "display_name": item.get("display_name") or item.get("id"),
                    "raw_meta": item,
                }
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
            results: List[Dict[str, Any]] = []
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
        base_url: Optional[str] = None,
    ) -> None:
        """Perform a lightweight healthcheck."""
        await self.list_models(provider_kind=provider_kind, api_key=api_key, base_url=base_url)

    async def test_chat(
        self,
        *,
        provider_kind: str,
        api_key: str,
        base_url: Optional[str],
        model_id: str,
        input_text: str,
    ) -> Dict[str, Any]:
        """Run a lightweight chat completion test."""
        if provider_kind in {"openai", "openai_compat"}:
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
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": model_id,
                "max_tokens": 64,
                "messages": [{"role": "user", "content": input_text}],
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
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
        base_url: Optional[str],
        model_id: str,
        input_text: str,
    ) -> Dict[str, Any]:
        """Run a lightweight embeddings test."""
        if provider_kind not in {"openai", "openai_compat"}:
            raise ValueError(f"Embedding test not supported for provider: {provider_kind}")
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.embeddings.create(model=model_id, input=input_text)
        return {
            "response": "ok",
            "tokens_prompt": response.usage.total_tokens if response.usage else None,
            "tokens_completion": None,
            "request_id": getattr(response, "id", None),
        }
