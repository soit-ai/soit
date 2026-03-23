"""Runtime execution event type constants (transactional outbox)."""


class RunEventType:
    """run.* domain facts (checklist §6.1)."""

    CREATED = "run.created"


class TaskEventType:
    """task.* domain facts (checklist §6.1)."""

    CREATED = "task.created"
    STARTED = "task.started"
    COMPLETED = "task.completed"
    FAILED = "task.failed"
    RETRIED = "task.retried"
    CHECKPOINTED = "task.checkpointed"
