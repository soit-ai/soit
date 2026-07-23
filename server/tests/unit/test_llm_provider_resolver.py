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


def _provider_model(**overrides):
    values = {
        "id": "provider-model-1",
        "provider_id": "provider-1",
        "model_id": "gpt-4.1-mini",
        "status": "active",
        "sync_status": "in_sync",
        "capability_matrix_json": {"chat": {"merged": True}},
        "pricing_json": {
            "currency": "USD",
            "unit": "mtok",
            "input": 0.4,
            "output": 1.6,
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


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
            credential_secret_id="sec_team-gateway",
            connection_config_json={
                "timeout_ms": 45000,
                "retry_policy": {"max_retries": 2, "backoff": "none"},
            },
            runtime_config_json=None,
            auth_config_json=None,
        ),
        "model": _provider_model(),
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

    class _ModelRepository:
        def __init__(self, db, request_ctx):
            assert request_ctx is ctx

        def get_by_provider_and_model_id(self, provider_id, model_id):
            assert provider_id == "provider-1"
            assert model_id == "gpt-4.1-mini"
            return state["model"]

    monkeypatch.setattr("app.adapters.llm.provider_resolver.get_db_sync", _Database)
    monkeypatch.setattr("app.adapters.llm.provider_resolver.ProviderRepository", _Repository)
    monkeypatch.setattr(
        "app.adapters.llm.provider_resolver.ProviderModelRepository",
        _ModelRepository,
    )
    cache = _FakeRedis()
    resolver = DatabaseProviderResolver(redis_client=cache, cache_ttl_seconds=30)

    first = await resolver(ctx, "team-gateway", "gpt-4.1-mini")
    state["provider"].base_url = "https://new.example.com/v1"
    cached = await resolver(ctx, "team-gateway", "gpt-4.1-mini")

    assert first is not None
    assert first.provider_id == "provider-1"
    assert first.timeout == 45.0
    assert first.max_retries == 2
    assert first.provider_model_id == "provider-model-1"
    assert first.model_id == "gpt-4.1-mini"
    assert first.model_status == "active"
    assert first.capability_matrix["chat"]["merged"] is True
    assert first.pricing["currency"] == "USD"
    assert cached is not None
    assert cached.base_url == "https://old.example.com/v1"
    assert state["queries"] == 1
    assert "resolved-secret" not in next(iter(cache.values.values()))

    assert "gpt-4.1-mini" in next(iter(cache.values))

    await resolver.invalidate(ctx, "team-gateway", "gpt-4.1-mini")
    refreshed = await resolver(ctx, "team-gateway", "gpt-4.1-mini")

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

    class _ModelRepository:
        def __init__(self, db, request_ctx):
            pass

    monkeypatch.setattr("app.adapters.llm.provider_resolver.get_db_sync", _Database)
    monkeypatch.setattr("app.adapters.llm.provider_resolver.ProviderRepository", _Repository)
    monkeypatch.setattr(
        "app.adapters.llm.provider_resolver.ProviderModelRepository",
        _ModelRepository,
    )
    cache = _FakeRedis()
    resolver = DatabaseProviderResolver(redis_client=cache, negative_cache_ttl_seconds=5)

    assert await resolver(ctx, "missing", "missing-model") is None
    assert await resolver(ctx, "missing", "missing-model") is None
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
        credential_secret_id=None,
        connection_config_json=None,
        runtime_config_json=None,
        auth_config_json=None,
    )

    class _Database:
        def close(self):
            return None

    class _Repository:
        def __init__(self, db, request_ctx):
            pass

        def get_by_slug(self, slug):
            return provider

    class _ModelRepository:
        def __init__(self, db, request_ctx):
            pass

        def get_by_provider_and_model_id(self, provider_id, model_id):
            return _provider_model()

    monkeypatch.setattr("app.adapters.llm.provider_resolver.get_db_sync", _Database)
    monkeypatch.setattr("app.adapters.llm.provider_resolver.ProviderRepository", _Repository)
    monkeypatch.setattr(
        "app.adapters.llm.provider_resolver.ProviderModelRepository",
        _ModelRepository,
    )
    resolver = DatabaseProviderResolver(redis_client=_FakeRedis(fail=True))

    resolved = await resolver(ctx, "team-gateway", "gpt-4.1-mini")

    assert resolved is not None
    assert resolved.slug == "team-gateway"
