# SOIT 大规模重构开发规划（激进版）

> 目标：以 **企业级 Agent 平台** 为最终形态，对 SOIT 进行一次以 **后端内核优先、Agent 中心化、前端后迁移** 为原则的大规模架构重构。
>
> 重构原则：**允许打破旧模块边界，允许重组数据模型，允许替换旧执行链路，不以短期兼容为最高优先级。**

---

# 1. 重构目标

## 1.1 产品目标

将 SOIT 从当前的多模块平台：

- chat
- bot
- dataset
- workflow
- agent
- plugin
- modelhub

重构为一个统一的 **Agent 中心化平台**：

- **Chat**：默认交互入口
- **Agent**：统一执行对象
- **Task / Run**：后台执行入口与结果载体
- **Workflow**：高级编排设计器
- **Knowledge**：知识资源中心
- **Skill**：可复用能力单元
- **Plugin**：扩展安装层
- **Observability**：运行治理中心

## 1.2 技术目标

建立一个可长期演进的统一内核：

- 单一运行时模型
- 单一任务状态机
- 单一 trace / artifact / feedback 体系
- 单一 app / publish / binding 体系
- Agent、Workflow、Knowledge、Skill、Plugin 全部围绕统一运行时工作

## 1.3 架构目标

完成从“模块并列架构”到“统一内核 + 能力分层架构”的迁移：

- 废除各模块独立执行宇宙
- 收敛旧模块对运行时的直接控制
- 把 Workflow / Knowledge / Skill / Tool / Plugin 变成 Agent 可组合能力
- 建立稳定的可观测、可恢复、可治理的运行底座

---

# 2. 重构原则

## 2.1 总原则

1. **先立新，再迁旧**
2. **先后端内核，再 Agent，再前端**
3. **优先统一对象模型，不优先保留旧 API 形态**
4. **允许临时适配层，但不做长期双轨制**
5. **以运行时稳定性优先于页面完成度**

## 2.2 激进重构原则

本次重构允许：

- 大规模重命名领域对象
- 大规模迁移表结构
- 合并旧模块 service/repository
- 删除不再符合新架构的 runtime 代码
- 前端路由和页面结构重组
- 暂时牺牲部分旧功能以换取内核统一

## 2.3 禁止事项

- 不允许继续给 chat / bot / workflow / agent 维持四套执行模型
- 不允许继续让 plugin / tool / skill 语义混乱
- 不允许继续新增基于旧模块边界的表结构
- 不允许前端继续扩张旧导航而不收敛核心对象

---

# 3. 目标架构

## 3.1 目标分层

### A. Core Kernel（平台内核）

- identity / tenant / workspace
- app registry
- run engine
- task engine
- trace engine
- artifact store
- policy / approval engine
- feedback / eval base

### B. Capability Layer（能力层）

- llm capability
- retrieval capability
- workflow capability
- tool capability
- skill capability
- memory capability

### C. Resource Layer（资源层）

- models
- knowledge
- workflows
- skills
- tools
- plugins
- secrets
- policies

### D. Experience Layer（体验层）

- chat
- agents
- tasks
- workflow designer
- plugin manager
- observability UI

## 3.2 核心对象

目标核心对象如下：

- `agent`
- `thread`
- `run`
- `run_step`
- `run_artifact`
- `task`
- `skill`
- `workflow`
- `knowledge_base`
- `tool`
- `plugin`
- `app`
- `app_version`
- `binding`
- `feedback`

## 3.3 最终关系

- Agent 是最终面向用户和运行时的核心对象
- Chat 是 Agent 的默认交互方式
- Task 是 Agent 的后台执行方式
- Workflow 是 Agent 的编排设计器和 Skill 的实现方式
- Skill 是 Agent 的可复用能力单元
- Tool 是 Agent 可调用的动作能力
- Plugin 是平台扩展安装包，可导出 Tool / Skill / Connector / Resource
- Knowledge 是 Agent / Workflow / Skill 共享的知识资源

---

# 4. 现有系统问题归纳

## 4.1 领域模型问题

- chat / bot / workflow / agent / appcenter 共存，职责重叠
- dataset 语义过旧，不符合企业 AI 平台表达
- plugin / tool / skill 概念未分层
- appcenter 已开始统一，但未成为真正单一发布中心

## 4.2 运行时问题

- 多套 executor 并存
- 多套 run/trace 逻辑并存
- chat 与后台 agent 运行链路未统一
- workflow 运行未完全纳入统一 run 模型

## 4.3 前端信息架构问题

- 仍以模块并列导航为主
- 缺少 Agent 中心化视角
- Chat 与 Agent 逻辑割裂
- Workflow 与最终交付对象关系不清晰

## 4.4 长期演进问题

- 模块各自沉淀状态和发布逻辑，后续维护成本持续放大
- 新功能如果继续叠加在旧边界上，会进一步破坏内核统一性

---

# 5. 总体实施策略

## 5.1 三阶段路线

### 第一阶段：后端内核重构

目标：完成统一运行时、统一资源中心、统一状态与追踪底座。

### 第二阶段：Agent 中心化重构

目标：把 Agent 升级为统一执行对象，接管 Chat 和后台 Task 两种模式。

### 第三阶段：前端迁移与产品收敛

目标：把前台从模块式导航迁移到 Agent 中心化平台。

## 5.2 执行方式

- 使用新目录和新服务先立新内核
- 旧模块通过 adapter 接入新内核
- 达到切换条件后逐步删除旧 runtime
- 最终完成前台路由、数据接口、领域对象统一

---

# 6. P0：后端内核大重构

# 6.1 Kernel 目标

本阶段目标：

- 完成统一运行时模型
- 完成统一任务状态机
- 完成 app/app_version/binding 统一资源中心
- 完成 Knowledge / Plugin / Tool / Skill 分层基础
- 废除旧模块各自维护运行时的趋势

---

## P0-A 统一领域模型与目录结构

### 目标

重组后端目录，让领域边界与目标架构一致。

### 新建议目录

```text
app/
  kernel/
    identity/
    app_registry/
    runtime/
    tasks/
    traces/
    artifacts/
    policy/
    approvals/
    feedback/
  domains/
    agents/
    workflows/
    knowledge/
    skills/
    tools/
    plugins/
    models/
  adapters/
    llm/
    retrieval/
    queue/
    storage/
    mcp/
  interfaces/
    api/
    workers/
    schedulers/
```

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P0-A1 | 定义新目录结构 | 明确 kernel / domains / adapters / interfaces |
| P0-A2 | 新建领域边界文档 | 每个域的职责、输入输出、依赖方向 |
| P0-A3 | 梳理旧模块映射关系 | chat/bot/dataset/workflow/agent/pluginmarket -> 新领域 |
| P0-A4 | 建立迁移适配层清单 | 明确哪些旧 service 先适配、哪些直接废弃 |
| P0-A5 | 统一 service 命名规范 | usecase / service / repository / gateway 统一 |

### 验收标准

- 新目录结构建立完成
- 旧模块迁移映射清单完成
- 开发不再继续扩写旧领域边界

---

## P0-B 统一运行时模型（Run Engine）

### 目标

建立全平台唯一执行模型。

### 核心对象

- `thread`
- `run`
- `run_step`
- `run_artifact`
- `run_feedback`

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P0-B1 | 设计统一 run schema | 明确 run 类型、模式、状态、来源 |
| P0-B2 | 设计统一 step schema | llm/tool/retrieval/workflow/skill/approval 等类型 |
| P0-B3 | 设计统一 artifact schema | text/json/file/report/table 等 |
| P0-B4 | 设计统一 thread schema | 对话线程与任务线程统一抽象 |
| P0-B5 | 设计统一 feedback schema | 用户反馈、人工评分、系统评测入口 |
| P0-B6 | 抽象 runtime_core service | 启动 run、推进 step、写 trace、产出 artifact |
| P0-B7 | 实现 run event publisher | 生命周期事件统一发布 |
| P0-B8 | 提供 run query service | 支持详情、列表、重放、筛选 |

### 数据库任务

| 编号 | 任务 | 说明 |
|---|---|---|
| P0-B9 | 重构 runs 表 | 增加 source_type、execution_mode、entry_type 等 |
| P0-B10 | 重构 run_steps 表 | step_type、status、input、output、trace_ref |
| P0-B11 | 重构 run_artifacts 表 | artifact_type、mime、storage_ref、preview_payload |
| P0-B12 | 新增 run_feedback 表 | 评价、标签、备注、评分 |
| P0-B13 | 新增 run_threads 表 | thread 与 agent/app/user 关系 |

### 验收标准

- Chat / Agent / Workflow 至少一种执行链路切到新 run engine
- 所有新执行必须记录 run、step、artifact

---

## P0-C 统一任务状态机（Task Engine）

### 目标

支持后台 Agent 长任务、恢复、重试、审批等待。

### 状态机建议

- `queued`
- `preparing`
- `running`
- `waiting_input`
- `waiting_approval`
- `paused`
- `retrying`
- `succeeded`
- `failed`
- `canceled`
- `expired`

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P0-C1 | 设计 task schema | task 与 run 的关联方式 |
| P0-C2 | 实现 task state machine | 状态转换规则与 guard |
| P0-C3 | 增加 pause/resume API | 后台任务可控 |
| P0-C4 | 增加 retry/cancel API | 标准恢复控制 |
| P0-C5 | 设计 checkpoint 模型 | step 级或 node 级恢复 |
| P0-C6 | 集成队列执行器 | celery/redis 或统一队列适配层 |
| P0-C7 | 设计 timeout/lease 机制 | 防止僵尸任务 |
| P0-C8 | 实现任务事件记录 | 任务状态变更写 trace |

### 数据库任务

| 编号 | 任务 | 说明 |
|---|---|---|
| P0-C9 | 重构 tasks 表 | 关联 run_id、agent_id、execution_mode |
| P0-C10 | 新增 task_checkpoints 表 | 保存恢复点 |
| P0-C11 | 新增 task_events 表 | 状态、原因、操作人、时间 |

### 验收标准

- 后台任务支持启动、暂停、继续、重试、取消
- 任一失败任务可从 checkpoint 恢复

---

## P0-D 统一 Trace / Artifact / Replay 内核

### 目标

构建长期调试和治理基础。

### Trace Event 类型建议

- run_started
- run_completed
- run_failed
- step_started
- step_completed
- step_failed
- llm_requested
- llm_completed
- tool_called
- tool_result
- retrieval_started
- retrieval_result
- workflow_entered
- workflow_exited
- skill_invoked
- approval_requested
- approval_resolved
- artifact_created

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P0-D1 | 统一 trace event schema | payload、severity、correlation_id |
| P0-D2 | 统一 trace writer | 各执行器统一写法 |
| P0-D3 | 统一 artifact writer | 文件/文本/结构化产物统一落库 |
| P0-D4 | 设计 run replay service | 支持回放执行过程 |
| P0-D5 | 设计 step inspect service | 单 step 调试查看 |
| P0-D6 | 增加 token/cost/latency 收集 | 后续 observability 基础 |
| P0-D7 | 建立 trace 与 artifact 关联 | 页面可直接查看结果链路 |

### 验收标准

- 任意 run 都能查看 step timeline
- 任意 artifact 都能追溯其来源 step

---

## P0-E App Registry / Publish 中心重构

### 目标

让 appcenter 成为真正唯一发布中心。

### 核心对象

- `app`
- `app_version`
- `app_binding`
- `app_publish`

### Binding 类型建议

- model_binding
- workflow_binding
- knowledge_binding
- skill_binding
- tool_binding
- plugin_binding
- policy_binding
- secret_profile_binding

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P0-E1 | 重构 app 领域模型 | 区分 app profile 与 runtime binding |
| P0-E2 | 重构 app_version 模型 | 可发布、可回滚、可比较 |
| P0-E3 | 增加统一 binding 表 | 所有能力通过 binding 关联 |
| P0-E4 | 统一 publish 流程 | chat/bot/workflow/agent 不再各自发布 |
| P0-E5 | 增加版本快照机制 | 发布时固化资源引用 |
| P0-E6 | 增加 app resolve service | 运行前解析真实执行配置 |

### 数据库任务

| 编号 | 任务 | 说明 |
|---|---|---|
| P0-E7 | 重构 apps 表 | app_type、entry_mode、owner_scope |
| P0-E8 | 重构 app_versions 表 | version_no、status、snapshot |
| P0-E9 | 新增 app_bindings 表 | 通用绑定对象 |
| P0-E10 | 新增 app_publishes 表 | 发布记录、环境、回滚信息 |

### 验收标准

- 新 App 发布只能走统一 publish service
- 旧模块发布能力进入弃用名单

---

## P0-F Knowledge 内核重构（Dataset -> Knowledge）

### 目标

将 dataset 重构为企业知识能力层。

### 核心对象

- `knowledge_base`
- `knowledge_document`
- `knowledge_chunk`
- `knowledge_index`
- `retrieval_profile`
- `ingestion_run`

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P0-F1 | 重命名产品语义 | dataset 对外统一为 knowledge |
| P0-F2 | 重构知识对象模型 | base/document/chunk/profile/index |
| P0-F3 | 抽象 ingestion pipeline | 上传、解析、切块、索引 |
| P0-F4 | 抽象 retrieval service | Agent / Workflow / Skill 共用 |
| P0-F5 | 增加 citation / grounding 结构 | 回答可追溯来源 |
| P0-F6 | 知识运行写入 run/trace | ingestion/retrieval 都进入统一观察体系 |

### 验收标准

- Agent 调用知识检索走统一 retrieval service
- 知识导入与检索都有 run/trace 记录

---

## P0-G Tool / Skill / Plugin 三层分离基础

### 目标

彻底厘清扩展体系。

### 定义

- **Tool**：运行时动作能力
- **Skill**：可复用业务能力
- **Plugin**：安装与分发单元

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P0-G1 | 定义 tool 领域模型 | schema、capability、auth、policy |
| P0-G2 | 定义 skill 领域模型草案 | 先做 schema 与 binding 设计 |
| P0-G3 | 重定义 plugin manifest | 可导出 tools/skills/resources/connectors |
| P0-G4 | 建立 capability registry | Tool/Skill/Plugin 导出统一注册 |
| P0-G5 | 增加权限模型 | plugin 安装权限、tool 使用权限、skill 使用权限 |
| P0-G6 | 设计启停/升级/卸载流程 | Plugin 生命周期标准化 |

### 验收标准

- Plugin 不再被运行时当作直接动作能力
- Agent 只面向 Tool / Skill / Knowledge / Workflow

---

## P0-H 旧执行链路下线计划

### 目标

避免长期双轨制。

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P0-H1 | 盘点旧 executor 清单 | chat/bot/workflow/agent/appcenter |
| P0-H2 | 标注新旧替换关系 | 谁被 runtime_core 替代 |
| P0-H3 | 建立 deprecated 清单 | 明确禁止新增开发的旧服务 |
| P0-H4 | 加适配层而非继续扩写旧逻辑 | 临时兼容，最终删除 |
| P0-H5 | 制定删除时机 | 哪个阶段正式删除旧 executor |

---

# 7. P1：Agent 模块重构与中心化

# 7.1 Agent 目标

让 Agent 成为平台唯一核心执行对象，统一承担：

- Chat 对话执行
- 后台 Task 执行
- Workflow 编排调用
- Knowledge 检索增强
- Skill 调用
- Tool 调用
- Policy / Approval 控制

---

## P1-A Agent 领域模型重构

### 核心对象

- `agent`
- `agent_profile`
- `agent_version`
- `agent_binding`
- `agent_thread`

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P1-A1 | 重构 agent aggregate | profile、instructions、mode、publish state |
| P1-A2 | 建立 agent_version | 可发布、可回滚、可比较 |
| P1-A3 | 建立 agent_bindings | 绑定 model/knowledge/workflow/skill/tool/policy |
| P1-A4 | 建立 agent_thread 关系 | Chat 会话归属到 agent |
| P1-A5 | 建立 agent_task 关系 | 后台任务归属到 agent |

### 验收标准

- 新 agent 成为独立一等对象
- Chat 和 Task 都能明确归属某个 agent

---

## P1-B Agent Pipeline 标准化

### 目标

统一 planner / executor / verifier 流程。

### 建议阶段

- input_normalization
- context_loading
- planning
- decision
- execution
- observation
- verification
- finalization

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P1-B1 | 设计 agent pipeline 接口 | 各阶段输入输出类型 |
| P1-B2 | 抽象 planner 为 stage | 不再散落在模块内部 |
| P1-B3 | 抽象 executor 为 stage | 调 tool/workflow/skill/retrieval |
| P1-B4 | 抽象 verifier 为 stage | 统一结果校验 |
| P1-B5 | 抽象 budget/rate/iterations 策略 | 集中到 policy layer |
| P1-B6 | memory hook 标准化 | load/write hooks |

### 验收标准

- Agent 执行流程成为标准 pipeline
- 不再出现 agent 内部散落逻辑无统一阶段模型

---

## P1-C Chat Mode 与 Task Mode 统一

### 目标

同一个 Agent 同时支持即时对话和后台执行。

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P1-C1 | 设计 execution_mode | chat / task |
| P1-C2 | Chat mode 走 run engine | 生成 thread/run/step/artifact |
| P1-C3 | Task mode 走 task engine | 任务提交后驱动 run |
| P1-C4 | 统一输入模型 | text / file / json / form |
| P1-C5 | 统一输出模型 | message / artifact / structured result |
| P1-C6 | 增加 chat 中提交后台任务能力 | 对话中可转 task |

### 验收标准

- 同一 Agent 可同时服务 chat 和 task 两种模式

---

## P1-D Skill 正式落地

### 核心对象

- `skill`
- `skill_version`
- `skill_binding`
- `skill_publish`

### Skill 绑定建议

- prompt/instructions
- tools
- workflow
- knowledge scope
- output schema
- approval policy
- retry/fallback policy

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P1-D1 | 建 skill 基础表 | 对象、版本、绑定 |
| P1-D2 | 建 skill resolve service | 运行时解析 skill 能力 |
| P1-D3 | Agent 挂载 skill | 多 skill 绑定 |
| P1-D4 | Workflow 调用 skill | 节点类型扩展 |
| P1-D5 | Plugin 导出 skill | 安装后注册 |
| P1-D6 | Skill 运行进入 run engine | 与 trace/artifact 打通 |

### 验收标准

- Skill 成为正式能力对象
- Agent / Workflow / Plugin 可复用 Skill

---

## P1-E Workflow 重构为 Agent 编排层

### 目标

Workflow 保留，但不再是独立执行孤岛。

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P1-E1 | 重构 workflow 发布目标 | 发布为 agent binding / skill / task template |
| P1-E2 | workflow 节点扩展 | agent_node / skill_node / approval_node |
| P1-E3 | workflow 运行进入统一 run engine | step/trace/artifact 一体化 |
| P1-E4 | workflow resolve service | 运行前解析节点依赖 |
| P1-E5 | 子流程能力标准化 | 支持 workflow as subgraph |

### 验收标准

- Workflow 作为 Agent 编排层成立
- Workflow 不再维护独立 run 宇宙

---

## P1-F Agent 治理能力补齐

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P1-F1 | 增加 agent policy binding | budget / iterations / tool allowlist |
| P1-F2 | 审批机制接入 agent | 高风险操作需审批 |
| P1-F3 | 审计日志串联 | 人、agent、task、tool 全链路 |
| P1-F4 | secret usage trace | 哪个 agent 用了哪些 secret |
| P1-F5 | 知识权限边界 | agent 只能访问授权 knowledge scope |

### 验收标准

- Agent 具备企业级治理基础

---

## P1-G Agent API 重构

### 目标

提供清晰的新 API 面。

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P1-G1 | 新建 agent create/update/publish API | 以绑定关系为中心 |
| P1-G2 | 新建 agent chat API | 启动/续接 thread |
| P1-G3 | 新建 agent task submit API | 后台执行入口 |
| P1-G4 | 新建 agent runs API | 查看运行记录 |
| P1-G5 | 新建 agent artifacts API | 查看产物 |
| P1-G6 | 新建 agent bindings API | 管理 tool/skill/knowledge/workflow |

---

# 8. P2：前端迁移与体验重构

# 8.1 前端目标

把前台从“模块并列系统”迁移到“Agent 中心平台”。

---

## P2-A 信息架构重组

### 新导航建议

- Agents
- Chat
- Workflows
- Knowledge
- Plugin
- Models
- Tasks
- Observability
- Settings

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P2-A1 | 重构侧边栏 IA | Agent 为中心，保留高级设计入口 |
| P2-A2 | 旧模块入口重新分组 | bot 弱化、dataset 改 knowledge |
| P2-A3 | 增加 Agent 主导航 | 列表、详情、创建、发布 |
| P2-A4 | 增加 Tasks 主导航 | 后台任务视角 |
| P2-A5 | 增加 Observability 主导航 | 运行治理视角 |

---

## P2-B Chat 并入 Agent 视角

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P2-B1 | Chat 页接入 agent selector | 与具体 agent 对话 |
| P2-B2 | 会话归属展示 | 当前会话属于哪个 agent |
| P2-B3 | Chat 消息渲染 trace 信息 | tool/retrieval/skill/task |
| P2-B4 | 支持聊天中转后台任务 | 用户从对话提交 task |
| P2-B5 | 支持展示 artifacts | 报告、文件、结构化结果 |

### 验收标准

- Chat 不再是独立产品逻辑，而是 Agent 的默认模式

---

## P2-C Agent 详情页建设

### 建议页签

- 对话
- 任务
- 知识
- 技能
- 编排
- 运行记录
- 配置

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P2-C1 | 新建 Agent 详情页骨架 | 统一承载主要能力 |
| P2-C2 | 接入绑定管理 | knowledge/skill/workflow/tool/plugin |
| P2-C3 | 接入任务列表与运行记录 | 后台执行视图 |
| P2-C4 | 接入 artifact 结果展示 | 输出结果统一沉淀 |
| P2-C5 | 接入配置页 | 模型、策略、权限、发布 |

---

## P2-D Workflow 设计器保留并升级

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P2-D1 | Workflow 入口保留 | 面向高级用户 |
| P2-D2 | 增加发布目标选择 | 发布到 Agent / Skill / Task Template |
| P2-D3 | Agent 页内跳转到编排 | 打通 Agent <-> Workflow |
| P2-D4 | 增加节点调试面板 | run/trace 联动 |
| P2-D5 | 增加 skill node / approval node UI | 匹配后端新能力 |

---

## P2-E Knowledge 前端迁移

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P2-E1 | dataset 页面文案升级为 knowledge | 先改语义 |
| P2-E2 | 重构知识对象页面 | base/document/ingestion/profile |
| P2-E3 | 增加 retrieval 配置页 | 供 Agent 绑定时选择 |
| P2-E4 | 增加入库运行记录页 | ingestion run 可视化 |

---

## P2-F Plugin 页面重构

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P2-F1 | 保留 Plugin 模块名 | 先不改命名 |
| P2-F2 | 页面定位改为安装中心 | 已安装/可升级/权限/导出对象 |
| P2-F3 | 展示导出能力 | tools / skills / resources / connectors |
| P2-F4 | 增加安装配置页 | manifest、权限、配置项 |
| P2-F5 | 增加启停/升级/卸载动作 | 完整生命周期 |

---

## P2-G Observability 前台建设

### 页面建议

- Runs
- Run Detail
- Task Detail
- Step Timeline
- Trace Explorer
- Artifact Viewer
- Cost Dashboard

### 任务表

| 编号 | 任务 | 说明 |
|---|---|---|
| P2-G1 | 新建 runs 列表页 | 搜索、过滤、状态 |
| P2-G2 | 新建 run 详情页 | step timeline、trace、artifact |
| P2-G3 | 新建 task 详情页 | 状态机、checkpoint、操作 |
| P2-G4 | 新建 artifact 查看器 | 文本/json/file/report |
| P2-G5 | 新建成本与延迟概览 | 基础治理数据 |

---

# 9. 数据模型重构任务表

## 9.1 新增或重构重点表

| 类别 | 表名建议 | 说明 |
|---|---|---|
| Runtime | runs | 统一执行记录 |
| Runtime | run_steps | 执行步骤 |
| Runtime | run_artifacts | 执行产物 |
| Runtime | run_feedback | 反馈 |
| Runtime | run_threads | 线程 |
| Tasks | tasks | 后台任务 |
| Tasks | task_checkpoints | 恢复点 |
| Tasks | task_events | 状态事件 |
| App Registry | apps | 应用对象 |
| App Registry | app_versions | 应用版本 |
| App Registry | app_bindings | 通用绑定 |
| App Registry | app_publishes | 发布记录 |
| Agent | agents | agent 主对象 |
| Agent | agent_versions | agent 版本 |
| Agent | agent_bindings | agent 绑定 |
| Skill | skills | skill 主对象 |
| Skill | skill_versions | skill 版本 |
| Skill | skill_bindings | skill 绑定 |
| Knowledge | knowledge_bases | 知识库 |
| Knowledge | knowledge_documents | 文档 |
| Knowledge | knowledge_chunks | 分块 |
| Knowledge | retrieval_profiles | 检索配置 |
| Plugin | plugins | 插件主对象 |
| Plugin | plugin_versions | 插件版本 |
| Plugin | plugin_exports | 导出能力清单 |
| Tool | tools | 工具清单 |
| Tool | tool_versions | 工具版本 |

## 9.2 迁移策略建议

### 迁移原则

- 新表优先
- 旧表尽量只做数据搬运，不继续承载新逻辑
- 关键旧表保留只读迁移窗口
- 发布切换后逐步冻结旧表写入

### 迁移步骤

1. 新建新架构表
2. 写数据转换脚本
3. 旧数据回填到新表
4. 新服务切换到新表
5. 停止旧表写入
6. 最后删除旧表或保留归档

---

# 10. API 重构任务表

## 10.1 新 API 分组建议

- `/agents/*`
- `/chat/*`
- `/tasks/*`
- `/runs/*`
- `/workflows/*`
- `/knowledge/*`
- `/skills/*`
- `/plugins/*`
- `/models/*`
- `/observability/*`

## 10.2 API 任务

| 编号 | 任务 | 说明 |
|---|---|---|
| API-1 | 新建 Agent API 分组 | 替代零散 agent/bot/chat API |
| API-2 | 新建 Chat API 分组 | 只保留会话视角，底层归 Agent |
| API-3 | 新建 Task API 分组 | 后台任务控制 |
| API-4 | 新建 Run API 分组 | 统一运行记录查询 |
| API-5 | 新建 Skill API 分组 | 新能力对象 |
| API-6 | 新建 Knowledge API 分组 | dataset 升级 |
| API-7 | 重构 Plugin API 分组 | 安装中心 |
| API-8 | 建立兼容层 | 短期兼容旧前端调用 |
| API-9 | 标记弃用旧 API | 输出 deprecated 列表 |

---

# 11. 测试与质量保障任务表

## 11.1 测试优先级

### 第一优先

- runtime_core
- task_state_machine
- app_registry
- agent_pipeline
- workflow_integration
- knowledge_retrieval
- plugin_installation

### 第二优先

- 前端关键流
- run/trace/artifact 可视化接口
- agent chat/task 切换链路

## 11.2 测试任务

| 编号 | 任务 | 说明 |
|---|---|---|
| QA-1 | 建立 runtime 集成测试 | run/step/artifact 全链路 |
| QA-2 | 建立 task 状态机测试 | pause/resume/retry/cancel |
| QA-3 | 建立 agent pipeline 测试 | chat/task 两种模式 |
| QA-4 | 建立 workflow->run 测试 | 节点、子流程、审批 |
| QA-5 | 建立 knowledge retrieval 测试 | 检索、引用、权限 |
| QA-6 | 建立 plugin install/export 测试 | manifest/permissions/exports |
| QA-7 | 建立 API 回归测试 | 新旧接口关键链路 |
| QA-8 | 建立迁移脚本验证测试 | 数据迁移正确性 |

---

# 12. Codex 执行建议

## 12.1 推荐执行顺序

### Sprint 1：立新骨架

- 新目录结构
- 新领域模型
- runtime core 基础对象
- task state machine 基础对象
- app registry 重构草案

### Sprint 2：打通统一运行时

- runs/steps/artifacts/threads/tasks 新表
- runtime_core service
- trace writer / artifact writer
- 第一条执行链路切换

### Sprint 3：Knowledge / Plugin / Tool 新分层

- dataset -> knowledge 内核
- plugin manifest / registry 重构
- tool 领域模型新建

### Sprint 4：Agent 中心化

- agent aggregate 重构
- chat mode / task mode 打通
- agent bindings
- 新 agent API

### Sprint 5：Skill / Workflow 打通

- skill 基础对象
- workflow 变成编排层
- workflow -> agent/skill/task template 发布

### Sprint 6：前端迁移

- 新导航
- Agent 详情页
- Chat 并入 Agent
- Plugin 页面改造
- Observability 页面建设

## 12.2 Codex 提示建议

建议把 Codex 的工作拆成这几类 prompt：

1. **架构迁移型**
   - 新建目录
   - 重构领域边界
   - 抽象统一接口

2. **数据迁移型**
   - 生成 Alembic 迁移
   - 生成旧数据迁移脚本
   - 补齐 repository/service 改造

3. **链路打通型**
   - 打通 agent chat run
   - 打通 task lifecycle
   - 打通 workflow run integration

4. **前端迁移型**
   - 新页面骨架
   - 老页面复用接线
   - 新导航和详情页组织

---

# 13. 风险与控制建议

## 13.1 主要风险

### 风险 1：双轨制长期存在

控制方式：
- 每阶段明确替换目标
- 输出 deprecated 清单
- 禁止继续扩写旧 runtime

### 风险 2：表结构迁移过大导致数据混乱

控制方式：
- 新表优先
- 做迁移脚本与回滚脚本
- 分环境验证迁移

### 风险 3：前端过早跟随导致返工

控制方式：
- 前端最后迁移
- 先完成内核和 Agent API
- 前端以 adapter 方式过渡

### 风险 4：Agent 中心化后 Workflow 被边缘化失去价值

控制方式：
- 明确 Workflow 是高级编排设计器
- 保留独立入口
- 与 Agent 编排页打通

### 风险 5：Plugin / Skill / Tool 再次混淆

控制方式：
- 先冻结定义
- 所有新开发必须遵守分层
- manifest / binding / registry 明确各自职责

---

# 14. 验收里程碑

## 里程碑 M1：新内核成立

判定条件：
- 新 runtime_core 可运行
- tasks 状态机可运行
- runs/steps/artifacts 新链路可写
- 新 app registry 可解析 app 运行配置

## 里程碑 M2：Agent 成为统一执行对象

判定条件：
- Agent 可直接 chat
- Agent 可提交后台 task
- Chat 与 Task 走同一 run 底座
- Workflow / Knowledge / Tool 可挂到 Agent

## 里程碑 M3：能力层清晰

判定条件：
- Skill 对象正式可用
- Workflow 可发布到 Agent / Skill / Task Template
- Plugin 仅承担安装与导出职责

## 里程碑 M4：前台收敛完成

判定条件：
- 新导航完成
- Agent 详情页成为核心操作页
- Chat 归属 Agent
- Tasks / Observability 页面可用

---

# 15. 最终建议

这次重构建议明确采取以下策略：

## 必须坚持的三件事

1. **先做后端内核，不被前端页面牵着走**
2. **先把 Agent 立成中心对象，再谈模块整合**
3. **先把 Tool / Skill / Plugin / Workflow / Knowledge 分层定死，再继续开发**

## 不建议的做法

- 不建议在旧架构上继续局部修补
- 不建议为了兼容现有页面而放弃统一运行时
- 不建议让 Chat、Workflow、Agent 继续各走各路

## 一句话结论

> 本次重构的核心不是“把模块换个名字”，而是把 SOIT 真正改造成一个 **以 Agent 为中心、以统一运行时为底座、以 Workflow/Skill/Knowledge/Plugin 为能力层的企业级 AI 平台**。

