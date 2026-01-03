"""app.wiring

Application composition and dependency wiring.

This module is the only place that should bind:
- kernel gateway interfaces -> adapters implementations
- domain services -> repositories -> db/session
"""

from .container import Container, get_container, reset_container

__all__ = ["Container", "get_container", "reset_container"]
