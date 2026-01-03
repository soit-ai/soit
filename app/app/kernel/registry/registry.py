""" registry

In-process registry for versioned artifacts (plugin/tool/workflow templates, etc.).

Why
- Provides a fast lookup layer for "what is available right now" in a tenant/workspace scope.
- Storage of truth is still the database and/or filesystem, but runtime needs an in-memory view.

Notes
- This registry is intentionally simple (thread-safe dict).
- Persistence/replication can be added later (Redis, DB, etc.) without changing call-sites.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Dict, Iterable, Optional, Tuple, List

from packaging.version import Version, InvalidVersion, parse as parse_version


@dataclass(frozen=True)
class ArtifactKey:
    """Uniquely identifies an artifact in a scope."""
    kind: str               # e.g. "plugin", "tool"
    tenant_id: str
    workspace_id: str
    name: str
    version: str


class Registry:
    """Thread-safe in-memory registry."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._items: Dict[ArtifactKey, Dict[str, Any]] = {}

    def register(
        self,
        *,
        kind: str,
        tenant_id: str,
        workspace_id: str,
        name: str,
        version: str,
        payload: Dict[str, Any],
    ) -> None:
        key = ArtifactKey(kind=kind, tenant_id=tenant_id, workspace_id=workspace_id, name=name, version=version)
        with self._lock:
            self._items[key] = payload

    def unregister(self, key: ArtifactKey) -> None:
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
    ) -> Optional[Dict[str, Any]]:
        key = ArtifactKey(kind=kind, tenant_id=tenant_id, workspace_id=workspace_id, name=name, version=version)
        with self._lock:
            return self._items.get(key)


def get_latest(
    self,
    *,
    kind: str,
    tenant_id: str,
    workspace_id: str,
    name: str,
) -> Optional[Tuple[ArtifactKey, Dict[str, Any]]]:
    """Get the latest version of an artifact by semantic version comparison.

    If versions are not valid semver, it falls back to lexicographic order.
    """
    items = self.list(kind=kind, tenant_id=tenant_id, workspace_id=workspace_id, name=name)
    if not items:
        return None

    def _key(item):
        k, _ = item
        try:
            return parse_version(k.version)
        except Exception:
            return k.version

    return sorted(items, key=_key, reverse=True)[0]
    def list(
        self,
        *,
        kind: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> List[Tuple[ArtifactKey, Dict[str, Any]]]:
        with self._lock:
            out: List[Tuple[ArtifactKey, Dict[str, Any]]] = []
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

    def clear_scope(self, *, tenant_id: str, workspace_id: str) -> None:
        with self._lock:
            keys = [k for k in self._items.keys() if k.tenant_id == tenant_id and k.workspace_id == workspace_id]
            for k in keys:
                self._items.pop(k, None)
