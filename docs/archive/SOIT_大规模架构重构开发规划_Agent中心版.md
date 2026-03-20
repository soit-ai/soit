# SOIT 大规模架构重构开发规划（基于 Agent 中心蓝图）

> Archive note
> 本文档是重构规划文档，保留用于理解设计来源与阶段目标，不代表仓库当前实现状态。
> 当前实现与目录边界请优先参考：
> `README.md`
> `app/docs/architecture/PROJECT_STRUCTURE.md`
> `app/docs/architecture/KERNEL_V1_DATA_MODEL.md`
> `web/docs/PROJECT_STRUCTURE.md`

## 1. 文档目标

本文档基于 **SOIT Agent 中心版新蓝图** 与 **Codex 架构约束清单**，输出一份可直接执行的大规模重构开发规划。

本次规划默认采用 **激进重构策略**：

- 不以兼容旧的 `App` 概念为优先目标
- 不以保留旧模块边界为优先目标
- 不以最小改动为优先目标
- 以 **统一内核、统一对象模型、统一运行时、长期可演进** 为第一优先级

本文档用于：
- 指导 Codex 进行多阶段重构
- 约束开发顺序，防止前端先行、内核滞后
- 明确模块迁移方向
- 明确数据模型重构方向
- 明确阶段性交付物与验收标准

---

## 2. 重构总原则

### 2.1 去 App 化，全面 Agent 化
前后端全面去掉 `App` 相关主概念，统一收敛为：

- Agent
- AgentVersion
- AgentBinding
- AgentPublish

### 2.2 单内核优先
所有执行统一进入 Runtime Core，统一走：

- Thread
- Run
- RunStep
- Task
- Artifact
- Trace
- Feedback

### 2.3 能力层与扩展层分离
必须明确区分：

- Tool：动作能力
- Skill：业务能力
- Workflow：编排能力
- Plugin：扩展安装层
- MCP：标准接入层

### 2.4 后端先行
重构顺序必须是：

1. 后端内核
2. Agent 能力层
3. Workflow / Skill / Knowledge / Plugin / MCP
4. 前端迁移
5. 观测与治理补齐

### 2.5 旧结构允许短期并存，但不允许长期双轨
迁移过程中允许保留临时兼容层，但必须有清晰删除计划。

---

## 3. 重构目标架构

### 3.1 顶层结构
SOIT 最终收敛为以下核心域：

- `kernel/runtime`
- `kernel/trace`
- `kernel/policy`
- `kernel/security`
- `modules/agent`
- `modules/workflow`
- `modules/skill`
- `modules/knowledge`
- `modules/modelhub`
- `modules/plugin`
- `modules/integrations/mcp`
- `modules/observability`
- `modules/identity`

### 3.2 前台结构
长期导航收敛为：

- Agents
- Chat
- Workflows
- Knowledge
- Plugin
- Models
- Tasks
- Observability
- Settings

### 3.3 核心对象
统一核心对象为：

- Agent
- AgentVersion
- AgentBinding
- AgentPublish
- Thread
- Run
- RunStep
- Task
- Artifact
- Feedback
- Workflow
- Skill
- KnowledgeBase
- Tool
- Plugin
- MCPConnector

---

## 4. 重构阶段总览

## Phase 0：重构准备期
目标：冻结架构边界，建立新蓝图约束，避免边改边漂移。

## Phase 1：后端核心对象与 Runtime Core 重构
目标：去 App 化，统一 Agent 中心模型与运行时内核。

## Phase 2：Agent 模块中心化重构
目标：把 Agent 真正做成唯一主对象与统一执行入口。

## Phase 3：Workflow / Skill / Knowledge / Plugin / MCP 能力层重构
目标：完成能力层与接入层边界重建。

## Phase 4：前端 Agent 中心化迁移
目标：将前台从旧模块平台迁移为 Agent 中心平台。

## Phase 5：Observability / Policy / Governance 完善
目标：完成平台长期可维护性与生产级治理能力。

## Phase 6：清理兼容层与删除旧结构
目标：完成旧概念下线与最终收口。

---

# 5. Phase 0：重构准备期

## 5.1 任务目标
在真正开始大规模改造前，先冻结架构方向。

## 5.2 任务清单

### 任务 0-1：冻结架构基线
- 固化《SOIT 平台新蓝图（Agent 中心版）》
- 固化《SOIT Codex 可直接执行的架构约束清单》
- 明确后续所有实现必须遵守蓝图

### 任务 0-2：建立重构分支策略
- 建立大重构专用主分支
- 模块级重构按 phase 或 domain 分支推进
- 约定兼容层命名规则、删除标记规则

### 任务 0-3：建立旧新对象映射表
输出旧结构到新结构映射：
- App → Agent
- AppVersion → AgentVersion
- AppBinding → AgentBinding
- Dataset → Knowledge
- Bot → Agent Template / LegacyBot
- PluginMarket → Plugin
- AppCenter Runtime → Runtime Core

### 任务 0-4：建立“禁止新增旧结构”检查项
- 不允许新建 App*
- 不允许新增独立 executor
- 不允许新增 dataset 产品语义
- 不允许 MCP 独立膨胀为业务中心模块

### 任务 0-5：建立阶段验收模板
每个 phase 需有：
- 已迁移对象列表
- 未迁移对象列表
- 兼容层列表
- 删除计划列表
- 风险列表
- 验收结果

---

# 6. Phase 1：后端核心对象与 Runtime Core 重构

## 6.1 目标
完成平台核心对象统一与运行时内核统一。

## 6.2 子目标
- 去掉 App 主模型
- 建立 Agent 主模型
- 建立统一 Run / Task / Trace / Artifact 体系
- 建立统一状态机
- 建立统一执行入口

## 6.3 数据模型任务

### 任务 1-1：Agent 主模型落地
新增或重构：
- `agents`
- `agent_versions`
- `agent_bindings`
- `agent_publishes`

要求：
- 替代原 `apps` / `app_versions` / `app_bindings` / `app_publishes`
- 明确 Agent 作为唯一主对象
- 版本与绑定必须围绕 Agent 组织

### 任务 1-2：Thread 模型标准化
新增或整理：
- `threads`
- `thread_messages`
- `thread_context_snapshots`（可选）

要求：
- Thread 必须从属于 Agent
- 不允许 Thread 成为独立业务主对象
- Chat 全部归属 Thread + Agent

### 任务 1-3：Run 模型统一
统一或重构：
- `runs`
- `run_steps`
- `run_artifacts`
- `run_cost_entries`
- `run_feedbacks`

要求：
- 所有执行都落到 Run
- Run 必须是唯一执行记录对象
- 各模块不能自建平行 result/log/output 表

### 任务 1-4：Task 模型统一
重构或补充：
- `tasks`
- `task_checkpoints`
- `task_events`

要求：
- Task 必须关联 Run
- Task 只负责后台执行调度与状态控制
- 后台长任务必须支持 checkpoint

### 任务 1-5：统一状态机定义
建立统一状态语义：
- queued
- preparing
- running
- waiting_input
- waiting_approval
- paused
- retrying
- succeeded
- failed
- canceled
- expired

要求：
- Run / Task 共用状态语言
- 模块内不允许自定义不兼容状态机

---

## 6.4 Runtime Core 任务

### 任务 1-6：建立 Runtime Core 目录与接口
新增或重构：
- `kernel/runtime/core`
- `kernel/runtime/contracts`
- `kernel/runtime/executors`
- `kernel/runtime/orchestrators`
- `kernel/runtime/checkpoints`

### 任务 1-7：建立统一执行入口
要求：
- Chat Mode 与 Task Mode 都通过 Runtime Core 驱动
- Runtime Core 统一创建 Run
- Runtime Core 统一写 RunStep / Artifact / Trace

### 任务 1-8：拆分 Capability Executor
按能力拆分执行器：
- llm executor
- tool executor
- workflow executor
- retrieval executor
- skill executor
- approval executor

要求：
- 不允许 chat / workflow / agent 各自维护完整执行内核
- 各模块只能提供 capability adapter

### 任务 1-9：统一 Retry / Resume / Cancel 机制
要求：
- 所有长任务都通过 Runtime Core 支持恢复
- 失败重试统一接入 Runtime Core
- 取消逻辑统一接入 Runtime Core
- 不允许模块自带一套恢复逻辑

### 任务 1-10：统一 Artifact 写入接口
要求：
- 所有结果必须通过统一 artifact service 输出
- Artifact 支持 text / json / file / report 等类型
- 支持 run/task/agent 关联与 lineage tracking

### 任务 1-11：统一 Trace 写入接口
要求：
- 所有执行通过统一 trace writer 写入
- 支持 run started / step started / tool called / retrieval called / artifact created / run finished 等事件

---

## 6.5 清理任务

### 任务 1-12：标记旧 AppCenter 为弃用
- 将原 appcenter 明确标记为 legacy / migration only
- 新代码不允许再依赖 appcenter 作为中心域

### 任务 1-13：清理模块自带执行器
梳理并逐步下线：
- chat 自治 executor
- workflow 自治 executor
- bot 自治 executor
- plugin 自治执行路径
- appcenter runtime router

---

## 6.6 Phase 1 验收标准
- App 概念从主模型退出
- Agent 成为唯一主对象
- Run/Task/Trace/Artifact 统一落地
- Runtime Core 成为唯一执行内核
- 无新增平行 executor

---

# 7. Phase 2：Agent 模块中心化重构

## 7.1 目标
把 Agent 从“平台模块之一”升级为“平台唯一中心”。

## 7.2 任务清单

### 任务 2-1：重构 Agent 聚合根
统一 Agent 聚合模型：
- profile
- instructions
- default model
- execution policy
- runtime config
- visibility / publish state

### 任务 2-2：建立 AgentBinding 模型
支持绑定：
- models
- workflows
- skills
- knowledge
- tools
- policies
- plugins exported capabilities
- mcp provided capabilities

### 任务 2-3：AgentVersion 落地
要求：
- Agent 版本必须显式化
- 绑定资源应可随版本变化
- 支持 draft / published / deprecated

### 任务 2-4：AgentPublish 流程重构
要求：
- 发布流程围绕 Agent 执行
- 不能再走旧 App 发布逻辑
- 可支持 workspace/tenant 级发布与回滚

### 任务 2-5：统一 Agent Chat 模式
要求：
- Chat 本质上是 Agent + Thread + Run
- 对话触发执行统一走 Runtime Core

### 任务 2-6：统一 Agent Task 模式
要求：
- Agent 可接收 structured input / batch input / file input
- Agent 后台执行走 Task + Run 模型
- 结果统一沉淀为 Artifact

### 任务 2-7：Agent 策略模型
支持：
- max iterations
- budget
- allowed tools
- allowed skills
- knowledge scope
- approval requirements
- timeout profile

### 任务 2-8：Agent Memory 接口重构
要求：
- memory 只能作为 Agent 的能力插件或 capability
- 不允许 Memory 单独膨胀成主对象中心
- 提供 memory read/write hook

### 任务 2-9：Bot 迁移策略
将 Bot 迁移为：
- Agent Template
- LegacyBot compatibility layer

要求：
- 不再继续扩展 Bot 独立主模型
- 旧 Bot 能映射到 Agent 构造流程

---

## 7.3 Phase 2 验收标准
- Agent 成为唯一中心聚合根
- Chat / Task 都归属于 Agent
- Bot 被降级为模板或兼容层
- 所有 Agent 资源通过 AgentBinding 表达

---

# 8. Phase 3：能力层与接入层重构

# 8.1 Workflow 重构

## 目标
将 Workflow 重新定义为 Agent 的编排设计器与 Skill 的实现能力。

### 任务 3-1：Workflow 模型标准化
统一：
- workflow
- workflow_version
- workflow_nodes
- workflow_edges
- workflow_publish

### 任务 3-2：Workflow 运行结果接入 Run 体系
要求：
- Workflow 执行必须统一写入 Run / RunStep / Artifact / Trace
- 不允许 workflow 自治结果体系

### 任务 3-3：Workflow 节点能力重构
标准节点类型：
- llm
- tool
- retrieval
- skill
- approval
- agent
- condition
- transform

### 任务 3-4：Workflow 发布目标收敛
Workflow 仅支持以下发布目标：
- Agent internal orchestration
- Skill implementation
- Task template

### 任务 3-5：Workflow 与 Agent 绑定
Agent 可绑定多个 Workflow，但 Workflow 只能作为 Agent 能力层，不可抢占主中心

---

# 8.2 Skill 重构

## 目标
正式引入 Skill 作为中层能力单元。

### 任务 3-6：新增 Skill 核心模型
新增：
- `skills`
- `skill_versions`
- `skill_bindings`

### 任务 3-7：Skill 封装内容定义
Skill 可包含：
- instructions
- workflows
- tools
- knowledge scopes
- output schemas
- policy constraints
- approval rules

### 任务 3-8：Skill 与 Agent 打通
要求：
- Agent 可挂多个 Skill
- Skill 可参与 Runtime 执行
- Skill 结果统一落 Run

### 任务 3-9：Skill 与 Workflow 打通
要求：
- Workflow 节点支持调用 Skill
- Skill 可由 Workflow 实现

### 任务 3-10：Skill 与 Plugin 打通
要求：
- Plugin 可导出 Skill
- Skill 来源应可标记为 local/plugin/mcp-derived

---

# 8.3 Knowledge 重构

## 目标
从 Dataset 正式迁移到 Knowledge 语义与结构。

### 任务 3-11：数据模型升级
新增或迁移：
- `knowledge_bases`
- `knowledge_documents`
- `knowledge_chunks`
- `knowledge_indexes`
- `retrieval_profiles`
- `ingestion_runs`

### 任务 3-12：Dataset 到 Knowledge 迁移
要求：
- 保留短期映射兼容层
- 新 API / 新前端统一使用 Knowledge 表达
- 禁止新增 dataset 产品语义

### 任务 3-13：拆分 Knowledge 内部三层
- ingestion pipeline
- knowledge store
- retrieval service

### 任务 3-14：Knowledge 与 Agent 绑定
要求：
- Agent 可绑定多个 Knowledge Base
- Runtime 检索必须通过标准 retrieval service

### 任务 3-15：Knowledge 与 Workflow / Skill 打通
要求：
- Workflow 节点可调用 retrieval
- Skill 可限定 knowledge scope

---

# 8.4 Plugin 重构

## 目标
保留 Plugin 模块名，但重新定位为平台扩展安装层。

### 任务 3-16：Plugin 核心模型标准化
统一：
- `plugins`
- `plugin_versions`
- `plugin_installs`
- `plugin_permissions`
- `plugin_exports`

### 任务 3-17：Plugin 生命周期管理
支持：
- install
- uninstall
- enable
- disable
- configure
- upgrade

### 任务 3-18：Plugin 导出能力模型
Plugin 可导出：
- tools
- skills
- connectors
- resources
- templates

### 任务 3-19：Plugin Registry 重构
要求：
- Plugin 导出能力必须进入统一 registry
- Runtime 不直接面向 Plugin 执行
- Runtime 只面向 Tool / Skill / Knowledge / Connector

---

# 8.5 MCP 重构

## 目标
将 MCP 明确放到标准接入层，不单独膨胀为业务中心。

### 任务 3-20：建立 MCP 集成域
新增目录：
- `modules/integrations/mcp`

### 任务 3-21：建立 MCP 核心模型
新增：
- `mcp_connectors`
- `mcp_servers`
- `mcp_connector_auth`
- `mcp_capability_syncs`
- `mcp_tool_mappings`
- `mcp_resource_mappings`
- `mcp_prompt_mappings`

### 任务 3-22：建立 MCP Client / Sync Service
要求：
- 连接 MCP Server
- 获取 tools/resources/prompts
- 同步到本地 registry
- 做健康检查与权限校验

### 任务 3-23：MCP Tool 映射
要求：
- MCP Tool 统一映射为 SOIT Tool
- Runtime 通过 Tool Registry 调用，不直接调用 MCP 原始对象

### 任务 3-24：MCP Resource 映射
要求：
- MCP Resource 映射为 Knowledge/Context Resource
- 可被 Agent / Skill / Workflow 使用

### 任务 3-25：MCP Prompt 映射
要求：
- MCP Prompt 不直接暴露为独立业务主对象
- 作为 Skill/Template 的构建来源之一

### 任务 3-26：MCP 与 Plugin 打通
要求：
- MCP Connector 可作为 Plugin 导出的连接器类型
- Plugin 可负责管理 MCP connector 的安装与配置

---

## 8.6 Phase 3 验收标准
- Workflow 被降级为高级设计器
- Skill 成为正式中层能力对象
- Dataset 完成向 Knowledge 的语义迁移
- Plugin 完成安装层重定位
- MCP 完成集成层落位
- Tool / Skill / Plugin / MCP 边界清晰

---

# 9. Phase 4：前端 Agent 中心化迁移

## 9.1 目标
将前端从旧模块式平台迁移到 Agent 中心平台。

## 9.2 信息架构任务

### 任务 4-1：重构一级导航
统一导航为：
- Agents
- Chat
- Workflows
- Knowledge
- Plugin
- Models
- Tasks
- Observability
- Settings

### 任务 4-2：下线或弱化旧入口
逐步弱化：
- Bot 独立中心
- Dataset 独立产品语义
- App 相关入口与文案

---

## 9.3 Agent 前台任务

### 任务 4-3：重构 Agent 列表页
展示：
- 名称
- 状态
- 发布信息
- 绑定能力摘要
- 最近任务状态

### 任务 4-4：重构 Agent 详情页
建议页签：
- 对话
- 任务
- 知识
- 技能
- 编排
- 工具
- 运行记录
- 配置

### 任务 4-5：Agent 创建/编辑流程
要求：
- 创建 Agent 时可绑定 model/workflow/skill/knowledge/tool
- 支持版本与发布操作

---

## 9.4 Chat 前台任务

### 任务 4-6：Chat 归属 Agent
要求：
- Chat 页面必须绑定 Agent
- Thread 必须从属于 Agent
- Chat 中发起的所有执行都落入 Agent 的 Run/Task

### 任务 4-7：Chat 中展示执行细节
支持展示：
- tool 调用
- retrieval 结果
- artifact 产出
- task 提交状态

---

## 9.5 Workflow 前台任务

### 任务 4-8：保留 Workflow 设计器入口
要求：
- Workflow 继续存在独立入口
- 定位为高级设计器

### 任务 4-9：Workflow 与 Agent 打通
要求：
- 从 Agent 页签可进入 Workflow 设计
- Workflow 可发布到 Agent/Skill/Task Template

---

## 9.6 Knowledge 前台任务

### 任务 4-10：Dataset 前台全面迁移为 Knowledge
要求：
- 页面命名统一改为 Knowledge
- 文档、索引、检索配置围绕 Knowledge 展示

---

## 9.7 Plugin 与 MCP 前台任务

### 任务 4-11：Plugin 页面重构
展示：
- 已安装插件
- 可升级版本
- 导出能力
- 权限声明
- 配置入口

### 任务 4-12：MCP 管理入口
放在：
- Plugin 下的 `MCP Connectors`
或
- Integrations 子域（如后续新增）

页面支持：
- 新建 connector
- 配置 auth
- 测试连接
- 同步能力
- 查看导入的 tools/resources/prompts

---

## 9.8 Tasks / Observability 前台任务

### 任务 4-13：Tasks 页面重构
展示：
- 后台任务列表
- 状态
- 关联 Agent
- 关联 Run
- 进度
- 重试/取消/继续

### 任务 4-14：Observability 页面建设
展示：
- run list
- run detail
- step timeline
- artifact preview
- tool/retrieval/skill/workflow trace
- latency / cost / success rate
- feedback

---

## 9.9 Phase 4 验收标准
- Agent 成为前台唯一中心
- Chat 归属 Agent
- Workflow 成为高级设计器
- Dataset 文案全面迁移为 Knowledge
- Plugin 成为安装中心
- MCP 不作为一级业务主导航

---

# 10. Phase 5：Observability / Policy / Governance 完善

## 10.1 目标
完成平台长期稳定运行所需的治理与可观测能力。

## 10.2 任务清单

### 任务 5-1：Trace 查询与回放
- Run replay
- step inspect
- error root cause inspect

### 任务 5-2：Policy Hook 统一
支持：
- tool allow/deny
- skill allow/deny
- knowledge scope control
- timeout/budget limits
- approval interception

### 任务 5-3：Approval 体系统一
要求：
- approval 节点统一接入 runtime
- Agent / Workflow / Skill / Task 共享审批模型

### 任务 5-4：反馈与评测回流
支持：
- 用户反馈
- 管理员标注
- eval dataset 回流（后续可扩）

### 任务 5-5：成本与配额治理
支持：
- per run cost
- per agent cost
- per tenant budget
- model budget constraints

---

## 10.3 Phase 5 验收标准
- 平台具备生产级运行追踪能力
- 平台具备审批、策略、预算控制能力
- 平台具备长期治理基础

---

# 11. Phase 6：兼容层清理与最终收口

## 11.1 目标
删除过渡层，完成真正的结构收敛。

## 11.2 任务清单

### 任务 6-1：删除 App 兼容层
- 删除旧 appcenter 主路径
- 删除旧 app 模型依赖
- 删除 app 相关前台概念

### 任务 6-2：删除 Dataset 旧产品语义
- 清理 dataset 页面与文案
- 清理 dataset 旧 API 暴露

### 任务 6-3：删除 Bot 独立中心逻辑
- 仅保留模板或迁移兼容逻辑
- 清理独立 Bot 运行路径

### 任务 6-4：删除旧 executor / 旧 runtime router
- 清理 legacy executor
- 清理临时兼容入口
- 清理双写逻辑

### 任务 6-5：清理无效绑定模型
- 删除旧 app binding
- 删除重复关系表
- 收敛到 AgentBinding / registry / capability mapping

---

## 11.3 Phase 6 验收标准
- 旧主概念彻底退出
- 旧双轨运行彻底结束
- 新蓝图成为唯一真实结构

---

# 12. 模块迁移映射表

## 12.1 概念迁移
- App → Agent
- AppVersion → AgentVersion
- AppBinding → AgentBinding
- AppPublish → AgentPublish
- Dataset → Knowledge
- Bot → Agent Template / LegacyBot
- PluginMarket → Plugin
- AppCenter Runtime → Runtime Core
- MCP External Connector → MCP Connector under Integration Layer

## 12.2 页面迁移
- Chat 页面 → Agent Chat 视图
- Bot 页面 → Agent Template / Legacy 页
- Dataset 页面 → Knowledge 页面
- Workflow 页面 → 保留但重定位
- Plugin 页面 → 扩展安装中心
- Run 页面 → Tasks / Observability 体系

## 12.3 执行路径迁移
- Chat Executor → Runtime Core + Agent Chat Mode
- Workflow Executor → Runtime Core + Workflow Capability Executor
- Agent Executor → Runtime Core + Agent Pipeline
- Plugin Runtime Hook → Plugin Export + Capability Registry
- MCP Raw Call → Tool/Resource/Prompt Mapping + Registry

---

# 13. 推荐的 Codex 执行顺序

1. Phase 0：准备与冻结蓝图  
2. Phase 1：数据模型 + Runtime Core  
3. Phase 2：Agent 中心化  
4. Phase 3：Workflow / Skill / Knowledge / Plugin / MCP  
5. Phase 4：前端迁移  
6. Phase 5：Observability / Policy / Governance  
7. Phase 6：清理兼容层

---

# 14. 验收总标准

当本次大规模重构完成后，应满足：

- App 概念退出前后端主架构
- Agent 成为唯一中心对象
- Runtime Core 成为唯一执行内核
- Chat 与 Task 统一归属于 Agent
- Workflow 成为高级设计器
- Skill 成为正式能力层
- Dataset 正式迁移为 Knowledge
- Plugin 成为扩展安装层
- MCP 成为标准接入层
- 所有执行统一落入 Run / Trace / Artifact / Task
- 平台具备长期可演进、可治理、可观测能力

---

# 15. 最终结论

本次重构不是“模块优化”，而是一次 **平台中心模型重建**。

SOIT 必须从旧形态：

- chat / bot / dataset / workflow / agent 并列平台
- app / appcenter 作为抽象中心
- 多套 executor 并存
- plugin / skill / tool / mcp 边界模糊

重建为新形态：

- **Agent 为唯一中心**
- **Runtime Core 为统一执行内核**
- **Workflow / Skill / Knowledge 为能力层**
- **Plugin 为扩展安装层**
- **MCP 为标准接入层**
- **Run / Task / Trace / Artifact 为运行与治理底座**

这套结构才适合 SOIT 作为一个长期可持续演进的企业级 AI 平台继续发展。
