# SOIT Responses API 架构要求与规划

> Blueprint note
> 本文档描述的是 Responses API 方向的目标规划。
> 若与当前仓库实现存在差异，请以 `README.md`、`app/docs/architecture/*`、`web/docs/*` 为当前事实来源。

## 1. 文档目标

本文档用于明确 SOIT 后续 Responses API 的整体设计要求、架构边界、统一运行时模型以及阶段性建设规划，作为后续 Codex 与研发团队进行架构重构、接口统一、数据流整合与模块改造的基线蓝图。

目标不是简单兼容某一家模型厂商的接口，而是为 SOIT 建立一套面向多模型、多工具、多 Agent、多工作流、多租户场景的统一响应资源层与语义流层。

SOIT 后续需要遵循的核心原则是：

**一切 AI 执行统一收敛为 Run / RunStep；Responses 只作为北向资源与语义事件投影。**

也即：

- Chat 触发的是一次 Run，Responses 负责对外暴露资源与语义流
- Agent 是具备默认策略、工具、记忆与上下文装配能力的 Run 配置集合
- Workflow 中的模型节点，本质上也是 Run 内的受控执行片段
- Tool、MCP、RAG、Memory、Approval、Artifact 等能力，都通过统一运行时事件流接入，再按需投影到 Responses

---

## 2. 总体设计结论

### 2.1 对外采用 Responses API 风格

SOIT 对外接口建议采用 Responses API 风格，而不是继续以传统 chat/completions 结构为中心。

原因如下：

- 更适合承载工具调用与多阶段执行过程
- 更适合表达多模态输入与结构化输出
- 更适合统一 Chat、Agent、Workflow 的调用方式
- 更适合前端基于语义事件流进行渲染
- 更适合作为后续 MCP、Memory、Approval 等能力的上层协议

### 2.2 对内不能直接绑定某厂商协议

虽然对外采用 Responses 风格，但 SOIT 内部不应直接将 OpenAI 或其他厂商的 response 对象作为内部真相源。

SOIT 内部必须维护自己的 Canonical Runtime Model，用于承载：

- 会话状态
- 运行实例
- 工具执行
- 事件追踪
- 产物生成
- Token 与成本统计
- 审批与治理链路
- 回放与审计

### 2.3 最优方案

SOIT 推荐采用三层结构：

- Northbound：SOIT 原生 Responses API
- Core Runtime：SOIT 统一运行时模型与执行编排层
- Southbound：Provider Adapter 适配层

即：

**对外 Responses 风格，对内 Canonical Runtime，对下 Provider Adapters。**

---

## 3. 总体架构要求

### 3.1 架构目标

SOIT Responses API 的核心目标包括：

1. 统一前端调用协议
2. 统一 Chat / Agent / Workflow / Tool / MCP 数据流
3. 统一多模型调用抽象
4. 统一对外语义事件记录与回放能力
5. 统一工具与外部能力接入方式
6. 支撑多租户、可审计、可治理、可扩展的平台能力

### 3.2 总体分层

建议采用如下分层：

```text
Clients / Frontend / SDK
        |
        v
SOIT Responses API Layer
        |
        v
Response Resource / Semantic Projection Layer
        |
        v
Runtime Core / Run / RunStep
        |
        +--> Conversation Manager
        +--> Context Builder
        +--> Policy / Guard / Approval
        +--> Tool Router
        +--> MCP Gateway
        +--> Memory Manager
        +--> Knowledge Retriever
        +--> Artifact Manager
        +--> Usage / Cost Tracker
        +--> Trace Recorder
        |
        v
Provider Adapters
  - OpenAI
  - Anthropic
  - Gemini
  - Qwen / DashScope
  - Ollama / vLLM
  - OpenRouter
```

### 3.3 关键原则

#### 原则一：聊天与北向协议统一

SOIT 不再保留互相割裂的：

- chat 接口体系
- agent run 接口体系
- workflow llm node 接口体系

统一为一套北向资源抽象：

- Response
- ResponseEvent
- Run Reference

#### 原则二：模型只负责推理，平台负责执行

模型只负责：

- 理解上下文
- 生成文本或结构化输出
- 发起工具调用意图
- 决定下一步动作建议

平台负责：

- 工具注册与路由
- 权限校验
- MCP 接入
- 超时与重试
- 审批与策略
- 成本追踪
- 日志与事件持久化
- 回放与审计

#### 原则三：一切过程事件化

SOIT 必须将每次执行过程记录为事件流，而不仅仅是保留最终输出文本。

事件化是后续以下能力的基础：

- Trace Viewer
- Debug Console
- Replay
- Cost Attribution
- Tool Audit
- HITL 审批
- SLA 与运维分析

---

## 4. 核心对象模型要求

SOIT Responses API 后续必须统一以下核心对象。

### 4.1 Conversation

表示长期会话容器。

职责：

- 保存多轮上下文
- 关联 tenant / project / agent
- 为多个 response 提供父级会话容器
- 支撑多端恢复与状态压缩

建议字段：

- id
- tenant_id
- project_id
- agent_id
- title
- mode
- status
- metadata
- created_at
- updated_at

### 4.2 Response

表示对外部 API 暴露的一次响应资源投影。

职责：

- 承载一次请求的北向输入与输出投影
- 关联 run
- 关联 conversation
- 关联 model/provider
- 提供前端和 SDK 的统一资源对象

建议字段：

- id
- conversation_id
- run_id
- model
- provider
- status
- input
- output
- usage
- metadata
- created_at

### 4.3 Run

表示 SOIT 内部真实执行实例。

职责：

- 记录一次完整运行的状态机
- 支撑 workflow 子运行与嵌套执行
- 提供运行时生命周期管理
- 作为执行真相源

建议字段：

- id
- type
- parent_run_id
- root_run_id
- response_id
- conversation_id
- workflow_run_id
- status
- started_at
- ended_at

### 4.4 Event

SOIT 对外语义流与回放对象。

职责：

- 记录对外暴露所需的关键语义事件
- 支撑前端流式展示
- 支撑 API 回放
- 支撑把 run 级事实投影到统一协议

建议字段：

- id
- run_id
- response_id
- conversation_id
- sequence
- type
- source
- payload
- created_at

### 4.5 ToolCall

表示一次工具调用的北向投影。

职责：

- 提供统一工具调用读取模型
- 从 RunStep 投影输入输出与错误
- 支撑前端展示和 API 回放
- 不替代 RunStep 审计真相

### 4.6 Artifact

表示执行过程中产生的文件、文本、JSON、图片或其他中间产物。

### 4.7 Usage / Cost

表示 token、模型成本、工具成本等统计信息。

要求支持：

- response 级
- tool call 级
- run 级
- workflow 节点级
- tenant/project 级归因

---

## 5. 统一事件模型要求

SOIT 内部事件模型建议至少覆盖以下类别。

### 5.1 输入类事件

- response.created
- response.input.added
- conversation.item.added
- context.compacted
- context.memory.attached
- context.dataset.attached

### 5.2 模型输出类事件

- response.output_text.delta
- response.output_text.completed
- response.output_json.delta
- response.output_json.completed
- response.reasoning.summary
- response.refusal
- response.completed
- response.failed

### 5.3 工具类事件

- tool.call.requested
- tool.call.approved
- tool.call.started
- tool.call.delta
- tool.call.completed
- tool.call.failed
- tool.result.appended

### 5.4 MCP 类事件

- mcp.server.attached
- mcp.tools.imported
- mcp.call.requested
- mcp.call.started
- mcp.call.completed
- mcp.call.failed

### 5.5 平台治理类事件

- approval.requested
- approval.approved
- approval.rejected
- guard.blocked
- policy.rewritten
- rate_limit.hit
- retry.scheduled
- fallback.triggered

### 5.6 资源类事件

- artifact.created
- artifact.updated
- usage.reported
- cost.reported
- memory.write.requested
- memory.write.completed

---

## 6. SOIT Responses API 要求

### 6.1 主资源接口

建议统一保留以下资源：

- `POST /v1/responses`
- `GET /v1/responses/{response_id}`
- `GET /v1/responses/{response_id}/events`
- `POST /v1/responses/{response_id}/cancel`
- `POST /v1/conversations`
- `GET /v1/conversations/{conversation_id}`
- `GET /v1/conversations/{conversation_id}/items`
- `POST /v1/conversations/{conversation_id}/items`
- `GET /v1/runs/{run_id}`
- `GET /v1/runs/{run_id}/events`
- `GET /v1/tools`
- `GET /v1/mcp/servers`

### 6.2 创建 Response 的请求要求

请求对象需支持以下能力：

- model
- conversation_id
- agent_id
- input
- instructions
- tools
- mcp_servers
- response_format
- context
- store
- stream
- metadata

### 6.3 Content Part 模型要求

输入内容不能只支持纯文本，需要支持多类型输入片段：

- input_text
- input_image
- input_file
- input_audio
- input_json
- tool_result_reference
- artifact_reference

### 6.4 Output Item 模型要求

输出不能只是一段文本，需支持统一 item 模型：

- message
- tool_call
- tool_result
- artifact
- reasoning_summary
- refusal
- approval_request
- handoff

---

## 7. 流式协议要求

建议第一阶段统一使用 SSE。

### 7.1 前端只消费 SOIT 语义事件

前端不可直接消费 Provider 原始 delta 数据。必须统一消费 SOIT 自己的流式事件协议。

原因：

- 便于前端与模型厂商解耦
- 便于兼容不同 provider
- 便于统一渲染 tool call / approval / artifact
- 便于加入平台级事件

### 7.2 最低支持事件

SSE 至少支持：

- response.created
- response.output_text.delta
- tool.call.requested
- tool.call.completed
- response.output_text.completed
- response.completed
- response.failed

---

## 8. Tool 与 MCP 架构要求

### 8.1 ToolSpec 必须平台内统一定义

SOIT 内部必须定义自己的 ToolSpec，而不是直接绑定某一家函数调用 schema。

ToolSpec 需至少包括：

- name
- title
- description
- input_schema
- output_schema
- auth
- policy
- source

### 8.2 工具分类

建议统一分类：

- builtin
- custom
- connector
- mcp

### 8.3 Tool Router 职责

Tool Router 必须承担：

- 参数校验
- 权限校验
- 风险与审批判断
- 工具执行
- 输出标准化
- 错误归一化
- 事件记录
- 成本统计

### 8.4 MCP 的位置要求

MCP 不应作为独立平行体系漂浮在工具系统之外。

建议定义为 Tool Source 的一种：

- Builtin Tools
- Custom Tools
- Connector Tools
- MCP Imported Tools

这样做的好处：

- 权限体系统一
- 审批体系统一
- trace 统一
- 前端展示统一
- 运行时路由统一

---

## 9. Memory 与 Knowledge 架构要求

### 9.1 Memory 不直接混入会话文本

Memory 建议作为独立上下文来源，由 Context Builder 在响应发起前进行注入。

建议分层：

- short_term_memory
- long_term_memory
- working_memory

### 9.2 Knowledge / RAG 作为上下文来源

检索结果不应简单拼成 message 文本后失去来源信息。

应以结构化上下文附件方式注入，并在事件流中记录：

- dataset.search.requested
- dataset.search.completed
- context.dataset.attached

---

## 10. Approval / HITL 架构要求

SOIT 后续面向企业级场景时，审批能力必须纳入统一运行时。

适用场景包括：

- 发邮件
- 修改 CRM
- 创建工单
- 调用写操作 API
- 调用高风险 MCP 工具
- 调用付费工具

审批事件需支持：

- approval.requested
- approval.approved
- approval.rejected
- approval.timed_out

---

## 11. Provider Adapter 架构要求

### 11.1 Provider 必须全部走适配层

SOIT 不允许业务模块直接调用具体 provider SDK。

所有模型调用必须通过统一 Provider Adapter。

### 11.2 统一抽象能力

适配层至少应统一：

- createResponse
- streamResponse
- cancel

### 11.3 统一输出事件

各 provider 的输出最终需被转成统一的 CanonicalModelEvent，再映射为 SOIT Runtime Event。

---

## 12. 会话状态要求

SOIT 必须自己保存：

- conversation
- conversation items
- context summary
- memory link
- run trace

Provider 侧会话状态只能作为优化能力，不能作为平台唯一真相源。

原因：

- 多模型迁移需要
- 数据主权需要
- 合规与审计需要
- replay 需要
- provider 替换需要

---

## 13. 存储层要求

建议至少建立以下主表：

- conversations
- conversation_items
- responses
- runs
- response_events
- run_steps
- artifacts
- approvals
- usage_records
- cost_records
- memory_records
- dataset_retrieval_logs

### 13.1 conversation_items 与 response_events 分离

二者不能合表。

建议职责：

- conversation_items：面向会话语义内容
- response_events：面向对外语义事件回放
- runs / run_steps：面向执行过程真相

这样更利于：

- UI 渲染
- 历史回看
- Debug Trace
- 成本与性能分析

---

## 14. 前端要求

### 14.1 Chat UI

前端对话页统一基于 `/v1/responses` 工作。

### 14.2 Debug / Trace UI

需支持查看：

- run timeline
- tool execution
- provider request/response summary
- token/cost
- memory attach/write
- retrieval hits
- artifact 列表

### 14.3 Workflow Node

Workflow 中所有 LLM 节点统一调用 Run 体系，并通过 Responses 暴露统一语义，而不是直连 provider。

---

## 15. 阶段规划

## P0：统一主链路闭环

目标：先跑通最小可用链路。

包括：

1. 建立 `/v1/responses` 主入口
2. 建立 `responses / response_events / runs / run_steps` 核心数据表
3. 建立 SSE 流式语义事件协议
4. 建立 OpenAI Provider Adapter
5. 建立 Tool Router 第一版
6. 改造 Chat 页面统一走 Responses API

## P1：扩展平台级能力

包括：

1. MCP Gateway
2. structured output / response_format
3. dataset retrieval events
4. memory attach / memory write
5. artifact manager
6. approval flow
7. trace viewer
8. provider fallback

## P2：高级编排能力

包括：

1. 多 response 并行编排
2. planning / sub-run
3. replay / deterministic replay
4. background run
5. cross-agent handoff
6. prompt caching
7. 深度成本归因与 SLA 分析

---

## 16. 推荐工程边界

建议目录按以下边界拆分：

```text
kernel/
  responses/
    api/
    application/
    domain/
    infra/
  conversations/
  runs/
  response_events/
  tools/
  mcp/
  memory/
  retrieval/
  approvals/
  artifacts/
  usage/
  providers/
    openai/
    anthropic/
    gemini/
    qwen/
```

---

## 17. 最终架构原则

SOIT 后续 Responses API 与运行时内核建议统一坚持以下原则：

**SOIT 统一以 Run / RunStep 为执行真相源，以 Responses 为北向资源与语义流投影层，以 Tool/MCP 为能力扩展层，以 Provider Adapter 为模型解耦层。**

---

## 18. 执行建议

落地时建议按以下顺序推进：

1. 先建立 `/v1/responses` 主入口
2. 将旧 chat 响应模型抽象为 Response + Run + Event
3. 前端改为统一消费 SSE 语义事件
4. Agent 改造为默认配置集合，而不是独立执行协议
5. Workflow 节点改造为内部调用统一 Run 体系，并对外暴露 Responses 语义
6. 再逐步接入 MCP、Memory、Knowledge、Approval

这样可以在控制重构风险的同时，逐步形成稳定的新运行时内核。
