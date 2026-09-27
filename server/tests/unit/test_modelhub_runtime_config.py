"""Tests for ModelHub LiteLLM runtime config and capability normalization."""

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.runtime_config import (
    normalize_capability_matrix,
    provider_timeout_seconds,
    resolve_litellm_runtime_config,
    validate_provider_timeout_ms,
)


@pytest.mark.parametrize(
    ("kind", "runtime", "connection", "auth", "credential_secret_id", "expected_provider"),
    [
        ("azure_openai", {}, {"api_version": "2026-01-01"}, {}, "sec_azure", "azure"),
        (
            "bedrock",
            {"litellm_params": {"aws_region_name": "us-east-1"}},
            {},
            {
                "secret_bindings": {
                    "aws_access_key_id": "sec_aws_access_key",
                    "aws_secret_access_key": "sec_aws_secret_key",
                }
            },
            None,
            "bedrock",
        ),
        ("openrouter", {}, {}, {}, "sec_openrouter", "openrouter"),
        ("ollama", {}, {}, {}, None, "ollama_chat"),
        ("dashscope", {}, {}, {}, "sec_dashscope", "dashscope"),
    ],
)
def test_litellm_provider_presets(
    kind,
    runtime,
    connection,
    auth,
    credential_secret_id,
    expected_provider,
):
    config = resolve_litellm_runtime_config(
        provider_kind=kind,
        runtime_config=runtime,
        connection_config=connection,
        auth_config=auth,
        credential_secret_id=credential_secret_id,
    )

    assert config.provider == expected_provider
    if credential_secret_id:
        assert config.secret_bindings["api_key"] == credential_secret_id
    if kind == "azure_openai":
        assert config.params["api_version"] == "2026-01-01"


def test_litellm_generic_provider_prefix_and_params_are_validated():
    config = resolve_litellm_runtime_config(
        provider_kind="company_gateway",
        runtime_config={
            "litellm_provider": "custom-provider",
            "litellm_params": {"organization": "org-1"},
        },
        connection_config={},
        auth_config={"secret_bindings": {"api_key": "sec_gateway"}},
        credential_secret_id=None,
    )

    assert config.provider == "custom-provider"
    assert config.params == {"organization": "org-1"}
    assert config.secret_bindings == {"api_key": "sec_gateway"}

    with pytest.raises(ValidationError, match="reserved LiteLLM parameter"):
        resolve_litellm_runtime_config(
            provider_kind="company_gateway",
            runtime_config={
                "litellm_provider": "custom-provider",
                "litellm_params": {"model": "override-model"},
            },
            connection_config={},
            auth_config={},
            credential_secret_id=None,
        )


@pytest.mark.parametrize(
    "legacy_value",
    ["secret:gateway", "kv/team/provider", "sec_gateway:value"],
)
def test_litellm_runtime_config_rejects_non_opaque_secret_ids(legacy_value):
    with pytest.raises(ValidationError, match="opaque secret_id"):
        resolve_litellm_runtime_config(
            provider_kind="openai",
            runtime_config={},
            connection_config={},
            auth_config={"secret_bindings": {"api_key": legacy_value}},
            credential_secret_id=None,
        )

    with pytest.raises(ValidationError, match="Invalid LiteLLM provider prefix"):
        resolve_litellm_runtime_config(
            provider_kind="company_gateway",
            runtime_config={"litellm_provider": "Invalid Provider"},
            connection_config={},
            auth_config={},
            credential_secret_id=None,
        )


def test_capability_matrix_normalizes_sources_and_merges_precedence():
    matrix = normalize_capability_matrix(
        {
            "chat": {
                "catalog": "supported",
                "diagnostics": "failed",
                "runtime": "supported",
                "user_override": "auto",
            },
            "tools": {
                "catalog": False,
                "diagnostics": None,
                "runtime": True,
                "user_override": "force_off",
            },
            "vision": {
                "catalog": True,
                "diagnostics": None,
                "runtime": None,
                "user_override": "auto",
            },
            "reasoning": {
                "catalog": "supported",
                "diagnostics": "passed",
                "runtime": False,
                "user_override": "enable_after_diagnostics",
            },
            "unknown": {},
        }
    )

    assert matrix["chat"] == {
        "catalog": True,
        "diagnostics": False,
        "runtime": True,
        "merged": False,
        "user_override": "auto",
    }
    assert matrix["tools"]["merged"] is False
    assert matrix["vision"]["catalog"] is True
    assert matrix["vision"]["merged"] is True
    assert matrix["reasoning"]["merged"] is True
    assert matrix["unknown"]["merged"] is None


@pytest.mark.parametrize("connection", [None, {}, {"timeout_ms": None}])
def test_a_provider_without_a_timeout_sets_none(connection):
    # None, not a minute: the gateway then applies the call type's own timeout.
    assert provider_timeout_seconds(connection) is None


@pytest.mark.parametrize(("timeout_ms", "seconds"), [(300000, 300.0), (45000.5, 45.0005), ("30000", 30.0)])
def test_a_provider_timeout_is_read_in_seconds(timeout_ms, seconds):
    assert provider_timeout_seconds({"timeout_ms": timeout_ms}) == seconds


@pytest.mark.parametrize("timeout_ms", [0, -1, "abc", True, float("nan"), float("inf"), [1]])
def test_an_unusable_stored_timeout_counts_as_none(timeout_ms, caplog):
    # A provider saved before the value was checked keeps routing.
    assert provider_timeout_seconds({"timeout_ms": timeout_ms}) is None
    assert "timeout_ms" in caplog.text


@pytest.mark.parametrize("timeout_ms", [0, -1, "30000", "abc", True, float("nan")])
def test_a_timeout_that_is_not_a_positive_number_is_refused_on_save(timeout_ms):
    with pytest.raises(ValidationError):
        validate_provider_timeout_ms(timeout_ms)


@pytest.mark.parametrize("timeout_ms", [None, 1, 300000, 2.5])
def test_a_positive_timeout_or_none_is_accepted_on_save(timeout_ms):
    validate_provider_timeout_ms(timeout_ms)
