# modules/entrypoints/bot/

Entrypoint: **bot**.

Place:
- routes.py (or router.py)
- dependencies.py (ctx injection, auth deps)
- handlers.py (thin orchestration)

Rules:
- No direct DB queries (use domain repositories/services).
- No direct external calls (use gateways via services).
