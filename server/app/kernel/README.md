# kernel/

SOIT stable core. Kernel MUST NOT depend on `modules/`.

Key responsibilities:
- scope & identity primitives
- execution semantics
- runtime persistence for tasks, threads, runs, and responses
- ports and security enforcement
- spec schemas and registry mechanisms

Boundary rules:
- `kernel/` may depend on `app.kernel`, `app.settings`, standard library, and third-party libraries.
- `kernel/` must not import `app.modules`, `app.api`, `app.adapters`, or `app.infra`.
- Kernel extension points that need product or infrastructure data must use provider interfaces registered from `wiring/`.
- Runtime task status transitions are centralized in `kernel/runtime/tasks/status.py`.
- SQLModel table classes are only defined under `kernel/runtime/db/models/`.
- Runtime state code is grouped under `kernel/runtime/tasks`, `kernel/runtime/threads`, `kernel/runtime/runs`, and `kernel/runtime/responses`.

Allowed extension points:
- Providers: kernel-owned protocols for scoped resource grants and egress policy. Concrete providers are registered only from `app/wiring`.
- Ports: external system access goes through port interfaces plus policy gateways. Shared timeout/retry/error/run-id behavior lives in `kernel/ports/common/policy.py`.
- Repository protocols: runtime services depend on protocol-shaped persistence contracts while existing SQLModel repositories remain the default implementations.
- Event registry: new kernel-owned `task.*`, `run.*`, `response.*`, and `approval.*` outbox event types must be registered in `kernel/events/payload_registry.py`.

Compatibility rules:
- Do not change HTTP, WebSocket, SSE, database table, or JSON column wire shape from inside kernel refactors.
- Add typed contracts incrementally. Existing dict inputs/outputs remain accepted unless a public API version explicitly changes.
