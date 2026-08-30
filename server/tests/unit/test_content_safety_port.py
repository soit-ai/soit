"""Content safety is pluggable, fails closed, and never logs matched text."""

import pytest

from app.adapters.safety.http_content_safety import HttpContentSafetyPort
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.safety.interface import (
    SafetyDecision,
    SafetyDirection,
    SafetyFinding,
    SafetyVerdict,
)
from app.settings.settings import Settings
from app.wiring.container import Container


def _ctx() -> RequestContext:
    return RequestContext(tenant_id="t", workspace_id="w", user_id="u")


def _port(**overrides) -> HttpContentSafetyPort:
    kwargs = {
        "ctx": _ctx(),
        "endpoint": "https://safety.internal/inspect",
    }
    kwargs.update(overrides)
    return HttpContentSafetyPort(**kwargs)


def test_verdict_evidence_excludes_the_matched_text():
    verdict = SafetyVerdict(
        decision=SafetyDecision.REDACT,
        findings=[SafetyFinding(category="pii.email", severity="high")],
        redacted_text="hello [REDACTED]",
        provider="acme",
    )

    evidence = verdict.evidence()

    # Recording the detected value would recreate the exposure the check exists
    # to prevent, so evidence carries categories only.
    assert "hello" not in str(evidence)
    assert "[REDACTED]" not in str(evidence)
    assert evidence["decision"] == "redact"
    assert evidence["provider"] == "acme"
    assert evidence["findings"] == [
        {"category": "pii.email", "severity": "high", "detail": None}
    ]


def test_provider_response_maps_onto_the_kernel_verdict():
    port = _port()

    verdict = port._to_verdict(
        {
            "decision": "block",
            "findings": [
                {"category": "violence", "severity": "high", "detail": "policy 4"},
                {"category": "", "severity": "low"},
                "not-a-mapping",
            ],
        }
    )

    assert verdict.decision is SafetyDecision.BLOCK
    assert verdict.blocked
    # Entries without a category carry no meaning and are dropped.
    assert [item.category for item in verdict.findings] == ["violence"]


def test_an_unrecognised_decision_is_not_treated_as_permission():
    assert _port(fail_closed=True)._to_verdict({"decision": "maybe"}).decision is (
        SafetyDecision.BLOCK
    )
    assert _port(fail_closed=False)._to_verdict({"decision": "maybe"}).decision is (
        SafetyDecision.ALLOW
    )


@pytest.mark.asyncio
async def test_an_unreachable_classifier_blocks_by_default(monkeypatch):
    port = _port(fail_closed=True)
    monkeypatch.setattr(
        "app.adapters.safety.http_content_safety.governed_httpx_client",
        lambda **_: (_ for _ in ()).throw(RuntimeError("network down")),
    )

    verdict = await port.inspect("hello", direction=SafetyDirection.INBOUND)

    # Availability of the classifier must not silently disable enforcement.
    assert verdict.blocked
    assert verdict.findings[0].category == "safety.provider_unavailable"


@pytest.mark.asyncio
async def test_a_deployment_may_opt_into_availability_over_enforcement(monkeypatch):
    port = _port(fail_closed=False)
    monkeypatch.setattr(
        "app.adapters.safety.http_content_safety.governed_httpx_client",
        lambda **_: (_ for _ in ()).throw(RuntimeError("network down")),
    )

    verdict = await port.inspect("hello", direction=SafetyDirection.OUTBOUND)

    assert verdict.decision is SafetyDecision.ALLOW
    assert verdict.findings[0].severity == "warning"


def test_container_reports_no_capability_when_unconfigured(monkeypatch):
    from app.wiring import container as container_module

    monkeypatch.setattr(container_module.settings, "content_safety_enabled", False)

    # No adapter means the platform has no such capability; callers must not
    # read None as "content is safe".
    assert Container().get_content_safety_port(_ctx()) is None


def test_container_requires_an_endpoint_before_claiming_an_external_classifier(
    monkeypatch,
):
    from app.wiring import container as container_module

    monkeypatch.setattr(container_module.settings, "content_safety_enabled", True)
    monkeypatch.setattr(container_module.settings, "content_safety_provider", "http")
    monkeypatch.setattr(container_module.settings, "content_safety_endpoint", "  ")

    # Claiming inspection while sending content nowhere is worse than saying
    # the capability is unavailable.
    assert Container().get_content_safety_port(_ctx()) is None


def test_container_builds_the_adapter_when_configured(monkeypatch):
    from app.wiring import container as container_module

    monkeypatch.setattr(container_module.settings, "content_safety_enabled", True)
    monkeypatch.setattr(container_module.settings, "content_safety_provider", "http")
    monkeypatch.setattr(
        container_module.settings,
        "content_safety_endpoint",
        "https://safety.internal/inspect",
    )

    port = Container().get_content_safety_port(_ctx())

    assert isinstance(port, HttpContentSafetyPort)


def test_container_builds_the_builtin_provider_by_default(monkeypatch):
    """It needs no service, so an unconfigured install still inspects."""
    from app.kernel.safety.rules import RuleContentSafetyPort, SafetyAction
    from app.wiring import container as container_module

    monkeypatch.setattr(container_module.settings, "content_safety_enabled", True)
    monkeypatch.setattr(container_module.settings, "content_safety_provider", "builtin")

    port = Container().get_content_safety_port(_ctx())

    assert isinstance(port, RuleContentSafetyPort)
    assert port.secret_action is SafetyAction.REDACT
    assert port.pii_action is SafetyAction.OBSERVE


def test_a_misspelled_action_does_not_quietly_disable_the_check(monkeypatch):
    from app.kernel.safety.rules import SafetyAction
    from app.wiring import container as container_module

    monkeypatch.setattr(container_module.settings, "content_safety_enabled", True)
    monkeypatch.setattr(container_module.settings, "content_safety_provider", "builtin")
    monkeypatch.setattr(container_module.settings, "content_safety_secret_action", "redakt")

    port = Container().get_content_safety_port(_ctx())

    assert port.secret_action is SafetyAction.REDACT


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


def test_production_rejects_an_external_classifier_without_an_endpoint():
    config = _production_settings(
        content_safety_enabled=True,
        content_safety_provider="http",
        content_safety_endpoint=None,
    )

    with pytest.raises(ValueError, match="no endpoint is configured"):
        config.validate_runtime_requirements()


def test_production_accepts_the_builtin_provider_with_no_endpoint():
    # It runs in process, so there is nothing to point at.
    _production_settings(
        content_safety_enabled=True,
        content_safety_provider="builtin",
    ).validate_runtime_requirements()


def test_production_accepts_content_safety_turned_off():
    # Not providing the capability is a documented, honest state.
    _production_settings(content_safety_enabled=False).validate_runtime_requirements()
