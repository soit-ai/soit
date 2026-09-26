"""LLM provider runtime configuration and capability normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.kernel.commons.errors import KernelError, ValidationError
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
    "openai": {
        "chat": True,
        "embeddings": True,
        "rerank": False,
        "tools": True,
        "image_generation": True,
        "image_edit": True,
    },
    "openai_compatible": {
        "chat": True,
        "embeddings": True,
        "rerank": False,
        "tools": True,
        "image_generation": True,
        "image_edit": True,
    },
    "deepseek": {
        "chat": True,
        "embeddings": False,
        "rerank": False,
        "tools": True,
        "image_generation": False,
        "image_edit": False,
    },
    "anthropic": {
        "chat": True,
        "embeddings": False,
        "rerank": False,
        "tools": True,
        "image_generation": False,
        "image_edit": False,
    },
    "gemini": {
        "chat": True,
        "embeddings": True,
        "rerank": False,
        "tools": True,
        "image_generation": True,
        # LiteLLM has no image-edit branch for Gemini; a route here would fail
        # at the provider with each vendor's own wording instead of ours.
        "image_edit": False,
    },
    "azure_openai": {
        "chat": True,
        "embeddings": True,
        "rerank": False,
        "tools": True,
        "image_generation": True,
        "image_edit": True,
    },
    "bedrock": {
        "chat": True,
        "embeddings": True,
        "rerank": False,
        "tools": True,
        "image_generation": True,
        "image_edit": True,
    },
    "openrouter": {
        "chat": True,
        "embeddings": True,
        "rerank": False,
        "tools": True,
        "image_generation": True,
        "image_edit": False,
    },
    "ollama": {
        "chat": True,
        "embeddings": True,
        "rerank": False,
        "tools": False,
        "image_generation": False,
        "image_edit": False,
    },
    "dashscope": {
        "chat": True,
        "embeddings": True,
        "rerank": False,
        "tools": True,
        "image_generation": True,
        "image_edit": False,
    },
}

IMAGE_CAPABILITY_DEFAULTS: dict[str, Any] = {
    "mask": None,
    "transparent_background": None,
    "max_dimension": None,
    "supports_seed": None,
}
"""Per-model image traits, declared alongside the coarse capability flags.

``None`` means the model never declared the trait. That is "unknown", not
"unsupported": a request is only refused against a trait the catalog or the
operator actually stated, so an undeclared model keeps behaving exactly as it
did before these fields existed.
"""

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


def normalize_image_capabilities(
    capabilities_json: dict[str, Any] | None,
) -> dict[str, Any]:
    """Read the per-model image traits out of a model's capability document.

    Traits live under an ``image`` object so they stay separate from the coarse
    ``image_generation`` / ``image_edit`` flags the router checks: the flags say
    whether the model can be routed at all, these say what it can be asked for.
    An absent or malformed document yields all-unknown rather than an error,
    because a bad catalog entry must not take the model offline.
    """
    traits = dict(IMAGE_CAPABILITY_DEFAULTS)
    if not isinstance(capabilities_json, dict):
        return traits

    raw = capabilities_json.get("image")
    if not isinstance(raw, dict):
        return traits

    for key in ("mask", "transparent_background", "supports_seed"):
        if key not in raw:
            continue
        try:
            traits[key] = _normalize_support_value(raw.get(key))
        except ValidationError:
            # An unreadable trait stays unknown; refusing requests on the
            # strength of a value we could not parse would be worse.
            traits[key] = None

    max_dimension = raw.get("max_dimension")
    if isinstance(max_dimension, bool):
        max_dimension = None
    if max_dimension is not None:
        try:
            parsed = int(max_dimension)
        except (TypeError, ValueError):
            parsed = 0
        traits["max_dimension"] = parsed if parsed > 0 else None

    return traits


def parse_image_size(size: str | None) -> tuple[int, int] | None:
    """Parse a ``WxH`` size hint into pixels, or None when unset."""
    if not size:
        return None
    width, _, height = str(size).partition("x")
    try:
        return int(width), int(height)
    except (TypeError, ValueError):
        raise ValidationError(f"Invalid image size: {size}") from None


def validate_image_request(
    image_capabilities: dict[str, Any] | None,
    *,
    model: str,
    size: str | None = None,
    has_mask: bool = False,
    background: str | None = None,
    seed: int | None = None,
) -> None:
    """Refuse an image request the routed model has declared it cannot serve.

    Checked here, before the provider call, so the caller gets one SOIT error
    code instead of each vendor's own wording for the same refusal, and so a
    request that could never succeed is never billed.

    Only declared traits are enforced. A model that never stated a trait is
    routed as before and may still be refused upstream.
    """
    traits = image_capabilities or {}

    if has_mask and traits.get("mask") is False:
        raise KernelError(
            "MODEL_IMAGE_CAPABILITY_UNAVAILABLE",
            "The routed model does not accept an edit mask",
            {"model": model, "capability": "mask"},
        )

    if background == "transparent" and traits.get("transparent_background") is False:
        raise KernelError(
            "MODEL_IMAGE_CAPABILITY_UNAVAILABLE",
            "The routed model cannot return a transparent background",
            {"model": model, "capability": "transparent_background"},
        )

    if seed is not None and traits.get("supports_seed") is False:
        raise KernelError(
            "MODEL_IMAGE_CAPABILITY_UNAVAILABLE",
            "The routed model does not accept a seed",
            {"model": model, "capability": "supports_seed"},
        )

    max_dimension = traits.get("max_dimension")
    parsed_size = parse_image_size(size)
    if parsed_size is not None and isinstance(max_dimension, int):
        longest = max(parsed_size)
        if longest > max_dimension:
            raise KernelError(
                "MODEL_IMAGE_CAPABILITY_UNAVAILABLE",
                (
                    f"Requested image size {size} exceeds the model's "
                    f"maximum dimension of {max_dimension} pixels"
                ),
                {
                    "model": model,
                    "capability": "max_dimension",
                    "max_dimension": max_dimension,
                    "requested": size,
                },
            )
