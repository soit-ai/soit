# kernel/events/

Transactional outbox, in-process event bus, and dispatcher support.

Rules:
- `DomainEventEnvelope.event_version` is the payload contract version, not a database schema version.
- Event outbox SQLModel table classes live in `kernel/runtime/db/models/events.py`; this package owns event bus, publisher, dispatcher, and registry logic.
- Kernel-owned `task.*`, `run.*`, `response.*`, and `approval.*` event types must be registered in `payload_registry.py`.
- `OutboxPublisher` resolves registered payload versions before enqueueing.
- `OutboxDispatcher` validates registered event versions before invoking handlers.
- Unknown event types keep the compatibility path and are not blocked by the registry.
- Adding a new kernel event type requires a registry entry and a focused dispatcher or publisher test.
