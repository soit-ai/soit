"""Outbox consumers for runtime execution (Wave B+)."""

from app.kernel.runtime.handlers.on_run_created import handle_run_created_outbox

__all__ = ["handle_run_created_outbox"]
