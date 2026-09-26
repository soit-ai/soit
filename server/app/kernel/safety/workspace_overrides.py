"""Per-workspace overrides of the deployment's content safety actions.

A workspace may set what the built-in rules do with personal data entering
and leaving the runtime. The rules read those settings through a lookup the
wiring registers, given the session of the run they inspect for when there is
one, so the kernel never reaches into the identity module.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

WorkspacePiiLookup = Callable[[Any, str, str], Awaitable[dict[str, str | None]]]
"""(session or None, tenant_id, workspace_id) -> {"inbound": ..., "outbound": ...}."""

_workspace_pii_lookup: WorkspacePiiLookup | None = None


def register_workspace_pii_lookup(lookup: WorkspacePiiLookup) -> None:
    global _workspace_pii_lookup
    _workspace_pii_lookup = lookup


def reset_workspace_pii_lookup() -> None:
    global _workspace_pii_lookup
    _workspace_pii_lookup = None


def get_workspace_pii_lookup() -> WorkspacePiiLookup | None:
    return _workspace_pii_lookup
