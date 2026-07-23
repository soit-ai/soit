"""LLM provider runtime configuration and capability normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.secrets.interface import require_opaque_secret_id

LITELLM_PROVIDER_PRESETS: dict[str, str] = {
    "openai": "openai",
    "openai_compatible": "openai",
    "anthropic": "anthropic",
    "deepseek": "deepseek",
    "gemini": "gemini",
    "azure_openai": "azure",
    "bedrock": "bedrock",
    "openrouter": "openrouter",
    "ollama": "ollama_chat",
    "dashscope": "dashscope",
}

PROVIDER_CAPABILITY_PRESETS: dict[str, dict[str, bool]] = {
    "openai": {"chat": True, "embeddings": True, "rerank": False, "tools": True},
    "openai_compatible": {
        "chat": True,
        "embeddings": True,
        "rerank": False,
        "tools": True,
    },
    "deepseek": {"chat": True, "embeddings": False, "rerank": False, "tools": True},
    "anthropic": {"chat": True, "embeddings": False, "rerank": False, "tools": False},
    "gemini": {"chat": True, "embeddings": True, "rerank": False, "tools": True},
    "azure_openai": {"chat": True, "embeddings": True, "rerank": False, "tools": True},
    "bedrock": {"chat": True, "embeddings": True, "rerank": False, "tools": True},
    "openrouter": {"chat": True, "embeddings": True, "rerank": False, "tools": True},
    "ollama": {"chat": True, "embeddings": True, "rerank": False, "tools": False},
    "dashscope": {"chat": True, "embeddings": True, "rerank": False, "tools": True},
}

LITELLM_STATIC_PARAM_ALLOWLIST = {
    "api_version",
    "organization",
    "project",
    "aws_region_name",
    "region_name",
    "extra_headers",
    "drop_params",
    "vertex_project",
    "vertex_location",
}

LITELLM_SECRET_BINDING_ALLOWLIST = {
    "api_key",
    "azure_ad_token",
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
}

LITELLM_RESERVED_PARAMS = {
    "model",
    "messages",
    "input",
    "stream",
    "stream_options",
    "tools",
    "tool_choice",
    "timeout",
    "num_retries",
    "api_base",
}

_PROVIDER_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


@dataclass(frozen=True)
class LiteLLMRuntimeConfig:
    """Validated LiteLLM prefix, static params, and secret references."""

    provider: str
    params: dict[str, Any]
    secret_bindings: dict[str, str]


def validate_litellm_provider_prefix(value: str) -> str:
    """Validate and return a LiteLLM provider prefix."""
    provider = value.strip()
    if not _PROVIDER_PREFIX_PATTERN.fullmatch(provider):
        raise ValidationError(f"Invalid LiteLLM provider prefix: {value}")
    return provider


def validate_litellm_params(
    params: dict[str, Any] | None,
    *,
    allow_secret_values: bool = False,
) -> dict[str, Any]:
    """Validate pass-through LiteLLM parameters against the SOIT allowlist."""
    values = dict(params or {})
    allowed = set(LITELLM_STATIC_PARAM_ALLOWLIST)
    if allow_secret_values:
        allowed.update(LITELLM_SECRET_BINDING_ALLOWLIST)
    for key in values:
        if key in LITELLM_RESERVED_PARAMS:
            raise ValidationError(f"Provider config contains reserved LiteLLM parameter: {key}")
        if key not in allowed:
            raise ValidationError(f"Provider config contains unsupported LiteLLM parameter: {key}")
    return values


def resolve_litellm_runtime_config(
    *,
    provider_kind: str,
    runtime_config: dict[str, Any] | None,
    connection_config: dict[str, Any] | None,
    auth_config: dict[str, Any] | None,
    credential_secret_id: str | None,
) -> LiteLLMRuntimeConfig:
    """Resolve one provider record into a validated LiteLLM runtime config."""
    runtime = runtime_config or {}
    connection = connection_config or {}
    auth = auth_config or {}
    raw_provider = runtime.get("litellm_provider") or LITELLM_PROVIDER_PRESETS.get(provider_kind)
    if not raw_provider:
        raise ValidationError(
            f"LiteLLM provider prefix is required for provider kind: {provider_kind}"
        )
    provider = validate_litellm_provider_prefix(str(raw_provider))
    params = validate_litellm_params(runtime.get("litellm_params"))
    if provider == "azure" and connection.get("api_version") is not None:
        params.setdefault("api_version", connection["api_version"])

    raw_bindings = auth.get("secret_bindings") or {}
    if not isinstance(raw_bindings, dict):
        raise ValidationError("Provider secret_bindings must be an object")
    secret_bindings: dict[str, str] = {}
    for key, secret_id in raw_bindings.items():
        if key not in LITELLM_SECRET_BINDING_ALLOWLIST:
            raise ValidationError(f"Unsupported LiteLLM secret binding: {key}")
        if not isinstance(secret_id, str) or not secret_id.strip():
            raise ValidationError(f"LiteLLM secret binding must reference a secret: {key}")
        secret_bindings[key] = require_opaque_secret_id(secret_id)
    if credential_secret_id and "api_key" not in secret_bindings:
        secret_bindings["api_key"] = require_opaque_secret_id(credential_secret_id)

    return LiteLLMRuntimeConfig(
        provider=provider,
        params=params,
        secret_bindings=secret_bindings,
    )


def _normalize_support_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "supported", "trusted", "passed", "callable", "enabled"}:
            return True
        if normalized in {"false", "unsupported", "failed", "unavailable", "disabled"}:
            return False
        if normalized in {"unknown", "skipped", "partial", "not_reported", ""}:
            return None
    raise ValidationError(f"Invalid capability support value: {value}")


def normalize_capability_matrix(
    matrix: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Normalize capability sources and calculate the final merged support."""
    normalized_matrix: dict[str, dict[str, Any]] = {}
    for capability, raw_entry in (matrix or {}).items():
        if raw_entry is None:
            entry = {}
        elif isinstance(raw_entry, dict):
            entry = raw_entry
        else:
            raise ValidationError(f"Invalid capability matrix entry: {capability}")

        catalog = _normalize_support_value(entry.get("catalog"))
        diagnostics = _normalize_support_value(entry.get("diagnostics"))
        runtime = _normalize_support_value(entry.get("runtime"))
        user_override = str(entry.get("user_override") or "auto")
        if user_override == "force_on":
            merged: bool | None = True
        elif user_override == "force_off":
            merged = False
        elif user_override == "enable_after_diagnostics":
            merged = diagnostics is True
        elif user_override == "auto":
            merged = next(
                (
                    value
                    for value in (diagnostics, runtime, catalog)
                    if value is not None
                ),
                None,
            )
        else:
            raise ValidationError(f"Invalid capability user override: {user_override}")

        normalized_matrix[str(capability)] = {
            "catalog": catalog,
            "diagnostics": diagnostics,
            "runtime": runtime,
            "merged": merged,
            "user_override": user_override,
        }
    return normalized_matrix
