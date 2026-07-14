# kernel/runtime/

Runtime is the centralized package for kernel execution state and persistence state.

Subpackages:

- `db/models/`: the only allowed location for SQLModel table classes owned by kernel runtime.
- `tasks/`: task repository, service, schemas, status policy, task events, and task outbox helpers.
- `threads/`: thread repository, service, schemas, and protocols.
- `runs/`: run, step, artifact, cost, trace writer, exporter, and run event handlers.
- `responses/`: response repository, service, schemas, and projection orchestrator.
- `common/`: runtime-only shared helpers such as pagination and idempotency repository support.

Guardrails:

- no dependency on `app.modules`, `app.api`, `app.adapters`, or `app.infra`
- no business-domain logic
- no transport-specific logic
- no SQLModel table class outside `runtime/db/models/`
- task status transitions use `tasks/status.py` as the single policy source
- runtime services depend on repository protocols; SQLModel repositories are default wiring, not service contracts
- outbox task events must use registered payload versions from `kernel/events/payload_registry.py`
