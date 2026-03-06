# app/api/v1/bot/

Entrypoint: **bot**.

Place:
- routes.py (or router.py)
- dependencies.py (ctx injection, auth deps)
- handlers.py (thin orchestration)

Rules:
- No direct DB queries (use domain repositories/services).
- No direct external calls (use ports via services).

## API Contract (v1)

Base prefix: `/api/v1/bots`

- `POST /` create bot
- `GET /` list bots
- `GET /{bot_id}` get bot
- `PUT /{bot_id}` update bot
- `DELETE /{bot_id}` archive bot

- `POST /{bot_id}/versions` create draft version
- `GET /{bot_id}/versions` list versions
- `GET /{bot_id}/versions/{version_id}` get version
- `PUT /{bot_id}/versions/{version_id}` update draft version only
- `POST /{bot_id}/publish` publish version (updates `current_version_id` and `published_version_id`)

- `POST /{bot_id}/execute` execute bot (manual trigger)
- `POST /{bot_id}/execute/webhook` execute bot by webhook payload
- `POST /{bot_id}/execute/schedule` execute bot by scheduled trigger payload
- `POST /{bot_id}/execute/event` execute bot by internal event payload
- `GET /{bot_id}/runs` list runs
- `GET /{bot_id}/runs/{run_id}` run detail
- `GET /{bot_id}/logs` projected run-step logs
- `GET /{bot_id}/metrics` aggregated runtime metrics

## Version Semantics

- `versions[].version`: internal monotonic integer version string.
- `versions[].display_version`: optional display label from `metadata.display_version`.
- only `draft` versions are mutable.
- `published` and `deprecated` versions are immutable.
- execute preflight currently runs for published versions; draft execution skips preflight for faster debug.
