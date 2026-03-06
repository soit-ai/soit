# secrets/

Workspace-scoped secrets management.

Endpoints:
- `GET /api/v1/secrets`: list secrets
- `POST /api/v1/secrets`: create secret (value stored in Vault)
- `GET /api/v1/secrets/{id}`: get secret metadata
- `PATCH /api/v1/secrets/{id}`: update metadata or rotate value
- `DELETE /api/v1/secrets/{id}`: delete secret
- `POST /api/v1/secrets/{id}/test`: validate secret resolution

Notes:
- Secret values are never returned by the API.
- `secret_ref` values are used by tools via `secret_ref` injection.
