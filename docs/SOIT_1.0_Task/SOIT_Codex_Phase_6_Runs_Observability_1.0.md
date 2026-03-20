# SOIT Codex Phase 6 - Runs and Observability 1.0

## Goal
建立最小可用的运行记录与排障能力，支撑 Agent、Workflow、Chat 的结果查看和问题定位。

## Scope
- Run list
- Run detail
- Run events
- Cross-linking from major objects
- Unified status display

## Must Follow
- 仅做 1.0 所需排障能力
- 不做复杂 BI 仪表盘
- 不做重型 tracing 平台

## Tasks
1. Review and normalize run data model.
2. Ensure object type tagging supports agent, workflow, response.
3. Ensure run status supports queued, running, completed, failed, cancelled.
4. Add summary fields for duration, model calls, tool calls, and errors.
5. Build run list API and filters.
6. Build run detail API with event timeline.
7. Build Runs list page with filters.
8. Build Run detail page with summary, timeline, failure details.
9. Add navigation links from Agent / Workflow / Chat pages.

## Deliverables
- Run list/detail/event APIs
- Runs list and detail UI
- Cross-object links to runs

## Acceptance Criteria
- User can inspect recent runs
- Failed runs show error reason and likely failure location
- Agent / Workflow / Chat can navigate to linked runs

## Suggested Commit
feat(observability): add 1.0 run list and diagnostic detail views
