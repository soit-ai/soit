"""Composition root: register outbox consumers on the process-wide registry."""

from __future__ import annotations

from app.kernel.events.outbox_models import EventOutbox
from app.kernel.events.registry import OutboxHandlerRegistry

_registry = OutboxHandlerRegistry()
_handlers_registered = False


def get_outbox_registry() -> OutboxHandlerRegistry:
    """Shared registry used by the API outbox background worker."""
    return _registry


def register_outbox_handlers() -> None:
    """Idempotent registration (call once at process startup before dispatcher loop)."""
    global _handlers_registered
    if _handlers_registered:
        return
    _handlers_registered = True

    reg = _registry

    def _builtin_smoke_handler(_db, _row: EventOutbox) -> None:
        """Placeholder consumer for `outbox.smoke` (tests / health wiring)."""
        return None

    reg.register("outbox.smoke", "builtin.smoke", _builtin_smoke_handler)
