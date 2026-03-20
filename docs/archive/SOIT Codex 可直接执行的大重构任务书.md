# SOIT Codex 可直接执行的 Patch 任务清单（按仓库目录映射）

> Archive note
> 本文档是重构执行期的目录化任务清单，保留用于追溯任务拆分过程。
> 当前仓库结构与实现边界请以 `README.md`、`app/docs/architecture/*`、`web/docs/*` 为准。

> 文件名为英文，内容为中文。
>
> 本文档是对《SOIT Codex 可直接执行的大重构任务书》的进一步细化版本。
>
> 目标不是再讲一遍架构原则，而是把重构拆成 **Codex 可直接按目录、按批次、按补丁执行** 的任务清单。
>
> 由于当前未直接扫描你的完整仓库，这里采用你前面多次讨论中已经基本稳定的目录形态作为默认映射基线：
>
> - 后端：`backend/app`
> - 前端：`web/src`
> - 后端通常包含 `api`、`models`、`schemas`、`services`、`repositories`、`db`、`core` 等传统层次
> - 前端通常包含 `pages`、`components`、`services`、`stores`、`types` 等目录
>
> Codex 执行时应以“**尽量对齐真实目录，如果目录不同则按本文职责映射调整**”为原则。

---

# 1. 使用方式

本文件适合直接作为 Codex 的执行输入。建议每次只让 Codex 执行一个 Patch Batch。

建议执行口径：

1. 先做后端内核与数据模型
2. 再做接口适配
3. 再做前端页面与协议迁移
4. 最后删除兼容层

每个 Patch Batch 都要求：

- 可提交
- 可编译
- 可迁移
- 可验证
- 有明确删除范围或下一步衔接说明

---

# 2. 默认仓库目录映射

## 2.1 后端当前常见目录（假定）

```text
backend/
  app/
    api/
    core/
    db/
    models/
    schemas/
    services/
    repositories/
    tasks/
    utils/
    main.py
```

## 2.2 后端目标目录

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
      events/
      trace/
      policy/
      context/
      artifacts/
    modules/
      agent/
      workflow/
      skill/
      knowledge/
      tool/
      plugin/
      modelhub/
      observability/
      identity/
      integrations/
        mcp/
    infrastructure/
      db/
      queue/
      cache/
      storage/
      provider/
    domain/
      shared/
```

## 2.3 前端当前常见目录（假定）

```text
web/
  src/
    pages/
    components/
    services/
    stores/
    hooks/
    router/
    types/
```

## 2.4 前端目标目录

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
    services/
      api/
      sse/
    stores/
    components/
    types/
```

---

# 3. Codex 执行总规则

## 3.1 必须优先创建的新目录

如果仓库中尚不存在以下目录，Codex 第一批 patch 应先创建空目录与 `__init__.py` / `index.ts` 基础文件：

### 后端

```text
backend/app/kernel/runtime/
backend/app/kernel/responses/
backend/app/kernel/events/
backend/app/kernel/trace/
backend/app/kernel/context/
backend/app/kernel/artifacts/
backend/app/modules/agent/
backend/app/modules/workflow/
backend/app/modules/skill/
backend/app/modules/knowledge/
backend/app/modules/tool/
backend/app/modules/plugin/
backend/app/modules/integrations/mcp/
backend/app/infrastructure/provider/
backend/app/api/v1/responses/
backend/app/api/v1/agents/
backend/app/api/v1/workflows/
backend/app/api/v1/knowledge/
backend/app/api/v1/plugins/
backend/app/api/v1/observability/
```

### 前端

```text
web/src/modules/responses/
web/src/modules/agents/
web/src/modules/workflows/
web/src/modules/knowledge/
web/src/modules/plugins/
web/src/modules/models/
web/src/modules/runs/
web/src/pages/agents/
web/src/pages/chat/
web/src/pages/workflows/
web/src/pages/knowledge/
web/src/pages/plugins/
web/src/pages/models/
web/src/pages/observability/
web/src/services/api/
web/src/services/sse/
```

## 3.2 明确禁止

Codex 不允许继续新增：

- `app_service.py` 这类以旧 App 概念扩展的新实现
- 新的独立 `chat_runtime.py`
- Workflow 内部直接调用 provider 的新逻辑
- 前端页面直接解析供应商原始流事件
- 新的 `dataset product center` 概念强化实现

---

# 4. Patch Batch 清单总览

| Batch | 名称 | 范围 |
|---|---|---|
| Batch 01 | 建立目录骨架与约束文档 | 后端/前端基础结构 |
| Batch 02 | Agent 主模型替代 App 主模型 | 数据模型/Schema/Repo |
| Batch 03 | Run / Response / Event 核心模型落地 | 运行时基础 |
| Batch 04 | Runtime Core 与 Orchestrator | 执行内核 |
| Batch 05 | Provider Adapter 与 Tool Router | 模型调用与工具路由 |
| Batch 06 | `/v1/responses` 接口落地 | 新主入口 |
| Batch 07 | 旧 chat 接口转接新内核 | 兼容层 |
| Batch 08 | 旧 agent / workflow 接口转接 | 兼容层 |
| Batch 09 | Workflow 节点改造为 Internal Run + Response Projection | 工作流执行改造 |
| Batch 10 | Knowledge / Plugin / MCP 落位 | 能力与接入层 |
| Batch 11 | 前端 API 层与 SSE 协议迁移 | 前端服务层 |
| Batch 12 | 前端 Chat / Agent / Workflow 页面迁移 | 前端页面层 |
| Batch 13 | Observability / Cost / Trace 页面与接口 | 可观测性 |
| Batch 14 | 删除兼容层与旧结构 | 最终收口 |

---

# 5. Batch 01：建立目录骨架与约束文档

## 5.1 Codex 执行动作

### 后端

1. 新建 `backend/app/kernel/*` 基础目录
2. 新建 `backend/app/modules/*` 基础目录
3. 新建 `backend/app/infrastructure/provider/`
4. 新建 `backend/app/api/v1/responses/` 等新 API 目录
5. 统一导出入口文件

### 文档

新增：

```text
/docs/architecture/soit-refactor-principles.md
/docs/architecture/soit-object-mapping.md
/docs/architecture/soit-phase-checklist.md
```

内容至少包括：

- App → Agent 映射
- Dataset → KnowledgeBase 映射
- Legacy chat/agent/workflow 统一接入 Run 体系与 Response Projection Layer
- 兼容层删除原则

## 5.2 验收标准

- 新目录创建完成
- import 路径不报错
- 主应用仍可启动
- 文档可被后续 patch 引用

---

# 6. Batch 02：Agent 主模型替代 App 主模型

## 6.1 目标

把旧 `App*` 结构收敛为 `Agent*` 主结构。

## 6.2 后端目录落位

优先改造以下位置：

```text
backend/app/models/
backend/app/schemas/
backend/app/repositories/
backend/app/services/
backend/app/modules/agent/
```

## 6.3 Codex 执行动作

### 数据模型层

新增或重构以下实体：

- `Agent`
- `AgentVersion`
- `AgentBinding`
- `AgentPublish`

如果当前已有：

- `App`
- `AppVersion`
- `AppBinding`
- `AppPublish`

则要求：

1. 新建新模型，不在旧模型上继续打补丁扩张
2. 旧模型加 `legacy` 标记注释
3. 新旧映射由 service adapter 临时桥接

### schema 层

新增：

- `agent_create.py`
- `agent_update.py`
- `agent_read.py`
- `agent_version_read.py`

### repository 层

新增：

- `agent_repository.py`
- `agent_version_repository.py`

### service 层

新增或重构：

- `agent_service.py`
- `agent_publish_service.py`

要求：

- 不允许 service 内部再使用旧 `App` 作为主返回对象
- 前期可读取旧数据，但返回协议必须面向 `Agent`

## 6.4 数据迁移要求

若已有生产数据模型，先添加迁移：

- 创建 `agents` 系列表
- 临时保留 `apps` 表
- 编写一次性 backfill 脚本（如果需要）

## 6.5 验收标准

- 后端可以读取 Agent 列表、详情、版本
- 新接口返回结构中不再出现 `app_*` 命名
- 旧 `App` 只作为兼容层存在

---

# 7. Batch 03：Run / Response / Event 核心模型落地

## 7.1 目标

建立统一执行记录与事件记录体系。

## 7.2 后端目录落位

```text
backend/app/models/
backend/app/schemas/
backend/app/kernel/events/
backend/app/kernel/trace/
backend/app/kernel/artifacts/
backend/app/modules/observability/
```

## 7.3 Codex 执行动作

### 新增核心模型

- `responses`
- `runs`
- `run_steps`
- `events`
- `artifacts`
- `tool_calls`
- `usage_records`
- `cost_records`
- `approvals`（可先预留）

### 统一枚举

建立统一状态枚举：

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

### 统一事件类型

建立事件类型枚举：

- response.created
- response.in_progress
- response.output_text.delta
- response.output_text.done
- response.tool_call.started
- response.tool_call.completed
- response.tool_call.failed
- response.artifact.created
- response.completed
- response.failed
- run.step.started
- run.step.completed

## 7.4 验收标准

- ORM 模型建立完成
- Alembic 迁移可执行
- 可创建一条测试 response/run/event 数据
- 事件模型与 provider 返回解耦

---

# 8. Batch 04：Runtime Core 与 Orchestrator

## 8.1 目标

建立统一执行内核，禁止 Chat/Agent/Workflow 再各自维护独立运行闭环。

## 8.2 后端目录落位

```text
backend/app/kernel/runtime/
backend/app/kernel/responses/
backend/app/kernel/context/
backend/app/kernel/trace/
```

## 8.3 Codex 执行动作

新增核心类或服务：

- `ResponseOrchestrator`
- `ContextBuilder`
- `RunManager`
- `EventPublisher`
- `TraceRecorder`
- `ArtifactManager`

### 关键职责要求

#### ResponseOrchestrator

负责：

- 接收统一 input
- 绑定 agent / thread / workflow context
- 调用 provider adapter
- 驱动 tool router
- 写入 response / run / event / cost / artifact

#### ContextBuilder

负责：

- 历史消息拼装
- system instructions 合并
- memory / knowledge / agent defaults 合并
- workflow 节点输入上下文合并

#### RunManager

负责：

- 创建 run
- 推进状态
- 创建 run_step
- 结束时统一归档

## 8.4 验收标准

- 可通过单元测试创建一次内部 response run
- chat / agent / workflow 暂未接入也没关系，但内核独立可跑通
- provider 相关逻辑不再散落在业务 service 中

---

# 9. Batch 05：Provider Adapter 与 Tool Router

## 9.1 目标

完成模型调用适配层与工具执行统一路由。

## 9.2 后端目录落位

```text
backend/app/infrastructure/provider/
backend/app/modules/tool/
backend/app/modules/modelhub/
backend/app/kernel/responses/
```

## 9.3 Codex 执行动作

### Provider Adapter

新增：

- `base_provider_adapter.py`
- `openai_responses_adapter.py`
- 其他供应商 adapter 的占位实现

要求：

- 统一输出内部 response event 语义
- 屏蔽供应商原始 chunk 差异
- 前端不得直接依赖供应商字段

### Tool Router

新增：

- `tool_registry.py`
- `tool_router.py`
- `tool_executor.py`
- `tool_permission_guard.py`

要求：

- 工具统一注册
- 工具执行过程必须产生日志事件
- 失败、重试、耗时、输入输出摘要要可记录

## 9.4 验收标准

- 任一 provider adapter 可返回统一事件流
- 一个 mock tool 可被 orchestrator 调起
- tool 事件会落库到 event / tool_call

---

# 10. Batch 06：`/v1/responses` 接口落地

## 10.1 目标

建立后端统一主入口。

## 10.2 后端目录落位

```text
backend/app/api/v1/responses/
backend/app/schemas/
backend/app/kernel/responses/
```

## 10.3 Codex 执行动作

新增接口：

- `POST /v1/responses`
- `GET /v1/responses/{id}`
- `GET /v1/responses/{id}/events`
- `POST /v1/responses/{id}/cancel`
- `POST /v1/responses/{id}/submit_tool_outputs`（可预留）

新增 schema：

- `response_create_request.py`
- `response_read.py`
- `response_event_read.py`

### 请求结构要求

至少支持：

- `agent_id`
- `thread_id`
- `input`
- `model`
- `tools`
- `stream`
- `metadata`

### 返回结构要求

- 标准 response 对象
- 不返回供应商原始 chunk 结构

## 10.4 验收标准

- `/v1/responses` 可创建一次 response
- 支持同步与流式两种路径之一，优先流式
- 接口文档可生成

---

# 11. Batch 07：旧 Chat 接口转接新内核

## 11.1 目标

让旧 Chat UI 不必一次性重写，也能先切到新执行内核。

## 11.2 后端目录落位

```text
backend/app/api/
backend/app/services/
backend/app/kernel/responses/
```

## 11.3 Codex 执行动作

1. 找出现有 chat 发送消息接口
2. 将原本直连 provider / chat service 的实现改为：
   - 解析旧请求
   - 转换为 `ResponseCreateRequest`
   - 调用 `ResponseOrchestrator`
   - 将返回重新适配为旧 UI 所需格式

### 兼容适配要求

新增：

- `legacy_chat_adapter.py`

要求：

- 仅负责协议转换
- 不允许在 adapter 中重新实现完整 chat runtime

## 11.4 验收标准

- 老 Chat 页面仍能工作
- 后端执行链已经切入新 response 内核
- 旧 chat service 仅剩转换逻辑

---

# 12. Batch 08：旧 Agent / Workflow 接口转接

## 12.1 目标

让旧 agent run 与 workflow llm 节点入口统一转到新运行时。

## 12.2 后端目录落位

```text
backend/app/modules/agent/
backend/app/modules/workflow/
backend/app/services/
backend/app/kernel/responses/
```

## 12.3 Codex 执行动作

### Agent

新增或重构：

- `legacy_agent_run_adapter.py`

要求：

- 旧 Agent run 接口不再直接执行模型调用
- 统一转成 response request

### Workflow

找到所有 workflow 中直接调用 provider 的节点执行代码，改为：

- Node Executor -> create internal response run
- response 输出回写 workflow context

## 12.4 验收标准

- agent 执行链与 chat 执行链共享同一 orchestrator
- workflow LLM 节点不再直接持有 provider 逻辑

---

# 13. Batch 09：Workflow 节点改造为 Internal Run + Response Projection

## 13.1 目标

彻底清理 workflow 内部自定义 LLM executor。

## 13.2 后端目录落位

```text
backend/app/modules/workflow/
backend/app/kernel/runtime/
backend/app/kernel/responses/
```

## 13.3 Codex 执行动作

### 节点分类处理

#### LLM Node

改为：

- 构造 internal response request
- 指定 workflow_run_id / node_id / structured_output_schema
- 执行后回写 node output

#### Tool Node

改为走统一 `ToolRouter`

#### Knowledge Node

改为走统一 knowledge retriever

### 删除旧逻辑

删除或标记废弃：

- `workflow_llm_executor.py`
- `workflow_model_service.py`（如仅服务于旧链路）

## 13.4 验收标准

- workflow 的 LLM、tool、knowledge 三类节点接入新统一能力层
- workflow debug 可以读取 run/event 数据

---

# 14. Batch 10：Knowledge / Plugin / MCP 落位

## 14.1 目标

把能力层边界收拢清楚。

## 14.2 后端目录落位

```text
backend/app/modules/knowledge/
backend/app/modules/plugin/
backend/app/modules/integrations/mcp/
backend/app/modules/skill/
```

## 14.3 Codex 执行动作

### Knowledge

要求：

- Dataset 产品语义弱化为 KnowledgeBase
- 检索统一提供给 ContextBuilder / Workflow / Agent

### Plugin

要求：

- Plugin 只负责安装、注册、配置、生命周期
- 不直接承担运行时核心编排职责

### MCP

要求：

- MCP 是标准接入层，不是一级业务中心
- MCP connector / server binding / auth policy 独立落位于 integrations/mcp

### Skill

要求：

- Skill 是复合业务能力，不是底层 Tool 替身
- Skill 可编排 Tool / Knowledge / Workflow / Policy

## 14.4 验收标准

- 能力边界在目录与 service 命名上清晰可见
- MCP 不再散落在 chat/agent/workflow 业务代码中

---

# 15. Batch 11：前端 API 层与 SSE 协议迁移

## 15.1 目标

让前端先从协议层解耦，避免页面层继续绑定旧接口。

## 15.2 前端目录落位

```text
web/src/services/api/
web/src/services/sse/
web/src/modules/responses/
web/src/types/
```

## 15.3 Codex 执行动作

### API 层

新增：

- `responses.ts`
- `agents.ts`
- `workflows.ts`
- `knowledge.ts`
- `plugins.ts`

### SSE 层

新增：

- `response-event-stream.ts`
- `event-normalizer.ts`

### 类型层

新增：

- `response.ts`
- `response-event.ts`
- `run.ts`
- `artifact.ts`

要求：

- 前端统一消费内部 event 类型
- 页面不得直接解析 provider 原始 chunk

## 15.4 验收标准

- 前端有统一 response event 类型定义
- 老页面可通过新 API 层读取数据

---

# 16. Batch 12：前端 Chat / Agent / Workflow 页面迁移

## 16.1 目标

把 UI 从旧概念和旧协议切换到 Agent + Responses 模型。

## 16.2 前端目录落位

```text
web/src/pages/chat/
web/src/pages/agents/
web/src/pages/workflows/
web/src/modules/agents/
web/src/modules/workflows/
web/src/modules/runs/
```

## 16.3 Codex 执行动作

### Chat 页面

要求：

- 消息发送走 `responses.ts`
- 流式展示基于统一 SSE 事件
- tool call / artifact / approval 预留 UI 位置

### Agent 页面

要求：

- 全面替换 `App` 文案、路由、状态对象为 `Agent`
- Agent 详情页展示：instructions、tools、knowledge、model、publish

### Workflow 页面

要求：

- Workflow Debug 面板可查看 response / run / event timeline
- LLM 节点调试结果来源于统一 run 数据

## 16.4 验收标准

- Chat/Agent/Workflow 页面三者协议统一
- 页面中不再出现 provider 原始事件字段依赖
- 主要路由不再使用 App 作为一级概念

---

# 17. Batch 13：Observability / Cost / Trace 页面与接口

## 17.1 目标

补齐生产可用的运行观测能力。

## 17.2 后端目录落位

```text
backend/app/modules/observability/
backend/app/api/v1/observability/
backend/app/kernel/trace/
```

## 17.3 前端目录落位

```text
web/src/pages/observability/
web/src/modules/runs/
```

## 17.4 Codex 执行动作

新增后端接口：

- `GET /v1/runs`
- `GET /v1/runs/{id}`
- `GET /v1/runs/{id}/events`
- `GET /v1/runs/{id}/artifacts`
- `GET /v1/costs`

前端新增页面：

- Run 列表
- Run 详情 Timeline
- Cost 统计页
- Tool 调用记录页

## 17.5 验收标准

- 能定位一次对话/一次 agent run/一次 workflow node run 的完整事件轨迹
- 能看到 token、cost、tool 调用、异常信息

---

# 18. Batch 14：删除兼容层与旧结构

## 18.1 目标

完成收口，不长期保留双轨。

## 18.2 Codex 执行动作

### 删除对象

当以下条件满足时删除：

- 新 Chat / Agent / Workflow 页面已切新协议
- 新 `/v1/responses` 已成为主入口
- workflow 已改用 internal response run

可删除或废弃：

- `App*` 主对象实现
- 旧 `chat_runtime`
- 旧 `workflow_llm_executor`
- provider 直连业务 service
- 前端旧 chat event parser
- 页面中的 `App Center` 核心命名

### 代码清理要求

- 删除 dead code
- 删除旧 DTO
- 删除旧 route
- 删除旧 store 字段
- 删除遗留 feature flag

## 18.3 验收标准

- 仓库中无新增旧概念扩张实现
- Chat / Agent / Workflow 三条执行链统一
- 平台一级主对象为 Agent
- 统一响应主入口为 Responses API

---

# 19. Codex 单次执行模板

每次让 Codex 执行时，建议直接复制以下模板。

```text
请按《SOIT_Codex_Patch_Task_Map.md》执行 Batch XX。
要求：
1. 仅修改该 Batch 相关目录和文件；
2. 优先保证代码结构正确，其次保证最小可运行；
3. 不要顺手扩展旧 App 概念；
4. 输出：
   - 修改文件清单
   - 新增文件清单
   - 数据库迁移说明
   - 接口变更说明
   - 风险与后续 Batch 衔接点
```

---

# 20. 推荐执行顺序

## 第一轮（先打基础）

- Batch 01
- Batch 02
- Batch 03
- Batch 04
- Batch 05
- Batch 06

## 第二轮（兼容旧链路）

- Batch 07
- Batch 08
- Batch 09
- Batch 10

## 第三轮（前端迁移）

- Batch 11
- Batch 12
- Batch 13

## 第四轮（删除旧结构）

- Batch 14

---

# 21. 额外说明

如果你接下来把真实仓库目录贴出来，我建议再生成最后一版：

**“按真实文件路径命名的 Codex 精确补丁清单”**。

那一版会进一步细化到类似：

- `backend/app/api/chat.py` 改到什么程度
- `backend/app/services/chat_service.py` 哪些函数要删除或转接
- `web/src/pages/chat/index.tsx` 如何改用 `responses.ts`
- `web/src/stores/chat.ts` 如何重构状态

这样就不是“按目录执行”，而是“按文件执行”。
