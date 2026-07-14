"""events

Kernel event bus primitives.
"""

from app.kernel.events.bus import Event, EventBus, InMemoryEventBus
from app.kernel.events.checkpoint import (
    ConsumerCheckpointRepository,
    try_claim_consumer_slot,
)
from app.kernel.events.dispatcher import OutboxDispatcher, OutboxDispatcherService
from app.kernel.events.envelope import DEFAULT_EVENT_VERSION, DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.kernel.events.redis_bus import RedisEventBus
from app.kernel.events.registry import OutboxHandlerRegistry, RegisteredOutboxHandler
from app.kernel.runtime.db.models.events import EventConsumerCheckpoint, EventOutbox

__all__ = [
    "ConsumerCheckpointRepository",
    "DEFAULT_EVENT_VERSION",
    "OutboxDispatcher",
    "OutboxDispatcherService",
    "DomainEventEnvelope",
    "Event",
    "EventBus",
    "EventConsumerCheckpoint",
    "EventOutbox",
    "InMemoryEventBus",
    "OutboxHandlerRegistry",
    "OutboxPublisher",
    "OutboxRepository",
    "RedisEventBus",
    "RegisteredOutboxHandler",
    "try_claim_consumer_slot",
]
