# adapters/

Replaceable implementations for gateways (Milvus/MinIO/OpenAI/etc).

Rules:
- Implement gateway interfaces defined in `kernel/gateways/*`.
- Do NOT implement business logic.
- Keep dependencies minimal (easy to swap).
