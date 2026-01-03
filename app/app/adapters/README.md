# adapters/

Replaceable implementations for ports (Milvus/MinIO/OpenAI/etc).

Rules:
- Implement port interfaces defined in `kernel/ports/*`.
- Do NOT implement business logic.
- Keep dependencies minimal (easy to swap).
