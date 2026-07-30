"""Tests for production runtime configuration validation."""

import pytest

from app.settings.settings import Settings


def _production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "database_url": "postgresql://user:pass@db/soit",
        "redis_url": "redis://redis:6379/0",
        "secret_key": "s" * 32,
        "vault_url": "http://vault:8200",
        "vault_token": "vault-token",
        "openai_api_key": "provider-key",
        "event_bus_backend": "redis",
        "response_interaction_inline_execution": False,
        "response_interaction_worker_enabled": True,
        "otel_enabled": True,
        "otel_exporter_otlp_endpoint": "http://otel-collector:4318/v1/traces",
        "plugin_signature_required": True,
        "plugin_signature_public_keys": ["trusted-key"],
        "plugin_integrity_required": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_settings_accept_a_fully_configured_runtime() -> None:
    # The baseline every case below derives from must itself be valid, or a
    # single-field override could pass for the wrong reason.
    _production_settings().validate_runtime_requirements()


def test_production_settings_reject_memory_event_bus() -> None:
    config = _production_settings(event_bus_backend="memory")

    with pytest.raises(ValueError, match="Redis"):
        config.validate_runtime_requirements()


def test_production_settings_reject_in_process_outbox_dispatcher() -> None:
    config = _production_settings(outbox_dispatcher_enabled=True)

    with pytest.raises(ValueError, match="dedicated outbox dispatcher"):
        config.validate_runtime_requirements()


def test_production_settings_reject_inline_chat_execution() -> None:
    config = _production_settings(response_interaction_inline_execution=True)

    with pytest.raises(ValueError, match="inline chat interaction"):
        config.validate_runtime_requirements()


def test_production_settings_require_durable_chat_worker() -> None:
    config = _production_settings(response_interaction_worker_enabled=False)

    with pytest.raises(ValueError, match="durable chat interaction worker"):
        config.validate_runtime_requirements()


def test_production_settings_require_opentelemetry() -> None:
    config = _production_settings(otel_enabled=False)

    with pytest.raises(ValueError, match="OpenTelemetry tracing"):
        config.validate_runtime_requirements()


def test_production_settings_require_otlp_endpoint() -> None:
    config = _production_settings(otel_exporter_otlp_endpoint="")

    with pytest.raises(ValueError, match="OTLP endpoint"):
        config.validate_runtime_requirements()


def test_production_settings_require_vault_configuration() -> None:
    config = _production_settings(vault_url=None, vault_token=None)

    with pytest.raises(ValueError, match="Vault"):
        config.validate_runtime_requirements()


def test_production_settings_require_llm_provider() -> None:
    config = _production_settings(
        openai_api_key=None,
        deepseek_api_key=None,
        anthropic_api_key=None,
    )

    with pytest.raises(ValueError, match="LLM provider"):
        config.validate_runtime_requirements()


def test_production_settings_reject_placeholder_secret_key() -> None:
    config = _production_settings(secret_key="change-me")

    with pytest.raises(ValueError, match="SECRET_KEY"):
        config.validate_runtime_requirements()


def test_production_settings_require_plugin_signature_verification() -> None:
    config = _production_settings(plugin_signature_required=False)

    with pytest.raises(ValueError, match="plugin signature verification"):
        config.validate_runtime_requirements()


def test_production_settings_require_a_trusted_plugin_public_key() -> None:
    config = _production_settings(plugin_signature_public_keys=[])

    with pytest.raises(ValueError, match="plugin signature public key"):
        config.validate_runtime_requirements()


def test_production_settings_require_plugin_digest_verification() -> None:
    config = _production_settings(plugin_integrity_required=False)

    with pytest.raises(ValueError, match="digest verification"):
        config.validate_runtime_requirements()


def test_production_settings_require_database_credentials() -> None:
    config = _production_settings(
        database_url=None,
        database_user=None,
        database_pass=None,
        database_name="",
    )

    with pytest.raises(ValueError, match="database"):
        config.validate_runtime_requirements()


@pytest.mark.asyncio
async def test_application_lifespan_validates_runtime_before_startup(monkeypatch) -> None:
    from app import main

    called = False

    def fail_validation(_self) -> None:
        nonlocal called
        called = True
        raise RuntimeError("invalid runtime")

    monkeypatch.setattr(
        Settings,
        "validate_runtime_requirements",
        fail_validation,
    )

    with pytest.raises(RuntimeError, match="invalid runtime"):
        async with main.lifespan(main.app):
            pass

    assert called is True


@pytest.mark.asyncio
async def test_production_startup_fails_when_plugin_registry_cannot_load(
    monkeypatch,
) -> None:
    from app import main
    from app.modules.plugin.runtime.loader import PluginRuntimeLoader

    monkeypatch.setattr(
        Settings,
        "validate_runtime_requirements",
        lambda self: None,
    )
    monkeypatch.setattr(main.app_settings, "environment", "production")

    def fail_load(_self) -> None:
        raise RuntimeError("plugin database unavailable")

    monkeypatch.setattr(PluginRuntimeLoader, "load_all", fail_load)

    with pytest.raises(RuntimeError, match="plugin registry"):
        async with main.lifespan(main.app):
            pass


@pytest.mark.asyncio
async def test_production_startup_fails_when_outbox_handlers_cannot_register(
    monkeypatch,
) -> None:
    from app import main
    from app.modules.plugin.runtime.loader import PluginRuntimeLoader
    from app.wiring import outbox_handlers

    monkeypatch.setattr(
        Settings,
        "validate_runtime_requirements",
        lambda self: None,
    )
    monkeypatch.setattr(main.app_settings, "environment", "production")
    monkeypatch.setattr(main.app_settings, "knowledge_ingest_worker_enabled", True)
    monkeypatch.setattr(PluginRuntimeLoader, "load_all", lambda self: None)

    class _Task:
        cancelled = False

        def cancel(self) -> None:
            self.cancelled = True

        def __await__(self):
            async def done():
                return None

            return done().__await__()

    task = _Task()
    task_created = False

    def create_task(coroutine):
        nonlocal task_created
        task_created = True
        coroutine.close()
        return task

    monkeypatch.setattr(main.asyncio, "create_task", create_task)

    def fail_registration() -> None:
        raise RuntimeError("handler registry unavailable")

    monkeypatch.setattr(
        outbox_handlers,
        "register_outbox_handlers",
        fail_registration,
    )

    with pytest.raises(RuntimeError, match="outbox handlers"):
        async with main.lifespan(main.app):
            pass

    assert task_created is False or task.cancelled is True
