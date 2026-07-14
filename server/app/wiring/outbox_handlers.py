"""Composition root: register outbox consumers on the process-wide registry."""

from __future__ import annotations

from app.kernel.events.registry import OutboxHandlerRegistry
from app.kernel.runtime.db.models.events import EventOutbox

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

    from app.kernel.runtime.runs.events import RunEventType
    from app.kernel.runtime.runs.handlers import handle_run_created_outbox
    from app.kernel.runtime.tasks.events import TaskEventType
    from app.kernel.runtime.tasks.on_task_outbox import handle_task_runtime_outbox

    reg.register(RunEventType.CREATED, "runtime.run_created.builtin", handle_run_created_outbox)

    from app.kernel.observe.event_types import ObserveEventType
    from app.kernel.observe.handlers.execution_observe import (
        handle_cost_recorded_observe,
        handle_run_created_observe,
        handle_run_status_updated_observe,
        handle_step_created_observe,
        handle_step_status_updated_observe,
        handle_task_lifecycle_observe,
        handle_workflow_node_observe,
    )

    reg.register(
        RunEventType.CREATED,
        "observe.run_created.trace_metrics",
        handle_run_created_observe,
    )
    reg.register(
        ObserveEventType.COST_RECORDED,
        "observe.cost.metrics",
        handle_cost_recorded_observe,
    )
    reg.register(
        ObserveEventType.RUN_STATUS_UPDATED,
        "observe.run_status.trace_metrics",
        handle_run_status_updated_observe,
    )
    reg.register(
        ObserveEventType.STEP_CREATED,
        "observe.step_created.trace_metrics",
        handle_step_created_observe,
    )
    reg.register(
        ObserveEventType.STEP_STATUS_UPDATED,
        "observe.step_status.trace_metrics",
        handle_step_status_updated_observe,
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
            f"observe.task.{_name}",
            handle_task_lifecycle_observe,
        )

    from app.modules.observe.domain.approval_events import ApprovalEventType
    from app.modules.observe.handlers.on_approval_outbox import (
        handle_approval_approved_outbox,
        handle_approval_rejected_outbox,
        handle_approval_requested_outbox,
    )

    reg.register(ApprovalEventType.REQUESTED, "observe.approval.requested", handle_approval_requested_outbox)
    reg.register(ApprovalEventType.APPROVED, "observe.approval.approved", handle_approval_approved_outbox)
    reg.register(ApprovalEventType.REJECTED, "observe.approval.rejected", handle_approval_rejected_outbox)

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
        "observe.workflow.node_completed",
        handle_workflow_node_observe,
    )
    reg.register(
        WorkflowEventType.NODE_FAILED,
        "observe.workflow.node_failed",
        handle_workflow_node_observe,
    )
