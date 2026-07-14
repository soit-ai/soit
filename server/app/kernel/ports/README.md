# kernel/ports/

Port interfaces and policy enforcement points for all external systems:
LLM, tools, vector DB, storage, secrets.

Rules:
- All external calls must go through ports.
- Enforce timeout/retry/audit/rate-limit/egress consistently.
- Policy gateways share run-id resolution, timeout/retry wrapping, and trace error details via `common/policy.py`.
- Keep existing error codes, trace step types, cost units, and rate limit keys stable when migrating a gateway.
- Port interface method signatures are public within the backend. Prefer typed contract wrappers inside policy code without changing adapter-facing signatures.
