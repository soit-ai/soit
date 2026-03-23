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

    from app.kernel.observability.event_types import ObservabilityEventType
    from app.kernel.observability.handlers.execution_observability import (
        handle_cost_recorded_observability,
        handle_run_created_observability,
        handle_run_status_updated_observability,
        handle_step_created_observability,
        handle_step_status_updated_observability,
        handle_task_lifecycle_observability,
        handle_workflow_node_observability,
    )

    reg.register(
        RunEventType.CREATED,
        "observability.run_created.trace_metrics",
        handle_run_created_observability,
    )
    reg.register(
        ObservabilityEventType.COST_RECORDED,
        "observability.cost.metrics",
        handle_cost_recorded_observability,
    )
    reg.register(
        ObservabilityEventType.RUN_STATUS_UPDATED,
        "observability.run_status.trace_metrics",
        handle_run_status_updated_observability,
    )
    reg.register(
        ObservabilityEventType.STEP_CREATED,
        "observability.step_created.trace_metrics",
        handle_step_created_observability,
    )
    reg.register(
        ObservabilityEventType.STEP_STATUS_UPDATED,
        "observability.step_status.trace_metrics",
        handle_step_status_updated_observability,
    )

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
        reg.register(
            event_type,
            f"observability.task.{_name}",
            handle_task_lifecycle_observability,
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

    from app.modules.workflow.domain.workflow_events import WorkflowEventType
    from app.modules.workflow.handlers.on_workflow_node_outbox import (
        handle_workflow_node_completed_outbox,
        handle_workflow_node_failed_outbox,
    )

    reg.register(
        WorkflowEventType.NODE_COMPLETED,
        "workflow.node_completed.builtin",
        handle_workflow_node_completed_outbox,
    )
    reg.register(
        WorkflowEventType.NODE_FAILED,
        "workflow.node_failed.builtin",
        handle_workflow_node_failed_outbox,
    )
    reg.register(
        WorkflowEventType.NODE_COMPLETED,
        "observability.workflow.node_completed",
        handle_workflow_node_observability,
    )
    reg.register(
        WorkflowEventType.NODE_FAILED,
        "observability.workflow.node_failed",
        handle_workflow_node_observability,
    )
