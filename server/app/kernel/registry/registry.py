"""registry

In-process registry for versioned artifacts (plugin/tool/workflow templates, etc.).

Why
- Provides a fast lookup layer for "what is available right now" in a tenant/workspace scope.
- Storage of truth is still the database and/or filesystem, but runtime needs an in-memory view.

Notes
- This registry is intentionally simple (thread-safe dict).
- Persistence/replication can be added later (Redis, DB, etc.) without changing call-sites.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass
from threading import RLock
from typing import Any

from packaging.version import parse as parse_version


@dataclass(frozen=True)
class ArtifactKey:
    """Unique key for a versioned artifact."""

    kind: str
    tenant_id: str
    workspace_id: str
    name: str
    version: str


class Registry:
    """Thread-safe in-memory registry."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[ArtifactKey, dict[str, Any]] = {}

    def register(
        self,
        *,
        kind: str,
        tenant_id: str,
        workspace_id: str,
        name: str,
        version: str,
        payload: dict[str, Any],
    ) -> None:
        """Register or overwrite an artifact payload."""
        key = ArtifactKey(
            kind=kind,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name=name,
            version=version,
        )
        with self._lock:
            self._items[key] = payload

    def unregister(self, key: ArtifactKey) -> None:
        """Remove an artifact from registry."""
        with self._lock:
            self._items.pop(key, None)

    def get(
        self,
        *,
        kind: str,
        tenant_id: str,
        workspace_id: str,
        name: str,
        version: str,
    ) -> tuple[ArtifactKey, dict[str, Any]] | None:
        """Get a single artifact (key, payload) by exact version."""
        key = ArtifactKey(
            kind=kind,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name=name,
            version=version,
        )
        with self._lock:
            payload = self._items.get(key)
            if payload is None:
                return None
            return key, payload

    def list(
        self,
        *,
        kind: str | None = None,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        name: str | None = None,
    ) -> builtins.list[tuple[ArtifactKey, dict[str, Any]]]:
        """List artifacts filtered by optional fields."""
        with self._lock:
            out: list[tuple[ArtifactKey, dict[str, Any]]] = []
            for k, v in self._items.items():
                if kind is not None and k.kind != kind:
                    continue
                if tenant_id is not None and k.tenant_id != tenant_id:
                    continue
                if workspace_id is not None and k.workspace_id != workspace_id:
                    continue
                if name is not None and k.name != name:
                    continue
                out.append((k, v))
            return out

    def get_latest(
        self,
        *,
        kind: str,
        tenant_id: str,
        workspace_id: str,
        name: str,
    ) -> tuple[ArtifactKey, dict[str, Any]] | None:
        """Get latest version by semantic version comparison.

        If versions are not valid semver/PEP440, it falls back to lexicographic order.
        """
        items = self.list(kind=kind, tenant_id=tenant_id, workspace_id=workspace_id, name=name)
        if not items:
            return None

        def _key(item: tuple[ArtifactKey, dict[str, Any]]):
            k, _ = item
            try:
                return parse_version(k.version)
            except Exception:
                return k.version

        return sorted(items, key=_key, reverse=True)[0]

    def clear_scope(self, tenant_id: str, workspace_id: str) -> None:
        """Clear all artifacts for a tenant/workspace scope."""
        with self._lock:
            keys = [
                k for k in self._items.keys()
                if k.tenant_id == tenant_id and k.workspace_id == workspace_id
            ]
            for k in keys:
                self._items.pop(k, None)
