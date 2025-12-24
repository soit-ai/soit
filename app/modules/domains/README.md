# modules/domains/

Business domains. Own:
- domain models (SQLModel)
- domain schemas (Pydantic)
- repositories/services
- domain state machines

Rules:
- External calls only via gateways.
- Do not import other domains' models directly.
