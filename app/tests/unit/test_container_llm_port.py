"""Unit tests for container LLM provider wiring."""

from app.adapters.llm.memory import InMemoryLLMPort
from app.adapters.llm.router import LLMRouterPort
from app.wiring.container import Container


def test_create_llm_port_uses_deepseek_when_only_deepseek_key(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SOIT_TESTING", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    port = Container()._create_llm_port()

    assert isinstance(port, LLMRouterPort)
    assert "deepseek" in port.providers
    assert "openai" not in port.providers


def test_create_llm_port_falls_back_to_memory_without_provider_keys(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SOIT_TESTING", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    port = Container()._create_llm_port()

    assert isinstance(port, InMemoryLLMPort)
