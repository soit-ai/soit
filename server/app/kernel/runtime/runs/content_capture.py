""" content_capture

What a run records of the content it handled.

``full`` keeps run and step summaries, previews and error messages as the
runtime writes them. ``metadata_only`` keeps none of that text: each value is
replaced by its length and a SHA-256 prefix, so two runs can still be told to
have handled the same input without either keeping it. Statuses, codes, token
counts, costs and timings are recorded either way.

The same holds for the structured records a run leaves: the tool call in a
step's metrics, a gateway audit payload. Their shape stays, so the ledger and
the evidence built from it still read them; every value that could carry
content is withheld, except identifiers (a run, a tool call, a secret
reference) and a URL's origin, which say what was reached without what was
sent. Withholding is idempotent: a marker passed back in is kept as it is.

The mode is a workspace setting that an API key can tighten but not loosen.
It is resolved when a request authenticates and travels in the request
context, including in contexts that workers store and resume. A worker that
builds a context of its own has no mode in it; the trace writer then looks the
workspace setting up through a lookup the wiring registers.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

CAPTURE_FULL = "full"
CAPTURE_METADATA_ONLY = "metadata_only"
CAPTURE_MODES = (CAPTURE_FULL, CAPTURE_METADATA_ONLY)

# Error details a failure can be diagnosed by without its text.
_STRUCTURAL_DETAIL_KEYS = frozenset(
    {"error_type", "code", "status_code", "reason", "param", "retry_after", "limit", "quota"}
)


def stricter_capture(*modes: str | None) -> str:
    """The mode that keeps least: metadata_only if any source asks for it."""
    return CAPTURE_METADATA_ONLY if CAPTURE_METADATA_ONLY in modes else CAPTURE_FULL


_MARKER = re.compile(r"\[withheld: \d+ chars, sha256:[0-9a-f]{16}\]")

# Fields of a record's own envelope (a step's tool call, an egress decision,
# the audit payload around a call, a step's metrics) that say what was called
# and how it went. They keep their value where the envelope holds them, never
# inside what the call handled.
_ENVELOPE_KEYS = frozenset(
    {
        "id",
        "run_id",
        "step_id",
        "tool_call_id",
        "workflow_run_id",
        "response_id",
        "task_id",
        "approval_id",
        "secret_id",
        "secret_ids",
        "egress_policy",
        "source",
        "source_kind",
        "adapter",
        "plugin_name",
        "plugin_version",
        "server_id",
        "server_name",
        "transport",
        "tool_ref",
        "tool_name",
        "tool_type",
        "gateway_type",
        "status",
        "decision",
        "success",
        "outcome",
        "reason",
        "error_code",
        "error_type",
        "code",
        "status_code",
        "http_status",
        "method",
        "latency_ms",
        "duration_ms",
        "attempt",
        "attempts",
        "attempt_count",
        "iteration",
        "replayed",
        "idempotent_replay",
        "result_type",
        "result_artifact_id",
        "artifact_key",
        "audit_size",
        "truncated",
        "timestamp",
        "model",
        "model_ref",
        "upstream_model",
        "provider",
        "provider_id",
        "provider_slug",
        "provider_kind",
        "direction",
        "category",
        "score",
        "strategy",
        "knowledge_id",
        "index_id",
        "node_id",
    }
)

# Where a record holds what the call handled. Every value inside is withheld,
# whatever its key, except the references records are linked by.
_PAYLOAD_KEYS = frozenset(
    {
        "arguments",
        "result",
        "metadata",
        "parameters",
        "content",
        "structuredContent",
        "body",
        "query",
        "headers",
        "error",
        "error_message",
        "details",
        "input",
        "output",
        "preview",
        "messages",
        "text",
        "data",
    }
)

# Inside a payload, only these still say which record another one is.
_REFERENCE_KEYS = frozenset(
    {"run_id", "tool_call_id", "workflow_run_id", "response_id", "task_id", "approval_id"}
)

def is_withheld(value: Any) -> bool:
    """Whether ``value`` is already a withheld marker."""
    return isinstance(value, str) and _MARKER.fullmatch(value) is not None


def withheld(value: str) -> str:
    """A marker that says how much text there was and which, but not what."""
    if is_withheld(value):
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"[withheld: {len(value)} chars, sha256:{digest}]"


def is_withheld_object(value: Any) -> bool:
    """Whether ``value`` is an object :func:`withheld_object` produced."""
    return isinstance(value, dict) and set(value) == {"withheld"} and is_withheld(value["withheld"])


def withheld_object(value: Any) -> dict[str, str]:
    """A whole object replaced by one marker, still an object."""
    if isinstance(value, dict) and set(value) == {"withheld"} and is_withheld(value["withheld"]):
        return dict(value)
    return {"withheld": withheld(json.dumps(value, default=str, sort_keys=True))}


def url_origin(url: str) -> str:
    """``scheme://host[:port]`` of a URL: where it went, not what it carried.

    Whatever cannot be read as one (no host, a port out of range, a broken
    IPv6 literal) is withheld whole rather than left to fail the write.
    """
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        return withheld(url)
    if not parts.scheme or not hostname:
        return withheld(url)
    host = hostname if ":" not in hostname else f"[{hostname}]"
    return f"{parts.scheme}://{host}" + (f":{port}" if port else "")


def _is_plain(value: Any) -> bool:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    return isinstance(value, list | tuple) and all(
        item is None or isinstance(item, str | int | float | bool) for item in value
    )


def _is_secret_reference(key: str, value: Any) -> bool:
    if key == "secret_id":
        return isinstance(value, str) and value.startswith("sec_")
    if key == "secret_ids":
        return isinstance(value, list | tuple) and all(
            isinstance(item, str) and item.startswith("sec_") for item in value
        )
    return False


def _leaf(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return withheld(value)
    return withheld(json.dumps(value, default=str))


def _url(value: Any) -> Any:
    if isinstance(value, str) and not is_withheld(value) and "://" in value:
        return url_origin(value)
    return _leaf(value)


def withhold_payload(value: Any) -> Any:
    """What a call handled, with only the references that link records kept."""
    if isinstance(value, dict):
        kept: dict[Any, Any] = {}
        for key, item in value.items():
            name = str(key)
            if _is_secret_reference(name, item):
                kept[key] = item
            elif (name in _REFERENCE_KEYS or name.endswith("_run_id")) and isinstance(item, str):
                kept[key] = item
            elif name == "url":
                kept[key] = _url(item)
            else:
                kept[key] = withhold_payload(item)
        return kept
    if isinstance(value, list | tuple):
        return [withhold_payload(item) for item in value]
    return _leaf(value)


def withhold_values(value: Any) -> Any:
    """A record's envelope with its shape and identifiers kept.

    What the envelope holds of the call itself (arguments, results, bodies)
    goes through :func:`withhold_payload`; any other value is withheld.
    """
    if isinstance(value, dict):
        kept: dict[Any, Any] = {}
        for key, item in value.items():
            name = str(key)
            if name in _PAYLOAD_KEYS:
                kept[key] = withhold_payload(item)
            elif name in _ENVELOPE_KEYS and _is_plain(item):
                kept[key] = item
            elif name == "url":
                kept[key] = _url(item)
            else:
                kept[key] = withhold_values(item)
        return kept
    if isinstance(value, list | tuple):
        return [withhold_values(item) for item in value]
    return _leaf(value)


@dataclass(frozen=True)
class ContentCapture:
    """Applies a capture mode to the text a trace is about to store."""

    mode: str = CAPTURE_FULL

    @property
    def keeps_content(self) -> bool:
        return self.mode != CAPTURE_METADATA_ONLY

    def text(self, value: str | None) -> str | None:
        if value is None or self.keeps_content:
            return value
        return withheld(value)

    def details(self, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """Error details with every free-text value withheld."""
        if value is None or self.keeps_content:
            return value
        kept: dict[str, Any] = {}
        for key, item in value.items():
            if key in _STRUCTURAL_DETAIL_KEYS or item is None or isinstance(item, bool | int | float):
                kept[key] = item
            elif isinstance(item, str):
                kept[key] = withheld(item)
            else:
                kept[key] = withheld(json.dumps(item, default=str, sort_keys=True))
        return kept

    def metrics(self, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """Step metrics with only counts, timings and identity kept.

        Numbers, flags and the fields that name a model, provider, tool or
        knowledge base stay; a tool call keeps its envelope; any other value
        a metric carries, a retrieval's query or a tool's output, is withheld.
        """
        if value is None or self.keeps_content:
            return value
        kept: dict[str, Any] = {}
        for key, item in value.items():
            if item is None or isinstance(item, bool | int | float):
                kept[key] = item
            elif key == "content_safety" and isinstance(item, list):
                kept[key] = [_without_finding_details(entry) for entry in item]
            elif key in _PAYLOAD_KEYS:
                kept[key] = withhold_payload(item)
            elif key in _ENVELOPE_KEYS and _is_plain(item):
                kept[key] = item
            else:
                kept[key] = withhold_values(item)
        return kept

    def identifiers(self, value: dict[str, Any]) -> dict[str, Any]:
        """Only the identifying fields of a record spread into another."""
        if self.keeps_content:
            return value
        return {key: item for key, item in value.items() if key in _ENVELOPE_KEYS and _is_plain(item)}

    def audit_payload(self, value: dict[str, Any]) -> dict[str, Any]:
        """A gateway audit payload with its structure and identifiers only."""
        if self.keeps_content:
            return value
        return withhold_values(value)


def _without_finding_details(evidence: Any) -> Any:
    """Content-safety evidence with any text a classifier echoed withheld."""
    if not isinstance(evidence, dict) or not isinstance(evidence.get("findings"), list):
        return evidence
    findings = []
    for finding in evidence["findings"]:
        if isinstance(finding, dict) and isinstance(finding.get("detail"), str):
            finding = {**finding, "detail": withheld(finding["detail"])}
        findings.append(finding)
    return {**evidence, "findings": findings}


WorkspaceCaptureLookup = Callable[[Any, str, str], Awaitable[str | None]]
"""(session, tenant_id, workspace_id) -> the workspace's mode, or None."""

_workspace_capture_lookup: WorkspaceCaptureLookup | None = None


def register_workspace_capture_lookup(lookup: WorkspaceCaptureLookup) -> None:
    global _workspace_capture_lookup
    _workspace_capture_lookup = lookup


def reset_workspace_capture_lookup() -> None:
    global _workspace_capture_lookup
    _workspace_capture_lookup = None


def get_workspace_capture_lookup() -> WorkspaceCaptureLookup | None:
    return _workspace_capture_lookup


def capture_mode(value: str | None) -> str:
    """A known mode, or the one that keeps least for anything else."""
    if value is None:
        return CAPTURE_FULL
    return value if value in CAPTURE_MODES else CAPTURE_METADATA_ONLY


async def lookup_workspace_capture(db: Any, tenant_id: str, workspace_id: str) -> str:
    """The workspace's mode read on ``db``, for a context that carries none.

    If the read fails, content is withheld rather than kept against the
    workspace's wishes. Without a session or a registered lookup there is no
    setting to honour, and content is kept.
    """
    lookup = get_workspace_capture_lookup()
    if lookup is None or db is None:
        return CAPTURE_FULL
    try:
        found = await lookup(db, tenant_id, workspace_id)
    except Exception:
        logger.warning("Content capture lookup failed; withholding content", exc_info=True)
        return CAPTURE_METADATA_ONLY
    return capture_mode(found)


async def writer_capture(writer: Any, ctx: Any) -> ContentCapture:
    """The mode of ``writer`` when it is a trace writer, else of ``ctx``."""
    method = getattr(writer, "content_capture", None)
    if callable(method):
        found = method()
        if inspect.isawaitable(found):
            found = await found
        if isinstance(found, ContentCapture):
            return found
    return await resolve_content_capture(None, ctx)


async def resolve_content_capture(db: Any, ctx: Any) -> ContentCapture:
    """What a store working for ``ctx`` keeps of content: the mode the request
    context carries from authentication, else the workspace setting."""
    mode = getattr(ctx, "content_capture", None)
    if mode is not None:
        return ContentCapture(capture_mode(mode))
    return ContentCapture(await lookup_workspace_capture(db, ctx.tenant_id, ctx.workspace_id))
