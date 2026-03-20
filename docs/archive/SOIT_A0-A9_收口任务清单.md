# SOIT A0-A9 收口任务清单

> Status note
> 本文档用于记录 A0-A9 收口过程与结果，属于阶段性交付记录。
> 当前架构说明仍应以仓库 README 与 `app/web docs` 下的结构文档为准。

本文档把“部分完成”和“未完成”的重构项收敛成最终任务，并对应当前实现结果进行标记。

## A0 蓝图冻结与约束

- [x] 补齐后端与前端 README/结构文档
- [x] 增加重构守卫脚本，限制新增旧中心语义
- [x] 固化 Agent 中心化的重构原则文档

主要产出：

- `app/docs/README.md`
- `web/docs/README.md`
- `app/scripts/refactor_guardrails.py`
- `docs/architecture/soit-refactor-principles.md`

## A1 Agent 主模型落地

- [x] 新增 `agents / agent_versions / agent_bindings / agent_publishes`
- [x] Agent CRUD、版本、发布、执行改走新表
- [x] Agent 执行创建 `thread / task`

主要产出：

- `app/app/modules/agent/domain/models.py`
- `app/app/modules/agent/infra/repository.py`
- `app/app/modules/agent/application/app_facade.py`
- `app/alembic/versions/20260306100000_agent_core_tables.py`

## A2 Thread / Task 统一

- [x] 新增 `threads / thread_messages / tasks / task_checkpoints / task_events`
- [x] 新增 `RuntimeCoreService` 与读侧 `RuntimeQueryService`
- [x] Chat 与 Agent 开始写入 Runtime Core

主要产出：

- `app/app/kernel/runtime/models.py`
- `app/app/kernel/runtime/repository.py`
- `app/app/kernel/runtime/core/service.py`
- `app/app/kernel/runtime/query_service.py`
- `app/alembic/versions/20260306113000_runtime_thread_task_tables.py`

## A3 Runtime Core 替换旧主链

- [x] Workflow 不再依赖 `AppRuntimeRouter`
- [x] Workflow 改为独立 `workflows / workflow_versions / workflow_publishes`
- [x] Workflow 直接调用 `ExecutionEngine`

主要产出：

- `app/app/modules/workflow/domain/models.py`
- `app/app/modules/workflow/infra/repository.py`
- `app/app/modules/workflow/application/app_facade.py`
- `app/alembic/versions/20260306143000_workflow_core_tables.py`

## A4 Agent 聚合根补全

- [x] Agent 版本、绑定、发布链补齐
- [x] Agent API 全面切到新聚合根
- [x] Agent 详情页、列表页接真实 Agent API

主要产出：

- `app/app/api/v1/agent/*`
- `web/src/pages/agents/*`
- `web/src/services/agent-service.ts`

## A5 Chat / Task 主路径收口

- [x] Chat 前端路由改为 `agentId + threadId`
- [x] Thread API 支持列表、详情、更新、删除
- [x] Task API 增加 `cancel / resume / retry`
- [x] Tasks 页面支持控制动作

主要产出：

- `app/app/api/v1/thread/*`
- `app/app/api/v1/task/*`
- `web/src/pages/chat/*`
- `web/src/pages/tasks/*`
- `web/src/services/thread-service.ts`
- `web/src/services/task-service.ts`

## A6 Knowledge / Skill / Workflow 能力层

- [x] Knowledge 前台与 API 入口切换
- [x] Knowledge 增加独立应用服务边界
- [x] Skill 独立模型与 API

主要产出：

- `app/app/modules/knowledge/application/service.py`
- `app/app/modules/skill/domain/models.py`
- `app/app/modules/skill/application/service.py`
- `app/app/api/v1/skill/*`
- `app/app/api/v1/knowledge/*`
- `web/src/pages/knowledge/*`
- `web/src/services/knowledge-service.ts`

## A7 Plugin / MCP / 接入层

- [x] `/plugins` 成为统一插件入口
- [x] 新增 `modules/plugin` 应用服务边界
- [x] MCP 独立接入层 API

主要产出：

- `app/app/modules/plugin/application/service.py`
- `app/app/modules/integrations/mcp/domain/models.py`
- `app/app/modules/integrations/mcp/application/service.py`
- `app/app/api/v1/mcp/*`
- `app/app/api/v1/pluginmarket/*`
- `web/src/pages/plugin/*`

## A8 前端 Agent 中心化

- [x] 一级导航切换到 Agent 中心 IA
- [x] 新增 `Agents / Knowledge / Tasks / Observability`
- [x] Chat、Knowledge、Observability 路由完成迁移

主要产出：

- `web/src/routes.ts`
- `web/src/components/nav/root-sidebar.tsx`
- `web/src/pages/observability/index.tsx`

## A9 治理、验证与遗留清理

- [x] 删除主入口旧 `apps / datasets / bots` 路由注册
- [x] 统一补充后端测试与入口测试
- [x] 前端历史死代码目录清理
- [x] Skill/MCP/Governance 生产级能力补齐

主要产出：

- `app/app/main.py`
- `app/app/modules/observability/*`
- `app/app/api/v1/observability/*`
- `app/alembic/versions/20260307100000_capability_governance_tables.py`
- `app/tests/unit/*`
- `app/tests/entrypoints/*`
- `web/src/pages/app/*`（已删除）
- `web/src/pages/bot/*`（已删除）
- `web/src/pages/dataset/*`（保留为迁移期知识库 UI 源目录，不再作为公开路由）
- `web/src/services/bot-service.ts`（已删除）
- `web/src/services/dataset-service.ts`（已删除，由 `knowledge-service` 承接公开入口）

## 结论

当前主干重构已经覆盖 A0-A9 核心目标，并完成最后一轮能力层、治理层和主要遗留清理。

治理层最终落点如下：

1. `skill` 已具备独立模型、版本、发布与 API
2. `mcp` 已具备独立接入层 API 与 capability catalog
3. `observability` 已补齐 approval / feedback / replay
4. budget / quota policy 继续由 `security` 的 limits API 统一承载
5. `dataset` 能力以 `knowledge` 产品语义对外承接，前端保留 `dataset` 目录仅用于迁移期源码复用

## 验证结果

- `cd app && uv run pytest`：`163 passed`
- `cd app && uv run python scripts/refactor_guardrails.py`：通过
- 前端 `typecheck`：按当前阶段约定跳过
