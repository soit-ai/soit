# modules/entrypoints/

API entrypoints (FastAPI routers/controllers).

Rules:
- No heavy business logic.
- Use domain services.
- Perform policy checks early.
- Ensure run/step tracing for execution endpoints.
