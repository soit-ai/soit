""" deps

Runtime accessors for the in-process Registry.
"""

from __future__ import annotations

from app.kernel.registry.registry import Registry

_registry_singleton: Registry | None = None


def get_registry() -> Registry:
    global _registry_singleton
    if _registry_singleton is None:
        _registry_singleton = Registry()
    return _registry_singleton


def reset_registry() -> None:
    global _registry_singleton
    _registry_singleton = None
