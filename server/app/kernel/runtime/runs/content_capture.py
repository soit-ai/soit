""" content_capture

What a run records of the content it handled.

``full`` keeps run and step summaries, previews and error messages as the
runtime writes them. ``metadata_only`` keeps none of that text: each value is
replaced by its length and a SHA-256 prefix, so two runs can still be told to
have handled the same input without either keeping it. Statuses, codes, token
counts, costs and timings are recorded either way.

The mode is a workspace setting that an API key can tighten but not loosen.
It is resolved when a request authenticates and travels in the request
context, including in contexts that workers store and resume. A worker that
builds a context of its own has no mode in it; the trace writer then looks the
workspace setting up through a lookup the wiring registers.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

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


def withheld(value: str) -> str:
    """A marker that says how much text there was and which, but not what."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"[withheld: {len(value)} chars, sha256:{digest}]"


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
