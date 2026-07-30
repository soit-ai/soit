"""Scope vocabulary for programmatic credentials.

A scope is a ceiling, never an elevation: the effective permission of a request
is the credential's scope intersected with the caller's role. A key scoped to
``read`` cannot write even when its owner is a workspace Owner.
"""

from __future__ import annotations

SCOPE_READ = "read"
SCOPE_WRITE = "write"
SCOPE_ADMIN = "admin"

ALL_SCOPES: frozenset[str] = frozenset({SCOPE_READ, SCOPE_WRITE, SCOPE_ADMIN})

_IMPLIED: dict[str, frozenset[str]] = {
    SCOPE_READ: frozenset({SCOPE_READ}),
    SCOPE_WRITE: frozenset({SCOPE_READ, SCOPE_WRITE}),
    SCOPE_ADMIN: frozenset({SCOPE_READ, SCOPE_WRITE, SCOPE_ADMIN}),
}
"""Broader scopes imply narrower ones, so callers need not list every level."""


def normalize_scopes(scopes: object) -> frozenset[str]:
    """Expand a scope list into every scope it grants.

    Unknown entries are dropped rather than trusted: an unrecognised scope must
    never widen access.
    """
    if not isinstance(scopes, list | tuple | set | frozenset):
        return frozenset()
    granted: set[str] = set()
    for entry in scopes:
        name = str(entry or "").strip().lower()
        granted |= _IMPLIED.get(name, frozenset())
    return frozenset(granted)


def unknown_scopes(scopes: object) -> list[str]:
    """Return the entries that are not part of the vocabulary."""
    if not isinstance(scopes, list | tuple | set | frozenset):
        return []
    return sorted(
        {
            str(entry or "").strip().lower()
            for entry in scopes
            if str(entry or "").strip().lower() not in ALL_SCOPES
        }
    )
