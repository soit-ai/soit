"""Domain event type strings for observability-side outbox facts (Wave C)."""


class ObservabilityEventType:
    """Emitted alongside authoritative trace rows for async metrics/projection."""

    COST_RECORDED = "cost.recorded"
