"""events

Kernel event bus primitives.
"""

from app.kernel.events.bus import Event, EventBus, InMemoryEventBus
from app.kernel.events.checkpoint import ConsumerCheckpointRepository
from app.kernel.events.envelope import DEFAULT_EVENT_VERSION, DomainEventEnvelope
from app.kernel.events.outbox_models import DeadLetterEvent, EventConsumerCheckpoint, EventOutbox
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.redis_bus import RedisEventBus
from app.kernel.events.registry import OutboxHandlerRegistry, RegisteredOutboxHandler

__all__ = [
    "ConsumerCheckpointRepository",
    "DEFAULT_EVENT_VERSION",
    "DeadLetterEvent",
    "DomainEventEnvelope",
    "Event",
    "EventBus",
    "EventConsumerCheckpoint",
    "EventOutbox",
    "InMemoryEventBus",
    "OutboxHandlerRegistry",
    "OutboxRepository",
    "RedisEventBus",
    "RegisteredOutboxHandler",
]
