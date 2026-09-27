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

# Keys whose values identify what a call touched rather than carry what it
# handled. They keep their value wherever they appear in a withheld record.
_IDENTIFIER_KEYS = frozenset(
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
        "iteration",
        "idempotent_replay",
        "result_type",
        "result_artifact_id",
        "artifact_key",
        "audit_size",
        "truncated",
        "timestamp",
        "provider",
        "direction",
        "category",
        "score",
        "knowledge_id",
        "index_id",
    }
)

# Top-level step metrics that hold what a call handled.
_CONTENT_METRIC_KEYS = ("tool_call", "egress", "content", "structuredContent")


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
    """``scheme://host[:port]`` of a URL: where it went, not what it carried."""
    parts = urlsplit(url)
    if not parts.scheme or not parts.hostname:
        return withheld(url)
    host = parts.hostname if ":" not in parts.hostname else f"[{parts.hostname}]"
    return f"{parts.scheme}://{host}" + (f":{parts.port}" if parts.port else "")


def _is_plain(value: Any) -> bool:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    return isinstance(value, list | tuple) and all(
        item is None or isinstance(item, str | int | float | bool) for item in value
    )


def withhold_values(value: Any) -> Any:
    """``value`` with its shape kept and every content-bearing leaf withheld."""
    if isinstance(value, dict):
        return {key: _withhold_member(str(key), item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [withhold_values(item) for item in value]
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return withheld(value)
    return withheld(json.dumps(value, default=str))


def _withhold_member(key: str, value: Any) -> Any:
    if key in _IDENTIFIER_KEYS and _is_plain(value):
        return value
    if key == "url" and isinstance(value, str) and not is_withheld(value) and "://" in value:
        return url_origin(value)
    return withhold_values(value)


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
        """Step metrics with the content of the call they describe withheld.

        Counts, timings, model and provider identity are kept; so is the
        structure of a tool call, its identifiers and its status.
        """
        if value is None or self.keeps_content:
            return value
        kept = dict(value)
        for key in _CONTENT_METRIC_KEYS:
            if key in kept:
                kept[key] = withhold_values(kept[key])
        safety = kept.get("content_safety")
        if isinstance(safety, list):
            kept["content_safety"] = [_without_finding_details(item) for item in safety]
        return kept

    def identifiers(self, value: dict[str, Any]) -> dict[str, Any]:
        """Only the identifying fields of a record spread into another."""
        if self.keeps_content:
            return value
        return {key: item for key, item in value.items() if key in _IDENTIFIER_KEYS and _is_plain(item)}

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
