# Outbox Event Model

SOIT uses a transactional outbox to persist domain facts before dispatching side effects.
The outbox keeps runtime state changes and event publication in the same database
transaction so workers can retry dispatch without losing or duplicating committed facts.

## Core Tables

- `event_outbox`: pending and processed domain events.
- `event_consumer_checkpoint`: idempotency checkpoint per consumer and event.
- `dead_letter_events`: failed dispatch records that need operator review or replay.

## Event Envelope

Each outbox record stores the canonical event envelope used by runtime dispatch:

- `event_id`, `event_type`, and `event_version` identify the fact.
- `tenant_id`, `workspace_id`, `subject_type`, and `subject_id` scope the affected resource.
- `idempotency_key` defaults to `event_id` and gives consumers a stable deduplication key.
- `run_id`, `task_id`, `thread_id`, and `workflow_run_id` link runtime ledger records.
- `correlation_id` and `causation_id` preserve causal traceability.
- `producer`, `occurred_at`, and `payload` describe the source and data.

The envelope is intentionally small and stable. Product modules should emit facts through
the runtime/event helpers instead of writing directly to dispatch infrastructure.

## Delivery Semantics

Business state and its outbox row are committed in one request-level unit of work. A
dedicated dispatcher process claims rows with a bounded lease, invokes registered
consumers, and records a checkpoint for each successful `(consumer_name, event_id)`.
Failed attempts use bounded exponential backoff; abandoned leases can be reclaimed, and
rows that exceed the attempt limit remain in the terminal `failed` state for operator
inspection.

This provides at-least-once delivery with idempotent consumer checkpoints. Consumers that
call external systems must also use the event id or idempotency key at that external
boundary; the database checkpoint alone cannot make a remote side effect exactly once.

Production runs the dispatcher separately from the API process. Its Prometheus endpoint
exports backlog size, retry count, terminal failures, oldest pending age, delivery outcome,
and delivery latency.
