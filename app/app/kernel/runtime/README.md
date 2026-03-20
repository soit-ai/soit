# kernel/runtime/

Runtime Core target package.

Planned subpackages:

- `core/`: execution entry points and shared runtime services
- `contracts/`: stable runtime enums, value objects, and interfaces
- `executors/`: capability-level executors
- `orchestrators/`: run/task orchestration
- `checkpoints/`: retry/resume persistence contracts

Guardrails:

- no dependency on retired legacy platform modules
- no business-domain logic
- no transport-specific logic
