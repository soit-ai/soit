"""Workflow execution event type constants for transactional outbox (B3/B6)."""


class WorkflowEventType:
    """workflow.* domain facts (checklist §6 / §11.2)."""

    NODE_COMPLETED = "workflow.node.completed"
    NODE_FAILED = "workflow.node.failed"
