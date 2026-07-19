"""Unit tests for container LLM provider wiring."""

import pytest

from app.adapters.llm.memory import InMemoryLLMPort
from app.adapters.llm.router import LLMRouterPort
from app.wiring.container import Container


@pytest.fixture(autouse=True)
def _isolate_provider_settings(monkeypatch):
    monkeypatch.setattr("app.wiring.container.settings.openai_api_key", None)
    monkeypatch.setattr("app.wiring.container.settings.deepseek_api_key", None)
    monkeypatch.setattr("app.wiring.container.settings.anthropic_api_key", None)


def test_create_llm_port_uses_deepseek_when_only_deepseek_key(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SOIT_TESTING", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    port = Container()._create_llm_port()

    assert isinstance(port, LLMRouterPort)
    assert "deepseek" in port.providers
    assert "openai" not in port.providers


def test_create_llm_port_keeps_test_provider_with_real_provider_keys(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SOIT_TESTING", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    port = Container()._create_llm_port()

    assert isinstance(port, LLMRouterPort)
    assert "openai" in port.providers
    assert isinstance(port.providers["test"], InMemoryLLMPort)


def test_create_llm_port_uses_openai_key_loaded_by_settings(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SOIT_TESTING", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("app.wiring.container.settings.openai_api_key", "settings-openai-key")

    port = Container()._create_llm_port()

    assert isinstance(port, LLMRouterPort)
    assert "openai" in port.providers


def test_create_llm_port_registers_anthropic_provider(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SOIT_TESTING", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    port = Container()._create_llm_port()

    assert isinstance(port, LLMRouterPort)
    assert "anthropic" in port.providers
    assert "openai" not in port.providers


def test_create_llm_port_allows_database_backed_providers_without_environment_keys(
    monkeypatch,
) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SOIT_TESTING", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("app.wiring.container.settings.environment", "production")

    port = Container()._create_llm_port()

    assert isinstance(port, LLMRouterPort)
    assert port.providers == {}
    assert port.provider_resolver is not None
    assert port.secrets_resolver is not None


def test_container_shares_provider_resolver_with_llm_router(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SOIT_TESTING", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    container = Container()

    resolver = container.get("llm_provider_resolver")
    port = container._create_llm_port()

    assert isinstance(port, LLMRouterPort)
    assert port.provider_resolver is resolver


def test_create_secrets_port_fails_closed_in_production_without_vault(
    monkeypatch,
) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SOIT_TESTING", raising=False)
    monkeypatch.setattr("app.wiring.container.settings.environment", "production")
    monkeypatch.setattr("app.wiring.container.settings.vault_url", None)
    monkeypatch.setattr("app.wiring.container.settings.vault_token", None)

    with pytest.raises(RuntimeError, match="Vault"):
        Container()._create_secrets_port()


def test_create_event_bus_rejects_memory_backend_in_production(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SOIT_TESTING", raising=False)
    monkeypatch.setattr("app.wiring.container.settings.environment", "production")
    monkeypatch.setattr("app.wiring.container.settings.event_bus_backend", "memory")

    with pytest.raises(RuntimeError, match="Redis"):
        Container()._create_event_bus()
