"""Tests for the workspace LLM provider resolver cache."""

from types import SimpleNamespace

import pytest

from app.adapters.llm.provider_resolver import DatabaseProviderResolver


class _FakeRedis:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}

    async def get(self, key: str):
        if self.fail:
            raise ConnectionError("redis unavailable")
        return self.values.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        if self.fail:
            raise ConnectionError("redis unavailable")
        self.values[key] = value
        self.expirations[key] = ttl

    async def delete(self, key: str):
        if self.fail:
            raise ConnectionError("redis unavailable")
        self.values.pop(key, None)


@pytest.mark.asyncio
async def test_provider_resolver_caches_config_and_invalidation_refreshes(monkeypatch, ctx):
    state = {
        "provider": SimpleNamespace(
            id="provider-1",
            slug="team-gateway",
            kind="openai_compatible",
            adapter_backend="litellm",
            status="active",
            base_url="https://old.example.com/v1",
            credential_ref="secret:team-gateway",
            connection_config_json={
                "timeout_ms": 45000,
                "retry_policy": {"max_retries": 2, "backoff": "none"},
            },
        ),
        "queries": 0,
    }

    class _Database:
        def close(self):
            return None

    class _Repository:
        def __init__(self, db, request_ctx):
            assert request_ctx is ctx

        def get_by_slug(self, slug):
            assert slug == "team-gateway"
            state["queries"] += 1
            return state["provider"]

    monkeypatch.setattr("app.adapters.llm.provider_resolver.get_db_sync", _Database)
    monkeypatch.setattr("app.adapters.llm.provider_resolver.ProviderRepository", _Repository)
    cache = _FakeRedis()
    resolver = DatabaseProviderResolver(redis_client=cache, cache_ttl_seconds=30)

    first = await resolver(ctx, "team-gateway")
    state["provider"].base_url = "https://new.example.com/v1"
    cached = await resolver(ctx, "team-gateway")

    assert first is not None
    assert first.provider_id == "provider-1"
    assert first.timeout == 45.0
    assert first.max_retries == 2
    assert cached is not None
    assert cached.base_url == "https://old.example.com/v1"
    assert state["queries"] == 1
    assert "resolved-secret" not in next(iter(cache.values.values()))

    await resolver.invalidate(ctx, "team-gateway")
    refreshed = await resolver(ctx, "team-gateway")

    assert refreshed is not None
    assert refreshed.base_url == "https://new.example.com/v1"
    assert state["queries"] == 2


@pytest.mark.asyncio
async def test_provider_resolver_negative_caches_missing_provider(monkeypatch, ctx):
    queries = 0

    class _Database:
        def close(self):
            return None

    class _Repository:
        def __init__(self, db, request_ctx):
            pass

        def get_by_slug(self, slug):
            nonlocal queries
            queries += 1
            return None

    monkeypatch.setattr("app.adapters.llm.provider_resolver.get_db_sync", _Database)
    monkeypatch.setattr("app.adapters.llm.provider_resolver.ProviderRepository", _Repository)
    cache = _FakeRedis()
    resolver = DatabaseProviderResolver(redis_client=cache, negative_cache_ttl_seconds=5)

    assert await resolver(ctx, "missing") is None
    assert await resolver(ctx, "missing") is None
    assert queries == 1
    assert next(iter(cache.expirations.values())) == 5


@pytest.mark.asyncio
async def test_provider_resolver_falls_back_to_database_when_redis_fails(monkeypatch, ctx):
    provider = SimpleNamespace(
        id="provider-1",
        slug="team-gateway",
        kind="openai_compatible",
        adapter_backend="litellm",
        status="active",
        base_url=None,
        credential_ref=None,
        connection_config_json=None,
    )

    class _Database:
        def close(self):
            return None

    class _Repository:
        def __init__(self, db, request_ctx):
            pass

        def get_by_slug(self, slug):
            return provider

    monkeypatch.setattr("app.adapters.llm.provider_resolver.get_db_sync", _Database)
    monkeypatch.setattr("app.adapters.llm.provider_resolver.ProviderRepository", _Repository)
    resolver = DatabaseProviderResolver(redis_client=_FakeRedis(fail=True))

    resolved = await resolver(ctx, "team-gateway")

    assert resolved is not None
    assert resolved.slug == "team-gateway"
