"""Read the ids a provider gives a call, so its cost entry can be found in the provider's logs.

Two ids are kept: the response's own id (``chatcmpl-…``, ``msg_…``, Gemini's
``responseId``) and the request id from the response headers
(``x-request-id``, ``request-id``). An id an SDK made up is not the
provider's and is dropped: LiteLLM fills a missing id with
``chatcmpl-<uuid4>``, and always does for Anthropic.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

MAX_ID_LENGTH = 255

_LITELLM_MADE_UP_ID = re.compile(
    r"^chatcmpl-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
# LiteLLM drops the response id for these providers and makes one up instead.
_LITELLM_PROVIDERS_WITHOUT_IDS = frozenset({"anthropic"})
# Headers LiteLLM passes through from the provider, first match wins.
_LITELLM_REQUEST_ID_HEADERS = ("llm_provider-x-request-id", "llm_provider-request-id", "x-request-id")


def clean_id(value: Any) -> str | None:
    """A provider id as stored: a non-empty string, at most 255 characters."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:MAX_ID_LENGTH] if value else None


def header_id(headers: Any, *names: str) -> str | None:
    """The first of ``names`` present in ``headers`` (an httpx or dict-like mapping)."""
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    for name in names:
        value = clean_id(getter(name))
        if value:
            return value
    return None


def openai_request_id(response: Any) -> str | None:
    """The ``x-request-id`` the OpenAI SDK keeps on a parsed response."""
    return clean_id(getattr(response, "_request_id", None))


def stream_request_id(stream: Any, *names: str) -> str | None:
    """A request id from an SDK stream's HTTP response headers."""
    response = getattr(stream, "response", None)
    return header_id(getattr(response, "headers", None), *(names or ("x-request-id",)))


def litellm_ids(response: Any, provider: str | None = None) -> tuple[str | None, str | None]:
    """The provider's response id and request id from a LiteLLM response.

    The response id is kept only when LiteLLM did not make it up.
    """
    hidden = getattr(response, "_hidden_params", None)
    hidden = hidden if isinstance(hidden, Mapping) else {}
    backend = str(hidden.get("custom_llm_provider") or provider or "").lower()
    upstream_id = clean_id(getattr(response, "id", None))
    if upstream_id and (backend in _LITELLM_PROVIDERS_WITHOUT_IDS or _LITELLM_MADE_UP_ID.match(upstream_id)):
        upstream_id = None
    headers = hidden.get("additional_headers")
    request_id = header_id(headers if isinstance(headers, Mapping) else None, *_LITELLM_REQUEST_ID_HEADERS)
    return upstream_id, request_id
