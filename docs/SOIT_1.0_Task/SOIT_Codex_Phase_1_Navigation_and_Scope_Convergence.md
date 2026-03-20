# SOIT Codex Phase 1 - Navigation and Scope Convergence

## Goal
收敛 SOIT 1.0 的前端导航、对象命名和历史入口，确保产品主界面只保留 1.0 必要模块，避免继续发散。

## Scope
- 前端一级导航收敛
- 历史模块入口隐藏或移除
- 命名统一（dataset -> knowledge）
- Dashboard 轻量化
- 清理死路由、空页面、历史兼容菜单

## Must Follow
- 严格按 1.0 范围执行
- 不新增 Store / Safe / Memory / Marketplace 类功能
- 不新增展示型页面
- 不扩展系统管理边界

## Tasks
1. Audit current front-end routes and side navigation.
2. Keep only Dashboard, Agents, Workflows, Knowledge, Chat, Tasks, Runs, Models, Settings.
3. Hide or remove menu entries for Safe, Store, AppCenter, Bot, PluginMarket.
4. Replace outward-facing dataset wording with knowledge.
5. Reposition chat as an interaction entry, not a top-level business domain.
6. Remove unused page imports and dead route references.
7. Simplify Dashboard to key counts, recent runs, recent failures.
8. Ensure route guards and breadcrumbs remain valid after cleanup.

## Deliverables
- Updated navigation config
- Cleaned routes
- Simplified dashboard
- Removed or hidden historical module entries

## Acceptance Criteria
- Main navigation matches SOIT 1.0 scope
- No broken routes after cleanup
- No user-facing dataset wording remains
- UI no longer exposes non-1.0 modules

## Suggested Commit
feat(scope): converge 1.0 navigation and remove non-core module entrypoints
