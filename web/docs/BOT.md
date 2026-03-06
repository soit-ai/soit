# Bot Module Contract

## Scope

This document defines the frontend-facing Bot module contract used by `web/src/services/bot-service.ts`.

## API Base

- `/api/v1/bots`

## Core Flows

1. Bot list and create
- `GET /bots`
- `POST /bots`

2. Bot configuration
- `GET /bots/{bot_id}`
- `PUT /bots/{bot_id}`

3. Version lifecycle
- `GET /bots/{bot_id}/versions`
- `POST /bots/{bot_id}/versions`
- `GET /bots/{bot_id}/versions/{version_id}`
- `PUT /bots/{bot_id}/versions/{version_id}`
- `POST /bots/{bot_id}/publish`

4. Runtime
- `POST /bots/{bot_id}/execute`
- `POST /bots/{bot_id}/execute/webhook`
- `POST /bots/{bot_id}/execute/schedule`
- `POST /bots/{bot_id}/execute/event`
- `GET /bots/{bot_id}/runs`
- `GET /bots/{bot_id}/runs/{run_id}`
- `GET /bots/{bot_id}/logs`
- `GET /bots/{bot_id}/metrics`

## Important Fields

- `BotVersion.version`: internal auto-increment version.
- `BotVersion.display_version`: optional business display version.
- `BotVersion.status`: `draft | published | deprecated`.
- `BotVersion.triggers/channels/limits`: stored in `bot.v1` spec.
- `BotRunSummary.user_id/message_count`: projected from run input and used by log UI.
- `BotMetrics.active_users/usage_distribution/resource_usage`: monitor UI data source.

## Behavior Rules

- Only `draft` versions are editable.
- Execute endpoint supports manual and trigger payload (`webhook/schedule/event`).
- Preflight reference validation is applied for published versions.
- Publish endpoint updates both `current_version_id` and `published_version_id`.
