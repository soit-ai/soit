# SOIT Codex Phase 4 - Agent 1.0

## Goal
打通 Agent 主链路，让用户能够创建、配置、发布并在 Chat 中实际使用 Agent。

## Scope
- Agent CRUD
- Agent version basics
- Publish flow
- Binding to model and knowledge
- Runtime entry integration

## Must Follow
- 仅实现 1.0 所需最小闭环
- 不做复杂模板商城、多人协作编辑、深度调试器
- 工具/MCP 绑定只保留基础占位或最小可用能力

## Tasks
1. Review and normalize agent domain schema.
2. Ensure agent fields include base info, prompt, model binding, knowledge binding, status.
3. Add or refine draft/published version semantics.
4. Complete agent CRUD APIs.
5. Complete publish API and validation checks.
6. Add runtime validation for model / knowledge availability.
7. Build Agent list page.
8. Build Agent create/edit page.
9. Build Agent detail page with config, bindings, publish state, recent runs.
10. Add entry to open Chat with selected Agent.
11. Add recent execution link to Runs.

## Deliverables
- Stable agent APIs
- Agent CRUD and publish UI
- Agent-to-Chat handoff
- Agent run linkage

## Acceptance Criteria
- User can create an agent
- User can bind model and knowledge
- User can publish agent
- User can start chat with that agent

## Suggested Commit
feat(agent): implement 1.0 agent creation, publish, and runtime linkage
