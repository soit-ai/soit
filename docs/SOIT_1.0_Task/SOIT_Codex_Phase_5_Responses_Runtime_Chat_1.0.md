# SOIT Codex Phase 5 - Responses Runtime and Chat 1.0

## Goal
统一 Thread / Response / SSE 对话运行时，让 Chat 成为 Agent 的真实使用入口。

## Scope
- Thread lifecycle
- Response lifecycle
- SSE event streaming
- Chat UI integration
- Agent / Response / Run linkage

## Must Follow
- 优先保证稳定性和可观察性
- 不扩展复杂多分支对话能力
- 不做复杂富文本消息系统

## Tasks
1. Standardize thread and response API contracts.
2. Define response lifecycle states: created, streaming, completed, failed, cancelled.
3. Normalize event payloads for model output, retrieval, tool call, errors.
4. Add failure reason and cancel reason fields.
5. Ensure response records link back to run and agent.
6. Build or refine Chat page to support agent selection.
7. Support thread creation and history viewing.
8. Support SSE streaming and cancel action.
9. Render basic event states in UI.
10. Surface linked run details from each conversation if available.

## Deliverables
- Unified response runtime contract
- Stable SSE-based chat flow
- Agent-backed thread experience

## Acceptance Criteria
- User can choose agent and start a thread
- Streaming output works end-to-end
- Failure states are visible
- Response can be linked to run details

## Suggested Commit
feat(runtime): finalize responses and chat integration for 1.0 agent usage
