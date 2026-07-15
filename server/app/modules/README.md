# modules/

Product logic built on top of kernel.

- `<domain>/domain/`: domain models and business entities.
- `<domain>/application/`: application services, schemas, and public contracts.
- `<domain>/infra/`: repositories and infrastructure-facing implementations.
- `<domain>/runtime/`: optional domain execution components.
- HTTP entrypoints live in `app/api/v1/*` and remain thin.
