# SOIT 当前架构梳理与重构任务计划表

> Archive note
> 本文档记录的是重构启动期的基线判断与任务拆解，属于历史规划材料，不再作为“当前实现架构说明”使用。
> 当前实现请优先参考：
> `README.md`
> `app/docs/architecture/PROJECT_STRUCTURE.md`
> `app/docs/architecture/KERNEL_V1_DATA_MODEL.md`
> `web/docs/PROJECT_STRUCTURE.md`

## 1. 文档目标

基于当前真实仓库结构，梳理 SOIT-Pro 现状架构，并将《SOIT_大规模架构重构开发规划_Agent中心版》拆解为可执行的重构任务计划表。

本文档解决两个问题：

1. 当前系统实际上是怎样组织的
2. 按照 Agent 中心蓝图，应如何分阶段推进重构

---

## 2. 当前仓库架构基线

## 2.1 顶层目录

当前仓库顶层结构为：

```text
.
├── app/      # 后端 FastAPI + SQLModel
├── web/      # 前端 React Router + Vite
├── docs/     # 项目级规划与架构文档
├── docker/   # 部署与容器资源
└── README.md
```

---

## 2.2 后端现状

### 2.2.1 分层结构已初步建立

`app/app/` 已按以下目录组织：

- `api/`
- `kernel/`
- `modules/`
- `adapters/`
- `infra/`
- `middleware/`
- `plugins/`
- `settings/`
- `utils/`
- `wiring/`

这说明后端已经具备“内核 + 业务模块 + 适配器”的分层雏形。

### 2.2.2 API 入口仍是多中心并列平台

`app/app/main.py` 当前同时注册了以下路由：

- `workflow`
- `dataset`
- `chat`
- `bot`
- `memory`
- `modelhub`
- `pluginmarket`
- `run`
- `agent`
- `appcenter`

结论：

- API 层仍然是多产品域并列
- `agent` 已经存在，但尚未成为唯一中心
- `appcenter` 仍然保留主入口角色

### 2.2.3 当前主数据模型仍以 AppCenter 为中心

`app/app/modules/appcenter/domain/models.py` 中，核心表仍然是：

- `apps`
- `app_versions`
- `app_market`
- `app_installations`
- `app_components`
- `app_component_edges`
- `app_version_refs`

其中 `App.type` 同时承担：

- `WORKFLOW`
- `CHAT`
- `BOT`
- `AGENT`
- `DATASET`

结论：

- Agent 还不是独立主模型
- 当前平台主模型本质上仍是 `App`
- 数据模型层仍处在“统一壳 + 多业务类型”阶段

### 2.2.4 Agent 已落 API，但仍依赖 AppCenter

`app/app/api/v1/agent/router.py` 已提供：

- 创建 Agent
- 查询 Agent
- 创建 AgentVersion
- 发布 Agent
- 执行 Agent

但 `app/app/modules/agent/application/app_facade.py` 显示：

- Agent 创建实际写入 `App(type="AGENT")`
- AgentVersion 实际写入 `AppVersion`
- Agent 执行仍通过 `AppRuntimeRouter`

结论：

- Agent 已有产品接口
- 但只是 `App/AppVersion` 的语义包装层
- 尚未形成独立 Agent 聚合根

### 2.2.5 运行时已有统一底座，但未形成 Runtime Core

当前执行链路主要由以下对象组成：

- `app/app/modules/appcenter/runtime/router.py`
- `app/app/modules/chat/runtime/chat_executor.py`
- `app/app/modules/bot/runtime/bot_executor.py`
- `app/app/modules/agent/runtime/agent_executor.py`
- `app/app/modules/workflow/runtime/workflow_executor.py`
- `app/app/modules/workflow/runtime/engine.py`

现状特点：

- `AppRuntimeRouter` 按 `app.type + spec_schema` 路由执行
- `ExecutionEngine` 已统一承接 `chat / bot / workflow / agent`
- 但各模块仍保留各自 executor 和模块内执行逻辑

结论：

- 当前是“部分统一执行”
- 还不是蓝图要求的 `kernel/runtime/*` 统一 Runtime Core
- 旧结构中的模块自治执行器仍然存在

### 2.2.6 Trace / Run 体系已具备雏形

`app/app/kernel/trace/models.py` 已有：

- `runs`
- `run_steps`
- `run_artifacts`
- `run_cost_entries`

现状优点：

- 平台已经有统一运行记录基础
- 可作为后续 Runtime Core 的底座继续演进

现状缺口：

- 仍通过 `app_id / app_version_id` 关联执行主体
- 尚无统一 `tasks`
- 尚无统一 `threads`
- 尚无统一 `feedback`

### 2.2.7 状态机尚未满足新蓝图

`app/app/kernel/execution/state_machine.py` 当前状态只有：

- `queued`
- `running`
- `paused`
- `succeeded`
- `failed`
- `canceled`

缺少新蓝图要求的：

- `preparing`
- `waiting_input`
- `waiting_approval`
- `retrying`
- `expired`

### 2.2.8 Dataset 仍是独立产品域，不是 Knowledge

`app/app/modules/dataset/domain/models.py` 当前核心对象为：

- `dataset`
- `dataset_documents`
- `dataset_ingest_tasks`
- `dataset_chunks`
- `dataset_indexs`

同时：

- Chat RAG 已直接依赖 Dataset 查询服务
- 数据摄取任务使用 `dataset_ingest_tasks`

结论：

- 数据集域能力已经较丰富
- 但语义仍是 Dataset，不是 Knowledge
- `ingest task` 仍是模块内任务模型，没有统一纳入平台 Task 域

### 2.2.9 Plugin / Model / Memory / Security 已各自成域

当前 `modules/` 下已有：

- `identity`
- `workflow`
- `dataset`
- `security`
- `bot`
- `chat`
- `secrets`
- `appcenter`
- `pluginmarket`
- `notification`
- `agent`
- `modelhub`
- `memory`

结论：

- 业务域已经很多
- 但边界仍是“产品模块并列”，不是“Agent 中心 + 能力层/接入层”

### 2.2.10 测试基础较完整，但围绕旧结构

`app/tests/` 已分为：

- `unit/`
- `integration/`
- `entrypoints/`

现有测试覆盖了：

- `appcenter`
- `bot`
- `dataset`
- `chat`
- `workflow`
- `agent`
- `run`
- `plugin`

结论：

- 这是重构的有利条件
- 但测试断言仍大量围绕 `App / Dataset / Bot` 旧概念

---

## 2.3 前端现状

### 2.3.1 前端目录结构规范，但仍是旧平台 IA

`web/src/` 当前包含：

- `pages/`
- `components/`
- `services/`
- `stores/`
- `hooks/`
- `styles/`
- `assets/`
- `i18n/`
- `config/`
- `constant/`
- `utils/`
- `types/`
- `data/`
- `lib/`

### 2.3.2 主路由仍按旧模块组织

`web/src/routes.ts` 当前主路由包括：

- `/chat/:appId?/:id?`
- `/bot/*`
- `/dataset/*`
- `/workflow/*`
- `/run/*`
- `/plugin/*`
- `/model/*`
- `/safe/*`
- `/store/*`
- `/setting/*`
- `/app/:type?/:id?`

结论：

- 前端仍围绕 `Bot / Dataset / Workflow / Run / App`
- Chat 页面仍然绑定 `appId`
- 仍有显式 `app` 路由

### 2.3.3 主导航仍不是 Agent 中心化

`web/src/components/nav/root-sidebar.tsx` 当前一级导航为：

- Chat
- Bot
- Dataset
- Workflow
- Runs
- Model
- Plugin
- Safe
- Store

结论：

- 前台信息架构仍是模块式平台
- 与蓝图要求的 `Agents / Chat / Workflows / Knowledge / Tasks / Observability` 不一致

### 2.3.4 当前没有独立 Agent 页面中心

`web/src/pages/` 下当前没有 `agent` 目录，现有页面中心仍是：

- `bot`
- `dataset`
- `workflow`
- `run`
- `chat`

结论：

- Agent 已在后端存在
- 但前台尚未形成 Agent 视角入口

---

## 2.4 当前架构一句话判断

SOIT-Pro 当前处于：

**“已经做出统一内核和 Agent 方向的早期尝试，但真实中心仍是 AppCenter，前后端仍保留 Bot/Dataset/Workflow 并列平台结构，属于重构前夜的混合态。”**

---

## 3. 与新蓝图的关键差距

| 维度 | 当前状态 | 目标状态 | 差距判断 |
|---|---|---|---|
| 主对象 | `App` 承载多类型 | `Agent` 为唯一主对象 | 高 |
| 执行内核 | `AppRuntimeRouter + 多 executor` | `Runtime Core` 唯一执行内核 | 高 |
| 运行记录 | `Run/Step/Artifact/Cost` 已有 | Run/Task/Trace/Artifact/Feedback 全量统一 | 中高 |
| 会话模型 | Chat 仍偏独立入口 | `Agent + Thread + Run` | 高 |
| 数据集语义 | `Dataset` 独立产品 | `Knowledge` 能力层 | 高 |
| 能力层 | Workflow/Plugin/MCP 边界混合 | Tool/Skill/Workflow/Plugin/MCP 清晰分层 | 高 |
| 前端 IA | Bot/Dataset/Workflow 并列 | Agents 中心导航 | 高 |
| 治理能力 | 有运行追踪基础 | 生产级 observability/policy/governance | 中 |

---

## 4. 重构执行原则

1. 后端先于前端
2. 数据模型先于 API
3. Runtime Core 先于 Agent 前台
4. 允许短期兼容层，但必须有删除计划
5. 不再新增任何 `App*`、`Dataset` 产品中心、模块自治 executor
6. 每个阶段都要同步补测试，不允许只迁移实现不迁移验收口径

---

## 5. 分阶段重构任务计划表

## Phase 0：准备与冻结

| 项目 | 内容 |
|---|---|
| 目标 | 冻结蓝图、固化旧新映射、建立禁增规则 |
| 当前基础 | 已有蓝图文档，但缺少基于真实仓库的执行清单；`app/docs/README.md` 缺失 |
| 关键任务 | 1. 补仓库对齐版架构文档 2. 输出旧新对象映射表 3. 约定 legacy/adapter/deprecated 命名规则 4. 建立 phase 验收模板 5. 增加禁止新增 `App*`/独立 executor 的检查项 |
| 涉及目录 | `docs/`、`app/docs/`、CI 配置、lint/check 脚本 |
| 验收标准 | 团队后续执行以 Agent 中心蓝图为唯一依据；文档和规则落库 |

## Phase 1：后端核心对象与 Runtime Core

| 项目 | 内容 |
|---|---|
| 目标 | 去 App 化，建立 Agent/Thread/Run/Task 核心对象与统一 Runtime Core |
| 当前基础 | 已有 `runs/run_steps/run_artifacts/run_cost_entries` 和 `ExecutionEngine` |
| 关键任务 | 1. 新建 `agents/agent_versions/agent_bindings/agent_publishes` 2. 新建 `threads/thread_messages` 3. 新建 `tasks/task_checkpoints/task_events` 4. 扩展状态机 5. 新建 `kernel/runtime/{core,contracts,executors,orchestrators,checkpoints}` 6. 下沉统一 artifact/trace/retry/resume/cancel 机制 |
| 涉及目录 | `app/app/kernel/`、`app/app/modules/agent/`、`app/alembic/`、`app/tests/` |
| 验收标准 | `App` 从主模型退位；Runtime Core 成为唯一执行入口；Task 域落地 |

## Phase 2：Agent 模块中心化

| 项目 | 内容 |
|---|---|
| 目标 | 让 Agent 从 facade 变为唯一中心聚合根 |
| 当前基础 | 已有 agent API 和部分 agent 运行能力 |
| 关键任务 | 1. 重构 Agent 聚合根 2. AgentVersion 显式化 3. AgentBinding 统一绑定 model/workflow/skill/knowledge/tool/plugin/mcp 4. AgentPublish 独立流程 5. Chat 统一为 `Agent + Thread + Run` 6. Task 统一为 `Agent + Task + Run + Artifact` 7. Bot 下沉为 `Agent Template/LegacyBot` |
| 涉及目录 | `app/app/modules/agent/`、`app/app/api/v1/agent/`、`app/app/modules/bot/`、`app/tests/` |
| 验收标准 | Agent 成为唯一中心；Bot 不再继续扩张为独立中心模块 |

## Phase 3：能力层与接入层重构

| 项目 | 内容 |
|---|---|
| 目标 | 重建 Workflow/Skill/Knowledge/Plugin/MCP 边界 |
| 当前基础 | 已有 workflow、dataset、pluginmarket、modelhub、memory 等成熟模块 |
| 关键任务 | 1. Workflow 结果统一接入 Run/Trace/Artifact 2. 新增 Skill 模型与执行接入 3. Dataset 迁移到 Knowledge 语义 4. PluginMarket 重定位为 Plugin 安装层 5. 新建 `modules/integrations/mcp` 6. 建统一 capability registry |
| 涉及目录 | `app/app/modules/workflow/`、`app/app/modules/dataset/`、`app/app/modules/pluginmarket/`、`app/app/modules/modelhub/`、`app/app/modules/memory/`、`app/app/modules/integrations/` |
| 验收标准 | Workflow 不再抢占主中心；Knowledge 替代 Dataset 语义；Plugin/MCP 边界清晰 |

## Phase 4：前端 Agent 中心化迁移

| 项目 | 内容 |
|---|---|
| 目标 | 把前台从旧模块平台迁移为 Agent 中心平台 |
| 当前基础 | 路由与导航已模块化，便于迁移；但当前没有 Agent 中心页 |
| 关键任务 | 1. 一级导航改为 `Agents / Chat / Workflows / Knowledge / Plugin / Models / Tasks / Observability / Settings` 2. 新建 Agent 列表/详情/编辑页 3. Chat 改为 Agent 归属 4. Run 页拆为 Tasks/Observability 5. Dataset 页面迁移为 Knowledge 6. MCP 放到 Plugin 子域 |
| 涉及目录 | `web/src/routes.ts`、`web/src/components/nav/`、`web/src/pages/`、`web/src/services/`、`web/src/stores/` |
| 验收标准 | 前台不再以 Bot/Dataset/App 为一级中心；Chat 与 Tasks 都归属于 Agent |

## Phase 5：Observability / Policy / Governance

| 项目 | 内容 |
|---|---|
| 目标 | 补齐生产级治理能力 |
| 当前基础 | 已有 run list/detail、cost summary、trace writer 基础 |
| 关键任务 | 1. Trace 查询与回放 2. Policy Hook 统一 3. Approval 模型统一 4. Feedback 回流 5. 成本/预算/配额治理 6. run/step/artifact 时间线增强 |
| 涉及目录 | `app/app/kernel/trace/`、`app/app/kernel/security/`、`app/app/modules/observability/`、`web/src/pages/run/` 或新 `observability/`、`web/src/pages/tasks/` |
| 验收标准 | 平台可观测、可审批、可预算控制，支持生产运行治理 |

## Phase 6：兼容层清理与收口

| 项目 | 内容 |
|---|---|
| 目标 | 删除双轨结构，完成最终收敛 |
| 当前基础 | 预计会保留一段时间的 `legacy AppCenter / Dataset / Bot / executor` 兼容层 |
| 关键任务 | 1. 删除 `appcenter` 主路径 2. 删除旧 `App*` 依赖 3. 删除 Dataset 旧产品语义 4. 删除 Bot 独立执行路径 5. 删除 legacy executor/router 6. 删除双写和重复 binding/ref 模型 |
| 涉及目录 | `app/app/modules/appcenter/`、`app/app/api/v1/appcenter/`、`app/app/modules/bot/`、`app/app/modules/dataset/`、`web/src/pages/app/`、旧文案与旧 store |
| 验收标准 | 新蓝图成为唯一真实结构，旧主概念彻底退出 |

---

## 6. 推荐落地批次

为避免 Phase 太大，建议按以下 10 个批次执行：

| 批次 | 名称 | 核心输出 |
|---|---|---|
| Batch A0 | 蓝图冻结与文档补齐 | 架构基线、映射表、禁增规则、验收模板 |
| Batch A1 | Agent 主模型与迁移骨架 | `agents*` 新表、迁移脚本、repository/service 骨架 |
| Batch A2 | Thread/Task/状态机统一 | `threads*`、`tasks*`、统一状态枚举 |
| Batch A3 | Runtime Core 落地 | `kernel/runtime/*`、统一执行接口、旧执行器转接点 |
| Batch A4 | Agent 聚合根中心化 | AgentVersion/Binding/Publish、Bot 模板化方案 |
| Batch A5 | Workflow/Skill/Knowledge | Workflow 接入 Run，Knowledge 语义迁移，Skill 新域 |
| Batch A6 | Plugin/MCP/Registry | Plugin 安装层、MCP 集成层、capability registry |
| Batch A7 | API 重构与兼容层 | agent/chat/workflow/dataset/run API 转接与新接口落位 |
| Batch A8 | 前端 IA 与页面迁移 | 新导航、新 Agent 页面、Chat/Tasks/Observability |
| Batch A9 | 治理补齐与 legacy 清理 | policy/approval/cost/feedback 与旧结构删除 |

---

## 7. 当前仓库对应的优先改造点

以下文件/目录应优先作为第一轮改造入口：

### 第一优先级

- `app/app/modules/appcenter/domain/models.py`
- `app/app/modules/appcenter/runtime/router.py`
- `app/app/modules/agent/application/app_facade.py`
- `app/app/modules/workflow/runtime/engine.py`
- `app/app/kernel/trace/models.py`
- `app/app/kernel/execution/state_machine.py`

### 第二优先级

- `app/app/modules/chat/runtime/chat_executor.py`
- `app/app/modules/dataset/domain/models.py`
- `app/app/modules/dataset/runtime/*`
- `app/app/modules/bot/runtime/*`

### 第三优先级

- `web/src/routes.ts`
- `web/src/components/nav/root-sidebar.tsx`
- `web/src/pages/chat/*`
- `web/src/pages/bot/*`
- `web/src/pages/dataset/*`
- `web/src/pages/run/*`

---

## 8. 风险与回滚策略

| 风险 | 说明 | 回滚策略 |
|---|---|---|
| 数据模型迁移过大 | `App -> Agent`、`Dataset -> Knowledge` 涉及核心表 | 分阶段建新表，先桥接，后切流，最后删旧表 |
| 执行链路震荡 | Chat/Bot/Workflow/Agent 当前都有独立 executor | 先建立 Runtime Core，再逐模块转接，不直接全量替换 |
| 前后端联动成本高 | 前端当前没有 Agent 中心页 | 后端先提供兼容层，前端按 IA 分批迁移 |
| 测试断言失效 | 现有测试大量基于旧语义 | 每个 batch 同步迁移测试，不积压到最后 |
| 兼容层长期滞留 | 双轨运行最容易拖延 | 每个 phase 强制登记兼容层清单和删除计划 |

---

## 9. 阶段验收模板

每个阶段结束后，都应输出以下内容：

- 已迁移对象列表
- 未迁移对象列表
- 兼容层列表
- 删除计划列表
- 风险列表
- 测试覆盖列表
- 验收结果

---

## 10. 最终结论

SOIT-Pro 当前不是“从零开始重构”，而是：

- 已有一定统一运行时基础
- 已有 Agent 初始产品形态
- 但真实主中心仍是 AppCenter
- 前后端仍保留旧平台并列结构

因此最合理的推进路径不是先改 UI，而是：

1. 先去 App 化并建立 Runtime Core
2. 再让 Agent 真正成为唯一中心
3. 再重构 Workflow / Skill / Knowledge / Plugin / MCP
4. 最后迁移前端信息架构并清理旧结构

这份任务计划表可作为后续每一轮 Codex 实施的基线文档。
