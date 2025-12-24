# kernel/gateways/

Gateway interfaces and policy enforcement points for all external systems:
LLM, tools, vector DB, storage, secrets.

Rules:
- All external calls must go through gateways.
- Enforce timeout/retry/audit/rate-limit/egress consistently.
