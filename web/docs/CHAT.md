# Chat Module (Web)

This document summarizes the web chat module and highlights areas that still need work.

## Scope

- Route: `/chat/:appId?/:id?`
- Pages: `web/src/pages/chat/index.tsx`, `web/src/pages/chat/ui/box-sidebar.tsx`
- Core UI: `web/src/components/ui/chat/*`
- Store: `web/src/stores/chat.tsx`
- Services: `web/src/services/chat-service.ts`
- Unified entry component: `web/src/components/ui/chat/chat-box.tsx`
- Legacy hook (kept for fallback): `web/src/hooks/use-chat.tsx`

## Main Flow

1. User opens `/chat/:appId?/:id?`.
2. User selects a provider model for the chat.
3. `ChatBox` creates local runtime, wraps `AssistantRuntimeProvider`, and registers model context through `useAui`.
4. `ChatAdapter.run()` handles send/streaming completion and emits events.
5. Sidebar lists conversations via `/chat/conversations`, supports provider switch, and groups by date.
6. `ChatBox` imports message history via `loadMessages()` when a conversation id is present.

## Key Components

- `ChatAdapter` (`web/src/components/ui/chat/chat-adapter.tsx`)
  - Sends messages to `/chat/completions` or `/chat/stream`.
  - Parses SSE events (`start`, `delta`, `complete`, `error`).
  - Emits `chat_conversation_created`, `refresh_chat_sidebar`, `chat_completion_finished`.
- `Thread` (`web/src/components/ui/chat/thread.tsx`)
  - UI for composer, message list, reasoning block, actions.
  - Placeholder toggles for "deep thinking / web search / code mode".
- `ChatBox` (`web/src/components/ui/chat/chat-box.tsx`)
  - Owns runtime and AUI provider boundary.
  - Exposes `AssistantClient` by `ref` for external thread control.
  - Handles thread switching + history import on conversation changes.
- `BoxSidebar` (`web/src/pages/chat/ui/box-sidebar.tsx`)
  - Lists conversations, rename, delete, load more, grouped by date.
- `MessageConverter` (`web/src/components/ui/chat/message-adapter.tsx`)
  - Converts API message format to Assistant UI thread messages.

## APIs Used

- `GET /chat/conversations`
- `POST /chat/conversations`
- `PATCH /chat/conversations/:id`
- `DELETE /chat/conversations/:id`
- `GET /chat/conversations/:id/messages`
- `POST /chat/completions`
- `POST /chat/stream` (SSE)

## State & Storage

- `useChatStore`: maps `appId -> conversationId`.
- `localStorage`:
  - `chat_default_model`
  - `workspace_id`
  - `token`

## Planned UX (Provider + Conversation Switch)

- New chat: user selects a provider model first.
- Sidebar: two switching dimensions:
  - Conversation list within the active provider.
  - Provider selector to switch across providers and refresh the list.

## Observed Gaps / To-Do

1. Rename flow lacks validation (empty/duplicate names, length limits).
2. Attachments UI is present, but `ChatAdapter` currently sends text-only payloads.
3. Composer toggles (deep thinking / web search / code mode) are UI-only.
4. Some tooltip/action strings are still hardcoded English.
5. Error handling is mostly console-level; retry/empty-state UX is limited.
6. SSE streaming lacks retry/backoff and offline recovery handling.
7. New-thread initialization uses fixed `"main"` thread handle in some paths, which may be brittle.

## Suggested Next Steps

- Wire sidebar search to query/filter conversations.
- Persist provider/model selection per conversation (or per provider) and restore on open.
- Add confirm dialog for delete and validate rename inputs.
- Send attachments and toggle options in `ChatAdapter` payloads.
- Add i18n coverage for tooltips and user-facing strings.
- Add basic user-facing error states and retry for streaming.
