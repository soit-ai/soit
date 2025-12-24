# modules/domains/pluginmarket/

Domain: **pluginmarket**.

Place:
- models.py (SQLModel tables)
- schemas.py (Pydantic)
- repository.py (DB access using scope-aware base)
- service.py (business logic)
- events.py (optional domain events)

Rules:
- Enforce tenant/workspace scope.
- Validate specs against kernel schemas if applicable.
