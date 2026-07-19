"""Tests for ModelHub LiteLLM runtime config and capability normalization."""

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.runtime_config import (
    normalize_capability_matrix,
    resolve_litellm_runtime_config,
)


@pytest.mark.parametrize(
    ("kind", "runtime", "connection", "auth", "credential_ref", "expected_provider"),
    [
        ("azure_openai", {}, {"api_version": "2026-01-01"}, {}, "secret:azure", "azure"),
        (
            "bedrock",
            {"litellm_params": {"aws_region_name": "us-east-1"}},
            {},
            {
                "secret_bindings": {
                    "aws_access_key_id": "secret:aws-access-key",
                    "aws_secret_access_key": "secret:aws-secret-key",
                }
            },
            None,
            "bedrock",
        ),
        ("openrouter", {}, {}, {}, "secret:openrouter", "openrouter"),
        ("ollama", {}, {}, {}, None, "ollama_chat"),
        ("dashscope", {}, {}, {}, "secret:dashscope", "dashscope"),
    ],
)
def test_litellm_provider_presets(
    kind,
    runtime,
    connection,
    auth,
    credential_ref,
    expected_provider,
):
    config = resolve_litellm_runtime_config(
        provider_kind=kind,
        runtime_config=runtime,
        connection_config=connection,
        auth_config=auth,
        credential_ref=credential_ref,
    )

    assert config.provider == expected_provider
    if credential_ref:
        assert config.secret_bindings["api_key"] == credential_ref
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
        auth_config={"secret_bindings": {"api_key": "secret:gateway"}},
        credential_ref=None,
    )

    assert config.provider == "custom-provider"
    assert config.params == {"organization": "org-1"}
    assert config.secret_bindings == {"api_key": "secret:gateway"}

    with pytest.raises(ValidationError, match="reserved LiteLLM parameter"):
        resolve_litellm_runtime_config(
            provider_kind="company_gateway",
            runtime_config={
                "litellm_provider": "custom-provider",
                "litellm_params": {"model": "override-model"},
            },
            connection_config={},
            auth_config={},
            credential_ref=None,
        )

    with pytest.raises(ValidationError, match="Invalid LiteLLM provider prefix"):
        resolve_litellm_runtime_config(
            provider_kind="company_gateway",
            runtime_config={"litellm_provider": "Invalid Provider"},
            connection_config={},
            auth_config={},
            credential_ref=None,
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
