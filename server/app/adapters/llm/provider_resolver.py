"""Database-backed workspace LLM provider resolver."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

import anyio
import redis.asyncio as redis_async

from app.adapters.llm.router import RuntimeProviderConfig
from app.infra.db.session import get_db_sync
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.runtime_config import resolve_litellm_runtime_config
from app.modules.modelhub.infra.repository import (
    ProviderModelRepository,
    ProviderRepository,
)
from app.settings.settings import settings

logger = logging.getLogger(__name__)


class DatabaseProviderResolver:
    """Resolve and briefly cache provider config for the current workspace."""

    CACHE_PREFIX = "soit:llm-provider:v2"

    def __init__(
        self,
        *,
        redis_client: Any | None = None,
        redis_url: str | None = None,
        cache_ttl_seconds: int = 30,
        negative_cache_ttl_seconds: int = 5,
    ) -> None:
        self.cache_ttl_seconds = cache_ttl_seconds
        self.negative_cache_ttl_seconds = negative_cache_ttl_seconds
        self._redis = redis_client or redis_async.from_url(
            redis_url or settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )

    @classmethod
    def _cache_key(cls, ctx: RequestContext, slug: str, model_id: str) -> str:
        return f"{cls.CACHE_PREFIX}:{ctx.tenant_id}:{ctx.workspace_id}:{slug}:{model_id}"

    @staticmethod
    def _config_from_provider(provider: Any, model: Any) -> RuntimeProviderConfig:
        connection = provider.connection_config_json or {}
        retry_policy = connection.get("retry_policy") or {}
        timeout_ms = connection.get("timeout_ms")
        litellm_config = None
        if provider.adapter_backend == "litellm":
            litellm_config = resolve_litellm_runtime_config(
                provider_kind=provider.kind,
                runtime_config=getattr(provider, "runtime_config_json", None),
                connection_config=connection,
                auth_config=getattr(provider, "auth_config_json", None),
                credential_secret_id=provider.credential_secret_id,
            )
        return RuntimeProviderConfig(
            provider_id=provider.id,
            slug=provider.slug or provider.kind,
            kind=provider.kind,
            adapter_backend=provider.adapter_backend,
            status=provider.status,
            base_url=provider.base_url,
            credential_secret_id=provider.credential_secret_id,
            timeout=float(timeout_ms) / 1000 if timeout_ms is not None else 60.0,
            max_retries=int(retry_policy.get("max_retries", 3)),
            retry_backoff=str(retry_policy.get("backoff", "exponential")),
            retryable_status_codes=tuple(
                int(code)
                for code in retry_policy.get(
                    "retryable_status_codes",
                    [408, 409, 429, 500, 502, 503, 504],
                )
            ),
            litellm_provider=litellm_config.provider if litellm_config else None,
            litellm_params=litellm_config.params if litellm_config else {},
            secret_bindings=litellm_config.secret_bindings if litellm_config else {},
            provider_model_id=model.id,
            model_id=model.model_id,
            model_status=model.status,
            model_sync_status=getattr(model, "sync_status", None),
            capability_matrix=getattr(model, "capability_matrix_json", None) or {},
            provider_capabilities=(
                (getattr(provider, "runtime_config_json", None) or {}).get("runtime_support")
                or {}
            ),
            pricing=getattr(model, "pricing_json", None) or {},
        )

    @classmethod
    def _resolve_from_database(
        cls,
        ctx: RequestContext,
        slug: str,
        model_id: str,
    ) -> RuntimeProviderConfig | None:
        db = get_db_sync()
        try:
            provider = ProviderRepository(db, ctx).get_by_slug(slug)
            if provider is None:
                return None
            model = ProviderModelRepository(db, ctx).get_by_provider_and_model_id(
                provider.id,
                model_id,
            )
            return cls._config_from_provider(provider, model) if model is not None else None
        finally:
            db.close()

    async def _read_cache(
        self,
        key: str,
    ) -> tuple[bool, RuntimeProviderConfig | None]:
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return False, None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            payload = json.loads(raw)
            if payload.get("missing") is True:
                return True, None
            config = payload.get("config")
            if not isinstance(config, dict):
                return False, None
            config["retryable_status_codes"] = tuple(
                config.get("retryable_status_codes") or ()
            )
            return True, RuntimeProviderConfig(**config)
        except Exception:
            logger.debug("llm.provider_cache.read_failed", exc_info=True)
            return False, None

    async def _write_cache(
        self,
        key: str,
        config: RuntimeProviderConfig | None,
    ) -> None:
        payload: dict[str, Any] = (
            {"missing": True}
            if config is None
            else {"config": asdict(config)}
        )
        ttl = self.negative_cache_ttl_seconds if config is None else self.cache_ttl_seconds
        try:
            await self._redis.setex(key, ttl, json.dumps(payload))
        except Exception:
            logger.debug("llm.provider_cache.write_failed", exc_info=True)

    async def __call__(
        self,
        ctx: RequestContext,
        slug: str,
        model_id: str,
    ) -> RuntimeProviderConfig | None:
        key = self._cache_key(ctx, slug, model_id)
        cache_hit, cached = await self._read_cache(key)
        if cache_hit:
            return cached
        config = await anyio.to_thread.run_sync(
            self._resolve_from_database,
            ctx,
            slug,
            model_id,
        )
        await self._write_cache(key, config)
        return config

    async def invalidate(
        self,
        ctx: RequestContext,
        slug: str,
        model_id: str | None = None,
    ) -> None:
        """Invalidate one model route or all cached routes for a provider."""
        try:
            if model_id is not None:
                await self._redis.delete(self._cache_key(ctx, slug, model_id))
                return
            prefix = f"{self.CACHE_PREFIX}:{ctx.tenant_id}:{ctx.workspace_id}:{slug}:*"
            scan_iter = getattr(self._redis, "scan_iter", None)
            if scan_iter is None:
                return
            keys = [key async for key in scan_iter(match=prefix)]
            if keys:
                await self._redis.delete(*keys)
        except Exception:
            logger.debug("llm.provider_cache.invalidate_failed", exc_info=True)
