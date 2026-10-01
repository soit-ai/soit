"""Knowledge connector registry wiring.

The one place that decides which connector kinds a deployment offers. Adding a
connector means writing its module under ``app.adapters.connectors`` and
registering it here.
"""

from __future__ import annotations

from functools import lru_cache

from app.adapters.connectors import s3, web
from app.kernel.ports.connectors import ConnectorRegistry


def build_connector_registry() -> ConnectorRegistry:
    """A fresh registry holding every built-in connector kind."""
    registry = ConnectorRegistry()
    registry.register(s3.REGISTRATION)
    registry.register(web.REGISTRATION)
    return registry


@lru_cache(maxsize=1)
def get_connector_registry() -> ConnectorRegistry:
    """The process-wide registry; connectors hold no state, so one is shared."""
    return build_connector_registry()
