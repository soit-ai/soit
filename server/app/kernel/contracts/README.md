# kernel/contracts/

Cross-module stable types and interfaces.

Examples:
- RequestContext
- Ref models (ModelRef/ToolRef/etc)
- ExecutionPlan / ToolCall / ToolResult
- VectorQuery / StorageObjectRef

Rules:
- No DB models.
- Keep contract changes explicit and versioned.
- Prefer additive dataclass contracts over loose dicts for new kernel-facing APIs.
