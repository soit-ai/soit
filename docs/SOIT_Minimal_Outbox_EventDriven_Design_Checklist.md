SOIT Minimal Outbox Event-Driven Design Checklist

Version: Minimal / Converged Edition
Scope: Keep the design lean. Use Outbox for reliable event publishing. Avoid over-designing summary/projection tables in Phase 1.

==================================================
1. Design Goals
==================================================

The target architecture for SOIT should be:
- Control plane remains synchronous
- Execution plane becomes gradually event-driven
- Use Outbox instead of introducing MQ in Phase 1
- Keep projections minimal
- Prefer extending core business tables over creating many summary tables

This design is intended for the current SOIT stage:
- Runtime / Run / Task mainline is still being consolidated
- Workflow and Approval are important but should not over-expand
- Event semantics need to be stabilized before introducing heavier infrastructure

==================================================
2. Architectural Principles
==================================================

2.1 Keep synchronous for control plane
The following should remain synchronous:
- Agent CRUD
- Workflow CRUD
- Knowledge Base CRUD
- Skill / Plugin / MCP management
- Secret / Policy / Model configuration
- Validation endpoints
- Query/list/detail APIs

2.2 Event-drive the execution plane
The following should gradually become event-driven:
- Run execution lifecycle
- Task execution lifecycle
- Workflow node scheduling
- Approval / HITL resume flow
- Trace / Audit / Cost recording

2.3 Use Outbox first
Phase 1 should use:
- Business transaction
- Outbox write in the same transaction
- Local dispatcher/worker consumes outbox

Do not introduce MQ in Phase 1.

2.4 Keep read models minimal
Do not build a large projection system at the beginning.
Preferred order:
- First: extend core tables with necessary query fields
- Second: add only one core projection if really needed
- Third: add more projections only when real query complexity appears

==================================================
3. Minimal Target Architecture
==================================================

Recommended minimal architecture:

API / Admin / Web
  -> Application Service
  -> Domain State Change
  -> Write business tables + event_outbox in one transaction
  -> Local Outbox Dispatcher Worker
  -> Consumers / Handlers
  -> Update business state / side effects

Main idea:
- API should not orchestrate long chains directly
- API triggers state changes only
- Outbox event triggers downstream handling
- Trace / Audit / Cost should subscribe instead of being deeply embedded in mainline execution

==================================================
4. Minimal Module Structure
==================================================

Recommended additions under current backend structure:

app/kernel/events/
  base.py
  envelope.py
  outbox_models.py
  outbox_repo.py
  dispatcher.py
  registry.py
  idempotency.py
  publisher.py

app/kernel/runtime/events.py
app/kernel/runtime/handlers/

app/modules/workflow/events.py
app/modules/workflow/handlers/

app/modules/approvals/events.py
app/modules/approvals/handlers/

app/kernel/trace/handlers/
app/kernel/observability/handlers/

Notes:
- Do not create too many abstraction layers at first
- Registry + dispatcher + simple handlers are enough for Phase 1
- Keep event definitions close to their modules

==================================================
5. Minimal Event Model
==================================================

Suggested base fields for domain events:
- event_id
- event_type
- event_version
- tenant_id
- subject_type
- subject_id
- run_id
- task_id
- thread_id
- workflow_run_id
- correlation_id
- causation_id
- producer
- occurred_at
- payload

Rules:
- correlation_id: use run_id as default for one execution chain
- causation_id: the event_id that directly caused this event

Do not overcomplicate event payloads in Phase 1.
Keep payloads concise and focused.

==================================================
6. Minimal Event Types for Phase 1
==================================================

Only define the event types that are immediately useful.

6.1 Runtime / Run / Task
- run.created
- run.started
- run.completed
- run.failed
- run.cancelled

- task.created
- task.started
- task.completed
- task.failed
- task.retried
- task.checkpointed

6.2 Workflow
- workflow.run.started
- workflow.node.ready
- workflow.node.started
- workflow.node.completed
- workflow.node.failed
- workflow.run.completed

6.3 Approval
- approval.requested
- approval.approved
- approval.rejected

6.4 Observability-side subscriptions
These are not necessarily standalone event types, but consumers should subscribe to runtime/workflow/approval events for:
- trace
- audit
- usage
- cost

Do not define a huge event catalog in Phase 1.

==================================================
7. Minimal Database Design
==================================================

7.1 Required new table: event_outbox

Recommended fields:
- id
- event_id
- event_type
- event_version
- tenant_id
- subject_type
- subject_id
- run_id
- task_id
- thread_id
- workflow_run_id
- correlation_id
- causation_id
- producer
- payload_json
- headers_json
- status
- available_at
- attempt_count
- last_error
- occurred_at
- created_at
- processed_at

Recommended status values:
- pending
- processing
- done
- failed

Recommended indexes:
- (status, available_at)
- (correlation_id)
- (subject_type, subject_id)
- (run_id)
- (workflow_run_id)

7.2 Required new table: event_consumer_checkpoint

Recommended fields:
- id
- consumer_name
- event_id
- processed_at
- result
- error_message

Unique key:
- (consumer_name, event_id)

Purpose:
- ensure idempotent consumption
- avoid duplicate handling when dispatcher retries

7.3 Optional table: dead_letter_events

Recommended fields:
- id
- event_id
- event_type
- consumer_name
- payload_json
- error_message
- failed_at

This table is optional in the very first cut, but recommended.

==================================================
8. Minimal Changes to Existing Business Tables
==================================================

Instead of adding many summary tables, first extend core business tables.

8.1 runs table
Add only the fields that are directly useful for read/query needs:
- current_task_id
- last_error
- started_at
- ended_at
- updated_at

Optional fields if already needed:
- total_tasks
- completed_tasks
- estimated_cost

Rationale:
- Supports most run list and run detail header queries
- Avoids introducing run_summary too early

8.2 workflow_runs table
Suggested additional fields:
- total_nodes
- completed_nodes
- failed_nodes
- waiting_nodes
- updated_at

Rationale:
- Supports monitor pages without needing a separate summary table immediately

8.3 approvals table
If current approvals table already has enough fields, do not add approval_summary.
Key useful fields should include:
- run_id
- task_id
- status
- assignee_id
- requested_at
- decided_at
- updated_at

==================================================
9. Summary / Projection Strategy
==================================================

9.1 Do not build a full summary layer now
Avoid creating all of the following in Phase 1:
- task_summary
- workflow_run_summary
- ingest_task_summary
- approval_summary
- usage_summary
- cost_summary
- trace_summary

9.2 Preferred minimal strategy
Choose one of the two:

Option A: No summary tables in Phase 1
- Extend runs
- Extend workflow_runs
- Query approvals directly from approvals table

Option B: Only one summary table in Phase 1 if needed
- Add run_summary only
- Keep all other modules on core tables

9.3 Recommended decision for current SOIT
Recommended now:
- Prefer Option A first
- Only add run_summary if runs list / observability overview becomes too query-heavy

==================================================
10. Minimal Dispatcher Design
==================================================

Dispatcher flow:
1. Pull pending outbox events whose available_at <= now
2. Claim them as processing
3. Resolve handlers by event_type
4. Execute handlers one by one
5. Before handler execution, check event_consumer_checkpoint
6. If already processed, skip
7. If success, write checkpoint
8. If all handlers succeed, mark outbox row done
9. If failed, increment attempt_count and retry later
10. If beyond threshold, optionally move to dead letter

Do not build a very complicated dispatcher framework in Phase 1.
Simple batch polling is sufficient.

==================================================
11. Minimal Consumers for Phase 1
==================================================

Implement only the consumers needed for the first execution chain.

11.1 Runtime execution consumer
Handles:
- run.created
- task.created / task lifecycle related events as needed

Responsibilities:
- start run execution
- advance task state
- trigger next state transition

11.2 Workflow scheduler consumer
Handles:
- workflow.node.completed
- workflow.node.failed

Responsibilities:
- schedule next node(s)
- mark workflow run completed when terminal condition is met

11.3 Approval consumer
Handles:
- approval.approved
- approval.rejected

Responsibilities:
- resume waiting run or node
- mark terminated flow on rejection

11.4 Observability consumers
Subscribe to execution events and record:
- trace
- audit
- usage
- cost

These should be side-effect subscribers, not embedded into the core execution code path.

==================================================
12. Phase 1 Scope
==================================================

Only implement these chains in Phase 1:
- Run / Task main execution chain
- Workflow node scheduling chain
- Approval waiting / resume chain
- Trace / Audit / Cost subscribers

Do not include in Phase 1:
- MQ
- full multi-agent orchestration
- heavy projection system
- complete knowledge ingest event pipeline
- complete MCP event lifecycle

==================================================
13. Phase 1 Task Breakdown
==================================================

13.1 Infrastructure
- add DomainEvent base model
- add event_outbox table
- add event_consumer_checkpoint table
- add optional dead_letter_events table
- add outbox repository
- add dispatcher worker
- add handler registry
- add idempotency helper

13.2 Runtime mainline
- emit run.created / run.started / run.completed / run.failed
- emit task lifecycle events
- make execution flow transition by events rather than long synchronous call chains

13.3 Workflow
- emit workflow node lifecycle events
- add simple scheduler consumer
- update workflow_runs counters directly or through consumer logic

13.4 Approval
- emit approval.requested / approval.approved / approval.rejected
- add waiting_approval resume path

13.5 Observability
- subscribe to execution events
- move trace / audit / usage / cost recording to consumers where practical

13.6 Database field updates
- extend runs
- extend workflow_runs
- verify approvals fields are sufficient

==================================================
14. Constraints
==================================================

Keep these constraints during implementation:
- API layer must not orchestrate long execution chains
- cross-module side effects should prefer event subscribers
- all consumers must be idempotent
- use outbox before MQ
- avoid building many summary tables too early
- avoid event explosion; define only meaningful business events
- events describe facts, not imperative commands

==================================================
15. Recommended Final Decision
==================================================

For the current SOIT stage, the recommended minimal design is:

1. Use Outbox, not MQ
2. Add only these new persistence pieces:
   - event_outbox
   - event_consumer_checkpoint
   - optional dead_letter_events

3. Do not create a full summary/projection system yet
4. First extend:
   - runs
   - workflow_runs
   - approvals if needed

5. Only add run_summary later if real query pressure appears
6. Focus Phase 1 on:
   - Run / Task
   - Workflow
   - Approval
   - Trace / Audit / Cost subscriptions

This is the most practical balance for SOIT now:
- enough event-driven structure to evolve the platform
- low enough complexity to keep implementation manageable
- no premature expansion of read models or message infrastructure

