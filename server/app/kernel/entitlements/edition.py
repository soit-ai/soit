"""The edition this process runs as, resolved once at startup.

The composition root resolves it from the license file and the installed
extension packages and records it here, so code that reports on the
deployment (diagnostics, the license heartbeat) reads one answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.kernel.entitlements.license import LicenseState, LicenseStatus


@dataclass(frozen=True)
class ExtensionMount:
    name: str
    status: str
    """``mounted`` or ``failed``."""
    error: str | None = None


@dataclass(frozen=True)
class EditionState:
    edition: str
    license: LicenseState
    enabled_features: frozenset[str]
    ignored_entitlements: frozenset[str] = frozenset()
    """Keys the license grants that no installed feature registry defines."""
    extensions: tuple[ExtensionMount, ...] = field(default_factory=tuple)


_current: EditionState | None = None


def current_edition() -> EditionState:
    """The resolved edition, or plain Community before startup resolved one."""
    if _current is not None:
        return _current
    from app.kernel.entitlements.features import resolve_enabled_features

    return EditionState(
        edition="community",
        license=LicenseState(LicenseStatus.ABSENT),
        enabled_features=resolve_enabled_features(edition="community"),
    )


def set_current_edition(state: EditionState) -> None:
    global _current
    _current = state
