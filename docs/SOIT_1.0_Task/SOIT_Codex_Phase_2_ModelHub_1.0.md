# SOIT Codex Phase 2 - ModelHub 1.0

## Goal
让模型管理成为 SOIT 1.0 主链路的稳定底座，支撑 Agent、Workflow、Chat 的实际调用。

## Scope
- Provider management
- Model registration/sync
- Default model selection
- Connectivity testing
- Availability validation

## Must Follow
- 只做 1.0 所需的模型管理能力
- 不做复杂计费、配额、商业化扩展
- 不做花哨展示页

## Tasks
1. Review existing provider and model domain objects.
2. Standardize provider create/update/test APIs.
3. Stabilize model sync or registration flow.
4. Add availability validation and normalized error structure.
5. Support default model configuration at platform/workspace level if already modeled.
6. Build Providers page with create/edit/test actions.
7. Build Models page with list, enable/disable, set default.
8. Verify Agent / Workflow / Chat can all read active models.

## Deliverables
- Stable provider APIs
- Stable model listing/configuration UI
- Unified model error handling

## Acceptance Criteria
- At least two provider types can be configured
- Model connectivity can be tested from UI
- Active models can be selected by Agent / Workflow / Chat
- Failure states are visible and understandable

## Suggested Commit
feat(modelhub): finalize provider and model management for 1.0 runtime usage
