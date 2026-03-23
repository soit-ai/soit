"""Domain event type strings for observability-side outbox facts (Wave C)."""


class ObservabilityEventType:
    """Emitted alongside authoritative trace rows for async metrics/projection."""

    COST_RECORDED = "cost.recorded"
    RUN_STATUS_UPDATED = "run.status.updated"
    STEP_CREATED = "step.created"
    STEP_STATUS_UPDATED = "step.status.updated"
