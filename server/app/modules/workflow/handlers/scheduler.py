"""Workflow scheduler outbox consumers (design spec §11.2).

DAG execution scheduling remains in WorkflowExecutor; these handlers update
`workflow_runs` counters and optional linear next-node chaining for tests / simple graphs.
"""

from __future__ import annotations

from app.modules.workflow.handlers.on_workflow_node_outbox import (
    handle_workflow_node_completed_outbox,
    handle_workflow_node_failed_outbox,
)

__all__ = [
    "handle_workflow_node_completed_outbox",
    "handle_workflow_node_failed_outbox",
]
