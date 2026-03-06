"""providers

External provider catalog adapters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from openai import AsyncOpenAI


class ProviderCatalogAdapter:
    """Adapter for fetching provider model catalogs and performing tests."""

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
        if provider_kind not in {"openai", "openai_compat"}:
            raise ValueError(f"Chat test not supported for provider: {provider_kind}")
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
