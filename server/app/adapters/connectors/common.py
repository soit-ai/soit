"""Helpers shared by the knowledge connector implementations."""

from __future__ import annotations

import fnmatch
import posixpath
import re
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any, TypeVar, cast
from urllib.parse import urlsplit

import httpx

from app.adapters.http.governed_client import governed_httpx_client
from app.kernel.commons.errors import KernelError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.connectors import ConnectorError
from app.kernel.security.egress import GovernedEgressGuard

RESOURCE_S3 = "knowledge:connector:s3"
RESOURCE_WEB = "knowledge:crawler"
"""The web connector shares the crawler's resource reference, so one egress
policy governs every way a knowledge base fetches web pages."""

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# File types the knowledge parsers can read, by extension.
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".txt": "text/plain",
    ".text": "text/plain",
    ".log": "text/plain",
    ".csv": "text/plain",
    ".tsv": "text/plain",
    ".json": "text/plain",
    ".yaml": "text/plain",
    ".yml": "text/plain",
    ".rst": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".xhtml": "text/html",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

_SECRET_KEY = re.compile(
    r"(secret|password|passwd|token|api[_-]?key|access[_-]?key|credential|authorization|bearer)",
    re.IGNORECASE,
)

T = TypeVar("T")


def content_type_for(name: str) -> str | None:
    """The parseable content type for a file name, or None when it is not one."""
    return SUPPORTED_EXTENSIONS.get(posixpath.splitext(name.lower())[1])


def basename(path: str) -> str:
    """The last path segment, or the whole value when there is none."""
    return path.rstrip("/").rsplit("/", 1)[-1] or path


def reject_unknown_keys(config: Mapping[str, Any], allowed: Iterable[str]) -> None:
    """Refuse configuration keys the connector does not declare.

    Credentials in particular must come from a secret, never from the config,
    so a key that looks like one gets a message saying so.
    """
    allowed_set = set(allowed)
    unknown = sorted(str(key) for key in config if key not in allowed_set)
    if not unknown:
        return
    secretish = [key for key in unknown if _SECRET_KEY.search(key)]
    if secretish:
        raise ConnectorError(
            ConnectorError.CONFIG_INVALID,
            f"{', '.join(secretish)} looks like a credential. Store credentials in a secret and select it on the "
            "source; they are never accepted in the configuration.",
        )
    raise ConnectorError(ConnectorError.CONFIG_INVALID, f"Unknown setting: {', '.join(unknown)}")


def config_string(
    config: Mapping[str, Any],
    key: str,
    *,
    required: bool = False,
    default: str | None = None,
    max_length: int = 512,
) -> str | None:
    value = config.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} is required")
        return default
    if not isinstance(value, str):
        raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} must be text")
    value = value.strip()
    if len(value) > max_length:
        raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} is too long (at most {max_length} characters)")
    return value


def config_bool(config: Mapping[str, Any], key: str, *, default: bool) -> bool:
    value = config.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} must be true or false")
    return value


def config_int(
    config: Mapping[str, Any],
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = config.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} must be a whole number")
    if not minimum <= value <= maximum:
        raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} must be between {minimum} and {maximum}")
    return value


def config_string_list(
    config: Mapping[str, Any],
    key: str,
    *,
    max_items: int = 50,
    max_length: int = 512,
) -> list[str]:
    value = config.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} must be a list of text values")
    cleaned: list[str] = []
    entries = cast("list[Any]", value)
    for entry in entries:
        if not isinstance(entry, str):
            raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} must be a list of text values")
        entry = entry.strip()
        if not entry:
            continue
        if len(entry) > max_length:
            raise ConnectorError(ConnectorError.CONFIG_INVALID, f"An entry of {key} is too long")
        cleaned.append(entry)
    if len(cleaned) > max_items:
        raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} takes at most {max_items} entries")
    return cleaned


def validate_http_url(value: str, *, key: str, allow_path: bool, allow_query: bool = False) -> str:
    """Check a user-supplied http(s) URL and return it without a trailing slash."""
    try:
        parts = urlsplit(value)
        _ = parts.port
    except ValueError as exc:
        raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} is not a valid URL") from exc
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} must be an http or https URL")
    if parts.username or parts.password:
        raise ConnectorError(
            ConnectorError.CONFIG_INVALID,
            f"{key} must not contain credentials; use a secret for authentication",
        )
    if not allow_query and (parts.query or parts.fragment):
        raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} must not contain a query or fragment")
    if not allow_path and parts.path not in ("", "/"):
        raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{key} must not contain a path")
    return value.rstrip("/")


def matches_any(value: str, patterns: Iterable[str]) -> bool:
    """Whether a glob pattern matches ``value`` (``*`` also crosses ``/``)."""
    return any(fnmatch.fnmatchcase(value, pattern) for pattern in patterns)


def make_client(
    ctx: RequestContext,
    resource_ref: str,
    *,
    egress_guard: GovernedEgressGuard | None = None,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """The one way connectors get an HTTP client: every request is egress-authorized."""
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    return governed_httpx_client(ctx=ctx, resource_ref=resource_ref, egress_guard=egress_guard, **kwargs)


def egress_refusal(exc: KernelError, host: str | None) -> ConnectorError:
    """Turn the egress guard's refusal into something an operator can act on."""
    where = f" to {host}" if host else ""
    hint = (
        " Allow the host in the workspace egress policy; a host on a private network additionally "
        "needs its network listed in EGRESS_PRIVATE_NETWORKS."
    )
    return ConnectorError(
        ConnectorError.EGRESS_BLOCKED,
        f"Outbound access{where} was refused by the egress policy ({exc.message}).{hint}",
        {"reason_code": exc.code},
    )


async def guarded(call: Callable[[], Awaitable[T]], *, host: str | None) -> T:
    """Run an HTTP call, mapping transport and egress failures to ConnectorError."""
    try:
        return await call()
    except ConnectorError:
        raise
    except httpx.TimeoutException as exc:
        raise ConnectorError(
            ConnectorError.UNREACHABLE, f"The request to {host or 'the endpoint'} timed out"
        ) from exc
    except httpx.HTTPError as exc:
        raise ConnectorError(
            ConnectorError.UNREACHABLE,
            f"Could not reach {host or 'the endpoint'}: {exc.__class__.__name__}",
        ) from exc
    except KernelError as exc:
        raise egress_refusal(exc, host) from exc


async def read_limited(response: httpx.Response, max_bytes: int) -> bytes:
    """Read a streamed body, refusing one larger than ``max_bytes``."""
    declared = response.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise ConnectorError(
            ConnectorError.ITEM_TOO_LARGE,
            f"The item is {declared} bytes, over the {max_bytes} byte limit",
        )
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > max_bytes:
            raise ConnectorError(
                ConnectorError.ITEM_TOO_LARGE,
                f"The item is over the {max_bytes} byte limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)
