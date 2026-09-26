"""Addresses of an Ollama server.

Ollama serves its native API under ``/api`` and an OpenAI-compatible one
under ``/v1`` on the same host. Operators paste either address as a
provider's base URL, so both are derived from whichever was given.
"""

from __future__ import annotations

OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"

OLLAMA_PLACEHOLDER_KEY = "ollama"
"""Sent when no credential is bound: OpenAI clients refuse an empty key, and a
bare Ollama ignores whatever key it is given."""


def ollama_root_url(base_url: str | None) -> str:
    """The server root, where the native ``/api`` endpoints live."""
    root = (base_url or OLLAMA_DEFAULT_BASE_URL).rstrip("/")
    return root.removesuffix("/v1")


def ollama_openai_base_url(base_url: str | None) -> str:
    """The OpenAI-compatible address, ``{root}/v1``."""
    return f"{ollama_root_url(base_url)}/v1"
