# SOIT Codex 可直接执行的大重构任务书

> Archive note
> 本文档是重构执行期任务书，保留用于追溯任务来源，不作为当前架构说明文档。

> 文件名为英文，内容为中文。
> 
> 本文档用于让 Codex 按阶段、按目录、按任务单元直接执行 SOIT 平台的大规模重构。
> 
> 本任务书已经将以下两类重构合并为一套统一实施方案：
> - Agent 中心化架构重构
> - 现有响应体系重构为统一 Responses API / Runtime Core

---

# 1. 重构目标

本次重构的目标不是局部修补，而是把 SOIT 从“多入口、多模型、多执行路径”的平台，重构为“Agent 中心、统一运行时、统一响应协议、统一能力挂载”的平台。

最终目标如下：

1. 去 App 化，统一为 Agent 主对象
2. 建立统一 Runtime Core
3. 建立统一 `/v1/responses` 主入口
4. 建立统一 Run / Step / Event / Artifact / Cost / Trace 模型
5. 建立 Tool / Skill / Workflow / Knowledge / Plugin / MCP 的清晰边界
6. 让 Chat / Agent / Workflow 共用同一执行内核
7. 清理旧接口、旧表、旧服务、旧前端路由

---

# 2. Codex 执行总原则

## 2.1 必须遵守的原则

1. 后端先于前端
2. 内核先于业务模块
3. 数据模型先于接口
4. 接口先于页面迁移
5. 兼容层必须有删除计划
6. 不允许新增任何旧概念的扩张实现

## 2.2 明确禁止事项

Codex 在重构过程中，不允许新增以下内容：

- 新的 `App`、`AppVersion`、`AppBinding`、`AppPublish` 概念
- 新的独立 chat runtime
- 新的独立 workflow llm executor
- 新的独立 tool 执行闭环
- 让 MCP 成为独立业务中心模块
- 让 Dataset 继续作为最终产品主概念膨胀
- 前端直接依赖 provider 原始返回结构
- 各模块私自新增 result/log/output 表绕过 Run/Event 体系

## 2.3 推荐执行方式

Codex 每次提交以“一个可验证的任务单元”为边界：

- 优先提交小而闭环的结构性改动
- 每个任务单元都要可编译、可迁移、可回滚
- 每个阶段完成后输出一次阶段总结

---

# 3. 目标架构落位

## 3.1 后端目标目录

以下为建议的目标目录结构，Codex 在重构中应尽量向该结构收敛：

```text
backend/
  app/
    api/
      v1/
        responses/
        agents/
        workflows/
        knowledge/
        plugins/
        models/
        observability/
    kernel/
      runtime/
      responses/
      trace/
      events/
      policy/
      security/
      context/
      artifacts/
    modules/
      agent/
      workflow/
      skill/
      knowledge/
      tool/
      plugin/
      integrations/
        mcp/
      modelhub/
      observability/
      identity/
    infrastructure/
      db/
      queue/
      cache/
      storage/
      provider/
    domain/
      shared/
```

## 3.2 前端目标目录

```text
web/
  src/
    pages/
      agents/
      chat/
      workflows/
      knowledge/
      plugins/
      models/
      observability/
      settings/
    modules/
      responses/
      agents/
      workflows/
      knowledge/
      plugins/
      models/
      runs/
    components/
    services/
      api/
      sse/
    stores/
    types/
```

## 3.3 统一核心对象

必须收敛到以下对象：

- Agent
- AgentVersion
- AgentBinding
- AgentPublish
- Thread
- ThreadMessage
- Response
- Run
- RunStep
- Event
- ToolCall
- Artifact
- Approval
- UsageRecord
- CostRecord
- Workflow
- Skill
- KnowledgeBase
- Plugin
- MCPConnector

---

# 4. 旧对象到新对象映射

| 旧概念 | 新概念 | 处理策略 |
|---|---|---|
| App | Agent | 主概念替换 |
| AppVersion | AgentVersion | 主概念替换 |
| AppBinding | AgentBinding | 主概念替换 |
| AppPublish | AgentPublish | 主概念替换 |
| Chat Session / Chat Message | Thread / ThreadMessage / Response | 逐步映射迁移 |
| Bot | Agent Template 或 LegacyAgentAdapter | 临时兼容，最终删除 |
| Dataset | KnowledgeBase | 产品语义收敛 |
| Workflow 内部 LLM 调用 | Internal Run + Response Projection | 执行方式替换 |
| 独立 Tool Executor | Tool Router | 统一路由 |
| Provider 原始输出 | Response Event / Output | 协议隔离 |

---

# 5. 分阶段执行计划总览

| Phase | 名称 | 目标 |
|---|---|---|
| Phase 0 | 重构准备与边界冻结 | 固化规则，建立映射和禁令 |
| Phase 1 | 核心数据模型与 Runtime Core | 统一 Agent / Run / Event / Artifact |
| Phase 2 | Responses API 与 Orchestrator | 建立统一响应主入口 |
| Phase 3 | Agent 中心化模块重构 | 让 Agent 成为唯一主对象 |
| Phase 4 | Workflow / Skill / Knowledge / Plugin / MCP 重构 | 清理能力边界与接入层 |
| Phase 5 | 旧接口兼容适配 | 旧入口转接到新内核 |
| Phase 6 | 前端迁移 | 前端改为消费新协议 |
| Phase 7 | Observability / Governance 完善 | 补齐 trace、cost、audit、policy |
| Phase 8 | 删除兼容层与旧结构 | 最终收口 |

---

# 6. Phase 0：重构准备与边界冻结

## 6.1 目标

在任何代码改造前，先冻结重构规则，避免 Codex 后续边做边偏移。

## 6.2 任务清单

### Task 0-1：建立架构约束文档

Codex 需要在仓库内新增：

```text
/docs/architecture/soit-refactor-principles.md
/docs/architecture/soit-object-mapping.md
/docs/architecture/soit-phase-checklist.md
```

内容要求：

- 记录去 App 化原则
- 记录 Agent 中心化原则
- 记录 Responses API 为唯一未来主协议
- 记录禁止新增旧结构
- 记录阶段验收模板

### Task 0-2：建立兼容层命名规则

统一约定：

- `legacy_*`：旧逻辑兼容层
- `adapter_*`：新旧适配层
- `deprecated_*`：待删除模块

### Task 0-3：建立重构分支与提交规则

输出到文档：

- phase 分支命名规则
- commit 粒度规则
- migration 命名规则
- deprecated 注释规则

## 6.3 验收标准

- 文档落库
- 团队能基于文档继续执行
- 后续 phase 不再新增架构争议

---

# 7. Phase 1：核心数据模型与 Runtime Core

## 7.1 目标

先完成底层统一对象模型，确保后续所有模块都建立在同一内核上。

## 7.2 数据库任务

### Task 1-1：新增 Agent 主表体系

新增或迁移以下表：

- `agents`
- `agent_versions`
- `agent_bindings`
- `agent_publishes`

要求：

- Agent 成为唯一主对象
- 字段中不要再出现 `app_*` 语义
- 版本、绑定、发布全部围绕 Agent 组织

### Task 1-2：新增 Thread 体系

新增以下表：

- `threads`
- `thread_messages`
- `thread_context_snapshots`（可选）

要求：

- Thread 必须从属于 Agent
- Thread 只承载会话语义，不直接承担执行状态

### Task 1-3：新增 Response / Run / Step / Event 体系

新增以下表：

- `responses`
- `runs`
- `run_steps`
- `response_events`
- `run_steps`
- `artifacts`
- `approvals`
- `usage_records`
- `cost_records`
- `run_feedbacks`

要求：

- 所有执行必须落到 `runs`
- 所有执行步骤必须落到 `run_steps`
- 对外语义事件必须落到 `response_events`
- 文件、结构化输出、导出结果必须落到 `artifacts`

### Task 1-4：新增 Task 体系

新增以下表：

- `tasks`
- `task_checkpoints`
- `task_events`

要求：

- 长时任务统一归 Task
- Task 与 Run 关联
- 支持 checkpoint 恢复

### Task 1-5：统一状态机

为以下对象建立统一状态机枚举和转换规则：

- Response
- Run
- Task
- ToolCall
- Approval

推荐状态：

- queued
- preparing
- running
- waiting_input
- waiting_approval
- paused
- retrying
- succeeded
- failed
- cancelled

## 7.3 内核代码任务

### Task 1-6：建立 Runtime Core 目录

新增目录：

```text
backend/app/kernel/runtime/
backend/app/kernel/responses/
backend/app/kernel/events/
backend/app/kernel/trace/
backend/app/kernel/artifacts/
backend/app/kernel/context/
```

### Task 1-7：抽象统一运行时接口

至少定义：

- `RunOrchestrator`
- `ResponseOrchestrator`
- `ToolRouter`
- `ProviderAdapter`
- `EventPublisher`
- `ArtifactManager`
- `UsageRecorder`
- `CostRecorder`

### Task 1-8：建立统一领域模型

把核心对象的 DTO / Schema / Domain Model 分层整理，避免：

- API Schema 混入 ORM 模型
- Provider 返回直接暴露给前端
- 各模块重复声明相似结构

## 7.4 验收标准

- 数据迁移可执行
- 新表可被应用加载
- Runtime Core 基础接口可被单测调用
- 旧逻辑尚未切换也不影响系统编译

---

# 8. Phase 2：Responses API 与 Orchestrator

## 8.1 目标

建立统一的 `/v1/responses`，让 Chat / Agent / Workflow 后续都能共用这一主入口。

## 8.2 API 任务

### Task 2-1：新增 `/v1/responses`

至少支持：

- 创建 response
- 查询 response
- 查询 response events
- 获取 response output
- 流式订阅 response 事件
- 取消 response

建议接口：

```text
POST   /v1/responses
GET    /v1/responses/{id}
GET    /v1/responses/{id}/events
GET    /v1/responses/{id}/output
POST   /v1/responses/{id}/cancel
GET    /v1/responses/{id}/stream
```

### Task 2-2：定义统一输入模型

输入模型至少支持：

- text input
- message input
- structured input
- file/artifact reference
- agent_id / agent_version_id
- thread_id
- tool choice
- output schema
- metadata

### Task 2-3：定义统一输出模型

输出模型至少支持：

- text
- structured_output
- tool_call
- tool_result
- artifact
- approval_request
- final_summary

### Task 2-4：定义统一 SSE 事件协议

事件类型建议包括：

- `response.created`
- `response.started`
- `response.output_text.delta`
- `response.output_item.added`
- `tool.call.created`
- `tool.call.started`
- `tool.call.completed`
- `tool.call.failed`
- `artifact.created`
- `approval.requested`
- `response.completed`
- `response.failed`

## 8.3 Orchestrator 任务

### Task 2-5：实现 ResponseOrchestrator

责任：

- 接受 Response 请求
- 构建上下文
- 选择 Agent/Profile
- 调用 ProviderAdapter
- 处理 ToolRouter
- 写入 events / runs / artifacts / usage / cost

### Task 2-6：实现 ProviderAdapter 抽象

至少定义统一适配接口：

- `prepare_request()`
- `stream_events()`
- `parse_output()`
- `parse_usage()`
- `parse_tool_calls()`

### Task 2-7：实现 ToolRouter

要求：

- 统一注册工具
- 统一执行工具
- 统一权限检查
- 统一审批挂点
- 统一 trace 记录

## 8.4 验收标准

- `/v1/responses` 可创建一个最小 response run
- SSE 可以输出统一事件
- provider 返回已被适配，不直接暴露原始协议
- 工具调用可进入 ToolRouter

---

# 9. Phase 3：Agent 中心化模块重构

## 9.1 目标

让 Agent 成为平台唯一主对象，Chat/Console/Runtime 全部围绕 Agent 运行。

## 9.2 模块任务

### Task 3-1：重构 Agent 聚合根

Agent 至少包含：

- 基本信息
- 默认 instructions
- 默认 model 配置
- 默认 tools
- 默认 workflow 绑定
- 默认 knowledge 绑定
- 默认 mcp 绑定
- 默认 memory/policy 配置

### Task 3-2：重构 AgentVersion

要求：

- 可冻结配置快照
- 可用于发布
- 可用于回滚
- 与运行记录可追溯关联

### Task 3-3：重构 AgentBinding

统一 Agent 与以下对象的绑定：

- Tool
- Workflow
- Skill
- KnowledgeBase
- MCPConnector
- Model Profile

### Task 3-4：重构 AgentPublish

要求：

- 发布面向外部入口
- 区分草稿 / 已发布 / 下线状态
- 可绑定版本

### Task 3-5：移除 App 在业务层的主入口角色

策略：

- 旧 App API 先保留兼容层
- 内部服务层不再以 App 为主对象
- 新代码全部改用 Agent

## 9.3 验收标准

- 后端新增 Agent 体系可独立运行
- 新建 Agent 可以触发 response run
- 旧 App 仍可读，但不再是新代码中心

---

# 10. Phase 4：Workflow / Skill / Knowledge / Plugin / MCP 重构

## 10.1 目标

把能力层边界彻底拉清，不再混在一起。

## 10.2 Workflow 任务

### Task 4-1：把 Workflow 的 LLM 节点改为 internal response run

要求：

- Workflow 节点不再直连 provider
- 节点执行通过 `ResponseOrchestrator`
- 节点输出回写 workflow context

### Task 4-2：统一 Workflow 执行记录

Workflow 运行过程中涉及的 LLM、工具、产物，必须统一写入 Run / Event / Artifact。

## 10.3 Skill 任务

### Task 4-3：定义 Skill 边界

Skill 是“面向场景的复合能力单元”，不是安装扩展。

Skill 可包含：

- prompt 模板
- tool 组合
- workflow 调用约定
- output schema

### Task 4-4：实现 Skill 调用接入点

Skill 应作为 Agent / Workflow 的可绑定能力，而不是独立执行内核。

## 10.4 Knowledge 任务

### Task 4-5：Dataset 语义收敛为 KnowledgeBase

要求：

- 后端模型统一改为 KnowledgeBase
- 检索能力作为运行时能力挂入 Context Builder
- 前台仍可保留“知识库”产品名，但内部数据模型统一

### Task 4-6：实现 Retriever 接入位

统一通过 Context Builder 注入：

- 检索片段
- 引用信息
- chunk metadata
- rerank 结果

## 10.5 Plugin 任务

### Task 4-7：明确 Plugin 为安装与分发层

Plugin 不直接等于 Tool / Skill / Workflow。

Plugin 可承载：

- tool provider
- skill bundle
- workflow template
- mcp connector descriptor

### Task 4-8：重构插件注册机制

要求：

- 支持安装/卸载/启停
- 支持版本管理
- 支持权限声明
- 支持依赖声明

## 10.6 MCP 任务

### Task 4-9：将 MCP 放入 integrations/mcp

要求：

- MCP 是标准接入层
- 通过 ToolRouter / ContextBuilder / ResourceGateway 接入
- 不单独膨胀成产品中心模块

### Task 4-10：实现 MCP Connector 模型

至少包含：

- server config
- auth config
- capabilities
- status
- agent binding

## 10.7 验收标准

- Workflow 不再直接调用 provider
- Knowledge 检索已能通过统一上下文接入
- Plugin 与 Skill 边界清晰
- MCP 已完成标准接入位落地

---

# 11. Phase 5：旧接口兼容适配

## 11.1 目标

在不立即打断现有前端的情况下，让旧入口转接到新内核。

## 11.2 任务清单

### Task 5-1：Chat 旧接口转接 ResponseOrchestrator

要求：

- 旧 chat create/send 接口不再直接走旧 chat service
- 改为转调 `/v1/responses` 内核或直接调用 `ResponseOrchestrator`
- 旧返回结构通过 adapter 映射回前端预期格式

### Task 5-2：Agent 旧运行接口转接新内核

### Task 5-3：Workflow 内部 LLM service 转接新内核

### Task 5-4：建立 legacy adapter 层

新增目录示例：

```text
backend/app/api/v1/legacy/
backend/app/modules/legacy_adapters/
```

要求：

- 所有兼容逻辑集中，不允许散落
- 每个 adapter 都要写明最终删除目标

## 11.3 验收标准

- 旧前端不大改也能跑在新内核之上
- 新旧链路输出一致性达到可接受范围
- 兼容层位置清晰、数量可统计

---

# 12. Phase 6：前端迁移

## 12.1 目标

把前端从“按产品模块分别消费协议”迁移为“统一消费 Responses API + Agent 中心对象”。

## 12.2 路由与导航任务

### Task 6-1：前端主导航去 App 化

最终导航建议收敛为：

- Agents
- Chat
- Workflows
- Knowledge
- Plugins
- Models
- Observability
- Settings

### Task 6-2：将旧 App 页面迁移到 Agents 页面

要求：

- 列表页、详情页、发布页统一改为 Agent 语义
- 前端路由不再新增 app/*

## 12.3 数据层任务

### Task 6-3：新增 responses 模块 API client

至少包括：

- createResponse
- getResponse
- listResponseEvents
- subscribeResponseStream
- cancelResponse

### Task 6-4：建立统一事件流消费器

要求：

- Chat 页面、Agent Console、Workflow Debug 均可消费同一套 SSE 事件
- 前端不再依赖 provider chunk 格式

### Task 6-5：建立统一输出渲染层

渲染层至少支持：

- 文本增量输出
- 工具调用状态
- 结构化输出
- artifact 卡片
- approval 状态
- cost / usage 概览

## 12.4 页面迁移任务

### Task 6-6：Chat 页面迁移

### Task 6-7：Agent 调试台迁移

### Task 6-8：Workflow 调试面板迁移

## 12.5 验收标准

- 前端已有主要对话页面能消费新 SSE 协议
- 新页面不再依赖旧接口
- 新增页面全部基于 Agent 与 Response 模型建设

---

# 13. Phase 7：Observability / Governance 完善

## 13.1 目标

把运行可观测性和治理能力补齐，形成生产级平台基础设施。

## 13.2 任务清单

### Task 7-1：Trace 时间线页面与 API

至少可查看：

- response timeline
- tool timeline
- workflow node timeline
- usage/cost timeline

### Task 7-2：Audit / Approval 接口补齐

### Task 7-3：Policy Hook 接入

策略挂点至少包括：

- tool execute before
- provider request before
- artifact export before
- publish before

### Task 7-4：统一 Cost 归因

要求：

- 按 run / agent / workflow / tool / provider 统计
- 前后端都能展示

### Task 7-5：Replay / Debug 能力预留

记录必要输入、输出、事件与配置快照，便于后续回放。

## 13.3 验收标准

- 至少能按 run 查看全链路事件
- usage/cost 有统一来源
- approval / policy 不再散落在业务代码中

---

# 14. Phase 8：删除兼容层与旧结构

## 14.1 目标

完成最终收口，真正落地新架构，而不是长期双轨。

## 14.2 删除任务

### Task 8-1：删除旧 App 主逻辑

删除条件：

- Agent 页面已完成迁移
- 旧 App API 无前端依赖
- 数据迁移已完成

### Task 8-2：删除旧 chat runtime

### Task 8-3：删除 workflow 直连 provider 的节点执行逻辑

### Task 8-4：删除散落式 tool 执行器

### Task 8-5：删除 provider 原始协议直出逻辑

### Task 8-6：清理 legacy adapter

## 14.3 验收标准

- 主代码路径只剩新架构
- `legacy_*` 数量接近零
- 无新增旧概念的入口

---

# 15. 推荐执行顺序（给 Codex 的实际提交顺序）

以下顺序更适合直接执行：

## 批次 A：基础骨架

1. 新增架构文档
2. 新增核心表 migration
3. 新增 kernel 目录骨架
4. 新增 domain model / schema 骨架

## 批次 B：统一运行时

5. 实现 ResponseOrchestrator 骨架
6. 实现 ProviderAdapter 抽象
7. 实现 ToolRouter 骨架
8. 实现 EventPublisher / ArtifactManager / UsageRecorder

## 批次 C：对外主入口

9. 新增 `/v1/responses`
10. 打通最小链路：文本输入 -> provider -> event stream -> final output
11. 支持工具调用写入 event / tool_call

## 批次 D：Agent 中心化

12. 重构 agents API
13. 新增 agent version / binding / publish API
14. 让 Agent 可直接触发 response run

## 批次 E：模块接入

15. Workflow LLM 节点改 internal response run
16. Knowledge retriever 接入 Context Builder
17. Plugin / MCP 接口接入统一运行时

## 批次 F：兼容层

18. 旧 chat 接口适配到新内核
19. 旧 agent 接口适配到新内核
20. 旧 workflow service 适配到新内核

## 批次 G：前端迁移

21. 前端 responses client
22. SSE 统一消费器
23. Chat 页面迁移
24. Agent Console 迁移
25. Workflow Debug 迁移

## 批次 H：治理与清理

26. Trace / Cost / Audit 页面与 API
27. 清理 legacy 代码
28. 删除旧接口和旧服务

---

# 16. 每个任务单元的提交模板

Codex 每完成一个任务单元，建议按以下格式输出结果：

## 16.1 提交说明模板

```text
任务名称：
改动范围：
新增文件：
修改文件：
数据库变更：
是否破坏兼容：
是否包含兼容层：
验证结果：
待跟进问题：
```

## 16.2 验收检查模板

```text
[ ] 代码可编译
[ ] migration 可执行
[ ] 单测通过（如已有）
[ ] 未新增旧概念扩张
[ ] 兼容层已集中管理
[ ] 有明确下一步衔接任务
```

---

# 17. Codex 实施约束清单

Codex 在执行过程中，必须持续检查以下约束：

1. 新功能是否仍在围绕 Agent 建设，而不是回到 App
2. 新接口是否落在 `/v1/responses`，而不是再造一套 chat 协议
3. Workflow 是否已经通过 internal response run，而不是直连 provider
4. Tool 是否统一走 ToolRouter
5. Provider 原始结构是否已被隔离在 Adapter 内部
6. 事件是否统一写入 events
7. 产物是否统一写入 artifacts
8. 成本是否统一写入 usage/cost records
9. 兼容层是否被集中管理并可删除
10. 前端是否只消费平台协议，不消费厂商协议

---

# 18. 本轮重构的最终交付定义

当以下条件同时满足时，可视为本轮重构完成：

- App 不再是平台主概念
- Agent 成为唯一主对象
- `/v1/responses` 成为统一响应入口
- Chat / Agent / Workflow 共用一套运行时
- Tool / Knowledge / MCP / Plugin / Skill 边界清晰
- 前端主页面已完成新协议迁移
- trace / cost / audit / approval 具备统一底层模型
- 旧接口与旧执行器已被删除或仅剩极少数临时兼容层

---

# 19. 对 Codex 的直接执行指令

可将以下内容直接作为本任务书的执行摘要：

```text
请基于本任务书按 Phase 顺序执行 SOIT 大规模重构。
要求后端优先、内核优先、数据模型优先。
禁止新增 App 体系、禁止新增独立 chat/workflow/tool executor、禁止前端继续依赖 provider 原始协议。
所有新能力优先进入 Agent + Responses API + Runtime Core。
每完成一个任务单元，请输出改动范围、文件清单、数据库变更、兼容性影响、验证结果、下一步任务。
如遇旧结构仍被依赖，可新增集中式 legacy adapter，但必须标注删除计划。
```
