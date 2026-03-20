# Chat Module (Web)

This document summarizes the web chat module and highlights areas that still need work.

## Scope

- Route: `/chat/:agentId?/:threadId?`
- Pages: `web/src/pages/chat/index.tsx`, `web/src/pages/chat/ui/box-sidebar.tsx`
- Core UI: `web/src/components/ui/chat/*`
- Services: `web/src/services/thread-service.ts`, `web/src/services/responses-service.ts`
- Unified entry component: `web/src/components/ui/chat/chat-box.tsx`
- Hook: `web/src/hooks/use-chat.tsx`

## Main Flow

1. User opens `/chat/:agentId?/:threadId?`.
2. User selects a provider model for the chat.
3. `ChatBox` creates local runtime, wraps `AssistantRuntimeProvider`, and registers model context through `useAui`.
4. `ChatAdapter.run()` handles send/streaming completion and emits events.
5. Sidebar lists threads via `/threads`, supports provider switch, and groups by date.
6. `ChatBox` imports message history from `thread_messages` when a thread is present.

## Key Components

- `ChatAdapter` (`web/src/components/ui/chat/chat-adapter.tsx`)
  - Creates threads on demand and sends messages to `/responses`.
  - Parses semantic SSE events (`response.created`, `response.output_text.delta`, `response.completed`, `tool.call.*`).
  - Emits `chat_thread_created`, `refresh_chat_sidebar`, `chat_completion_finished`.
- `Thread` (`web/src/components/ui/chat/thread.tsx`)
  - UI for composer, message list, reasoning block, actions.
  - Placeholder toggles for "deep thinking / web search / code mode".
- `ChatBox` (`web/src/components/ui/chat/chat-box.tsx`)
  - Owns runtime and AUI provider boundary.
  - Exposes `AssistantClient` by `ref` for external thread control.
  - Handles thread switching + history import on thread changes.
- `BoxSidebar` (`web/src/pages/chat/ui/box-sidebar.tsx`)
  - Lists threads, rename, archive, delete, load more, grouped by date.
- `MessageConverter` (`web/src/components/ui/chat/message-adapter.tsx`)
  - Converts runtime thread messages to Assistant UI thread messages.

## APIs Used

- `GET /threads`
- `POST /threads`
- `PATCH /threads/:id`
- `DELETE /threads/:id`
- `GET /threads/:id`
- `POST /responses`
- `POST /responses` (SSE)

## Thread Model Notes

- `thread` is the only session container. Do not add chat-only state back under separate conversation resources.
- `threads` now carries session-level defaults and list metadata:
  - `summary`
  - `system_prompt`
  - `default_model_ref`
  - `default_temperature`
  - `default_max_tokens`
  - `default_top_p`
  - `message_count`
  - `last_message_at`
  - `last_user_message_at`
  - `last_assistant_message_at`
  - `thread_type`
  - `source`
- `thread_messages` now carries message-level execution facts directly:
  - `sequence_no`
  - `response_id`
  - `task_id`
  - `status`
  - `model_ref`
  - `tokens_prompt`
  - `tokens_completion`
  - `finish_reason`
  - `citations_json`
  - `attachments_json`
  - `tool_calls_json`
- Rule: high-signal query fields should be read from first-class columns. `metadata_json` is only for low-frequency extension data.

## State & Storage

- `localStorage`:
  - `chat_default_model`
  - `chat_default_provider`
  - `workspace_id`
  - `token`

## Planned UX (Provider + Thread Switch)

- New chat: user selects a provider model first.
- Sidebar: two switching dimensions:
  - Thread list within the active provider.
  - Provider selector to switch across providers and refresh the list.

## Observed Gaps / To-Do

1. Rename flow lacks stronger validation (length limits and server-side duplicate handling).
2. Attachments UI is present, but `ChatAdapter` currently sends text-only payloads.
3. Composer toggles (deep thinking / web search / code mode) are UI-only.
4. Some tooltip/action strings are still hardcoded English.
5. Error handling is mostly console-level; retry/empty-state UX is limited.
6. SSE streaming lacks retry/backoff and offline recovery handling.
7. Attachment upload/send is still only partially wired; message attachment state is persisted but not yet fully surfaced end-to-end.

## Suggested Next Steps

- Wire sidebar search to query/filter threads.
- Persist provider/model selection per thread (or per provider) and restore on open.
- Add confirm dialog for delete and validate rename inputs.
- Send attachments and toggle options in `ChatAdapter` payloads.
- Add i18n coverage for tooltips and user-facing strings.
- Add basic user-facing error states and retry for streaming.
