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

    from app.kernel.runtime.events import RunEventType, TaskEventType
    from app.kernel.runtime.handlers.on_run_created import handle_run_created_outbox
    from app.kernel.runtime.handlers.on_task_outbox import handle_task_runtime_outbox

    reg.register(RunEventType.CREATED, "runtime.run_created.builtin", handle_run_created_outbox)

    for _name, event_type in (
        ("created", TaskEventType.CREATED),
        ("started", TaskEventType.STARTED),
        ("completed", TaskEventType.COMPLETED),
        ("failed", TaskEventType.FAILED),
        ("retried", TaskEventType.RETRIED),
        ("checkpointed", TaskEventType.CHECKPOINTED),
    ):
        reg.register(
            event_type,
            f"runtime.task.builtin.{_name}",
            handle_task_runtime_outbox,
        )

    from app.modules.observability.domain.approval_events import ApprovalEventType
    from app.modules.observability.handlers.on_approval_outbox import (
        handle_approval_approved_outbox,
        handle_approval_rejected_outbox,
        handle_approval_requested_outbox,
    )

    reg.register(ApprovalEventType.REQUESTED, "observability.approval.requested", handle_approval_requested_outbox)
    reg.register(ApprovalEventType.APPROVED, "observability.approval.approved", handle_approval_approved_outbox)
    reg.register(ApprovalEventType.REJECTED, "observability.approval.rejected", handle_approval_rejected_outbox)
