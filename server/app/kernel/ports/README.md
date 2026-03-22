# kernel/ports/

Port interfaces and policy enforcement points for all external systems:
LLM, tools, vector DB, storage, secrets.

Rules:
- All external calls must go through ports.
- Enforce timeout/retry/audit/rate-limit/egress consistently.
