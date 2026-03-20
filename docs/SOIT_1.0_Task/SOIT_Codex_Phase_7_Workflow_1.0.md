# SOIT Codex Phase 7 - Workflow 1.0

## Goal
打通 Workflow 主链路，让用户可以创建、编辑、发布、执行并查看 Workflow 运行结果。

## Scope
- Workflow schema / DSL
- Workflow CRUD
- Builder basics
- Publish flow
- Execute and inspect

## Must Follow
- 节点集只保留 1.0 最小集合
- 不扩展复杂流程编排高级特性
- 不做模板市场和过多可视化增强

## Tasks
1. Standardize workflow schema and DSL contract.
2. Finalize workflow CRUD and publish APIs.
3. Implement or refine workflow execution entry.
4. Ensure runtime captures node-level events needed for 1.0 diagnostics.
5. Limit supported nodes to Start / LLM / Knowledge Retrieve / Code or Transform / Condition / End.
6. Build Workflow list page.
7. Build Workflow builder basics: drag, connect, configure, save.
8. Add publish action.
9. Add test run action.
10. Add result viewing and link to runs.
11. Show draft vs published version state.

## Deliverables
- Stable workflow schema/API
- Minimal builder UI
- Publish and test-run flow

## Acceptance Criteria
- User can create a workflow
- User can configure minimum supported nodes
- User can publish and execute workflow
- User can inspect workflow run result

## Suggested Commit
feat(workflow): complete 1.0 builder, publish, and execution flow
