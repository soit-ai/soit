# SOIT 现有响应重构为新 Responses API 方案

## 1. 文档目标

本文档用于指导 SOIT 将现有分散的响应体系逐步重构为统一的 Responses API 资源层与统一运行时模型，确保后续 Chat、Agent、Workflow、Tool、MCP、Memory、Knowledge 等能力可以收敛到一致的数据流与执行抽象之上。

本方案重点解决以下问题：

- 现有 chat、agent、workflow 的响应协议割裂
- 前端与 provider 原始返回结构耦合过深
- 工具调用链路缺乏统一抽象
- 上下文、记忆、检索、审批能力难以纳入同一运行时
- trace、cost、replay、audit 难以形成统一底层模型

---

## 2. 现状判断

根据当前 SOIT 的产品方向与已有模块规划，现有响应体系大概率存在以下典型问题。

### 2.1 Chat、Agent、Workflow 各自维护不同调用路径

常见现状包括：

- Chat 页面走一套 chat message 接口
- Agent 页面或 Agent Runtime 走另一套 run 接口
- Workflow 的 LLM 节点直接调用 provider 或走独立 service

问题：

- 调用协议重复建设
- 状态模型不一致
- 工具集接入方式不统一
- 前端复用困难
- 后期 MCP / Approval / Trace 集成成本高

### 2.2 输入输出模型仍以 message array 为中心

这会导致：

- tool call、artifact、approval 这类非纯文本结果难以优雅表达
- 结构化输出与多模态输入不易扩展
- 事件流和最终结果混杂在一起

### 2.3 工具调用嵌入在业务逻辑中

很多系统在演进中会出现：

- 部分工具在 chat service 中直接调用
- 部分工具在 agent runner 中直接调用
- 部分 workflow 节点直接调用内部 service

问题：

- 工具不可统一注册
- 权限和审批不可统一
- trace 不完整
- 成本无法准确归因

### 2.4 事件追踪能力不足

常见问题：

- 只有最终文本结果，没有运行过程事件
- 工具开始、完成、失败没有统一记录
- usage/cost 不可归因到具体阶段
- 难以做 debug timeline 和 replay

### 2.5 Provider 耦合较重

如果前端或业务层直接依赖 provider 返回结构，会带来：

- 切换模型困难
- 兼容多模型困难
- 前端协议不断膨胀
- 平台内核被厂商协议牵引

---

## 3. 重构目标

本次重构目标不是仅仅“替换一个接口地址”，而是要完成“Run 作为执行真相源、Responses 作为北向投影层”的边界统一。

核心目标如下：

1. 建立统一的 `/v1/responses` 主入口
2. 建立统一的 Response / Run / Event 核心对象模型
3. 建立统一的 SSE 语义事件流
4. 建立统一的 Tool Router
5. 建立统一的 Provider Adapter
6. 将 Chat / Agent / Workflow 逐步收敛到同一运行时
7. 为 MCP、Memory、Knowledge、Approval、Artifact 预留标准接入位

---

## 4. 重构总策略

建议采用：

**先抽象、再兼容、后迁移、最后淘汰旧接口。**

不要一次性彻底推倒重来。建议分四段进行。

### 阶段一：引入新内核，不动旧业务入口

目标：先把底层统一运行时和 Responses 投影层做起来。

包括：

- 建立 Response / Run / Event 核心表
- 建立 Response 资源协调层
- 建立 Provider Adapter
- 建立 Tool Router
- 建立统一 SSE 语义事件

这一阶段允许旧接口继续存在，但新能力都优先基于 Run 体系实现，再由 Responses 对外暴露统一语义。

### 阶段二：旧接口适配到新内核

目标：让旧 chat/agent/workflow 接口不再直连旧逻辑，而是转调统一 Run 体系，并复用 Responses 资源投影层。

这样可以做到：

- 对外兼容旧前端
- 对内统一新运行时

### 阶段三：前端改造为原生 Responses API

目标：逐步让 Chat、Agent Console、Workflow Debug 面板直接消费 `/v1/responses` 和统一事件流。

### 阶段四：淘汰旧协议与旧 service

目标：删除历史兼容层与重复逻辑，统一为新架构。

---

## 5. 重构后的目标架构

```text
Existing UI / New UI / SDK
        |
        +--> Legacy Compatibility Layer
        |         |
        |         v
        |   Response Resource / Semantic Layer
        |
        +--> Native /v1/responses
                  |
                  v
           Response Resource / Semantic Layer
                  |
                  v
             Runtime Core / Run / RunStep
                  |
                  +--> Conversation Manager
                  +--> Context Builder
                  +--> Tool Router
                  +--> MCP Gateway
                  +--> Memory Manager
                  +--> Knowledge Retriever
                  +--> Approval / Policy
                  +--> Usage / Cost
                  +--> Trace Recorder
                  |
                  v
             Provider Adapters
```

---

## 6. 现有模块到新模型的映射关系

### 6.1 Chat 模块

现有 Chat 的 message-based 请求，重构后映射为：

- 页面输入 -> Response.input
- 历史消息 -> Conversation + ConversationItems
- 模型生成 -> Response.output projection
- 流式返回 -> Response semantic event stream
- 工具调用 -> Tool Router + Tool Events

即：

**Chat 不再是一套独立协议，而是 Run 的一种触发方式，由 Response 统一对外暴露。**

### 6.2 Agent 模块

现有 Agent 逻辑建议重构为：

- Agent 只保留配置、策略、能力绑定
- Agent 执行统一走 Run 体系，Responses 负责对外资源投影

Agent 实际上成为：

- 默认 instructions
- 默认 tools
- 默认 mcp_servers
- 默认 memory policy
- 默认 dataset policy
- 默认 approval policy

即：

**Agent = Response Profile + Runtime Policy Bundle**

### 6.3 Workflow 模块

现有 Workflow 的 LLM 节点不要再直连 provider。

统一改为：

- Workflow Node -> create internal run and linked response projection
- Response 完成后将结构化输出回写到 workflow context
- 下游节点继续执行

这样后续：

- Workflow 与 Chat 共享工具体系
- Workflow 与 Agent 共享 run/trace/cost
- Workflow 可直接复用 structured output、artifact、approval 等能力

---

## 7. 核心对象重构方案

## 7.1 新增核心表

建议优先新增以下表，而不是直接改旧表：

- responses
- runs
- response_events
- run_steps
- artifacts
- approvals
- usage_records
- cost_records

原因：

- 降低对旧逻辑侵入
- 便于灰度迁移
- 便于回滚
- 便于双写验证

## 7.2 保留旧会话表并逐步迁移

如果当前已有 chat sessions / chat messages 表，建议先保留，并做映射层。

短期策略：

- 旧 message 表继续服务旧页面
- 新 Response 流程将必要结果同步或映射回旧表
- 待前端完成迁移后，再将 conversation 体系切换为新主表

## 7.3 conversation_items 与 response_events 分离

切勿把两者混为一个日志表。

建议：

- conversation_items：会话语义层
- response_events：对外语义事件层
- runs / run_steps：执行过程真相层

---

## 8. 接口重构方案

## 8.1 新增原生接口

优先新增：

- `POST /v1/responses`
- `GET /v1/responses/{id}`
- `GET /v1/responses/{id}/events`
- `POST /v1/responses/{id}/cancel`

这是后续主接口。

## 8.2 旧接口兼容转发

现有旧接口先不删除，而是改造成兼容层：

- 旧 chat 接口 -> 内部调用统一 Run 体系
- 旧 agent run 接口 -> 内部调用统一 Run 体系
- 旧 workflow llm service -> 内部调用统一 Run 体系

这样能保证：

- 外部暂时不破坏
- 内部逻辑开始统一

## 8.3 兼容模式建议

可增加兼容路由：

- `/compat/openai/v1/responses`
- `/compat/openai/v1/chat/completions`

用途：

- 接入已有 SDK
- 兼容外部生态
- 压测与回归测试

---

## 9. Provider 重构方案

### 9.1 现状问题

如果当前业务模块直接调用 OpenAI、Claude、Gemini 等 SDK，后续必须收口。

### 9.2 目标状态

所有模型调用统一通过 Provider Adapter。

要求：

- Chat 不可直连 provider
- Agent 不可直连 provider
- Workflow 节点不可直连 provider
- 工具内部如需模型能力，也应走 adapter 或受控 model service

### 9.3 实施步骤

1. 提取现有 provider 调用逻辑到 adapters 层
2. 定义 CanonicalModelRequest / CanonicalModelEvent
3. 所有旧调用方改为调用 adapter facade
4. 将 adapter 输出转成统一 Runtime Event

---

## 10. Tool 重构方案

### 10.1 现状问题

现有工具能力可能散落在不同 service 内。

### 10.2 目标状态

建立统一 Tool Registry + Tool Router。

所有工具调用必须走：

- ToolSpec 注册
- 参数校验
- 权限与审批判断
- 执行
- 输出标准化
- event 记录

### 10.3 重构步骤

1. 梳理现有内置工具、数据检索、外部连接器能力
2. 统一抽象为 ToolSpec
3. 将旧 service 直接调用改造成 Tool Router 调用
4. 把工具结果统一写入 run_steps，并按需投影为 response events

---

## 11. 流式返回重构方案

### 11.1 现状问题

现有系统可能存在：

- 前端直接消费 provider token delta
- 不同页面流式协议不一致
- 工具事件无法流式展示

### 11.2 目标状态

统一前端只消费 SOIT SSE 语义事件。

### 11.3 实施步骤

1. 建立统一 SSE event schema
2. provider delta 先进入 adapter
3. adapter 转换为 canonical event
4. runtime 记录到 run / run_step，并按需投影为 SOIT response event
5. 前端按事件类型渲染

### 11.4 前端改造重点

需要重点改造：

- Chat 消息流展示
- Tool Card 展示
- Approval Card 展示
- Artifact 展示
- Trace Timeline 展示

---

## 12. Conversation 与上下文重构方案

### 12.1 短期策略

先兼容旧消息存储，不强行一次性替换。

### 12.2 中期策略

逐步建立：

- conversations
- conversation_items
- context summaries
- memory links

### 12.3 长期策略

SOIT 自身成为会话状态唯一真相源，provider 侧状态仅作临时优化。

---

## 13. Memory / Knowledge / MCP 迁移位置

### 13.1 Memory

从“提示词拼接逻辑”中抽出来，改由 Context Builder 负责注入。

### 13.2 Knowledge / RAG

从“模型前手工拼接文本”迁移为结构化上下文来源，并记录 retrieval 事件。

### 13.3 MCP

不要平行挂在 Agent 模块下，统一作为 Tool Source 接入 Tool Registry。

---

## 14. 迁移阶段规划

## 阶段 A：打底层

目标：不改前端主流程，先把新内核做起来。

任务：

1. 建立 Response / Run / Event 数据表
2. 建立 Response 资源协调层
3. 建立 Provider Adapter 第一版
4. 建立 Tool Router 第一版
5. 建立 SSE 语义事件协议
6. 建立基础 trace 能力

交付结果：

- Run 体系可独立运行
- 可从测试接口创建 response projection

## 阶段 B：兼容旧入口

目标：旧系统内部改走新内核。

任务：

1. 旧 chat 接口转调统一 Run 体系
2. 旧 agent run 转调统一 Run 体系
3. workflow llm 节点转调统一 Run 体系
4. 补齐旧返回结构与新事件流之间的映射

交付结果：

- 用户无感知
- 内部数据流开始统一

## 阶段 C：前端原生切换

目标：Chat/Agent/Workflow UI 逐步切到新协议。

任务：

1. Chat 页面使用 `/v1/responses`
2. 前端统一消费 SSE 语义事件
3. Agent Console 接入统一 Trace
4. Workflow Debug 页接入 Run Timeline

交付结果：

- 新 UI 与 Run + Responses 边界完全对齐

## 阶段 D：移除旧逻辑

目标：收尾和清理。

任务：

1. 删除旧 chat 内核逻辑
2. 删除旧 agent 专属执行通道
3. 删除 workflow 直连 provider 逻辑
4. 删除前端 provider 专属处理逻辑
5. 收敛为单一运行时内核

---

## 15. 推荐的 P0 实施清单

建议第一批必须完成：

### P0-1 接口与路由

- 新增 `/v1/responses`
- 新增 `/v1/responses/{id}`
- 新增 `/v1/responses/{id}/events`

### P0-2 数据模型

- responses
- response_events
- runs
- run_steps

### P0-3 运行时

- Response 资源协调层
- Context Builder 最小版
- Tool Router 最小版
- OpenAI Adapter 第一版

### P0-4 流式协议

- SSE 输出
- response.output_text.delta
- tool.call.*
- response.completed

### P0-5 兼容层

- 旧 chat 入口转调新内核

### P0-6 前端试点

- 先选择一个 Chat 页面试点接入新 Responses API

---

## 16. 推荐的 P1 实施清单

### P1-1 Structured Output

- response_format
- output_json.completed

### P1-2 Knowledge / RAG

- retrieval logs
- context.dataset.attached

### P1-3 Memory

- memory attach
- memory write pipeline

### P1-4 MCP

- MCP Gateway
- MCP Imported Tools

### P1-5 Approval

- approval.requested
- approval.approved / rejected

### P1-6 Trace Viewer

- Run Timeline
- Tool Trace
- Usage/Cost 面板

---

## 17. 风险点与控制建议

### 风险一：一次性改动过大

控制方式：

- 先新增，不先替换
- 通过兼容层逐步收口
- 双写验证关键数据

### 风险二：旧前端耦合 provider 流

控制方式：

- 新页面先试点
- 建统一事件映射层
- 逐步清理前端 provider 专属逻辑

### 风险三：工具体系迁移不彻底

控制方式：

- 工具能力先统一登记
- 新功能禁止绕过 Tool Router
- 老功能分批改造

### 风险四：Workflow 节点改造成本高

控制方式：

- 先只改 LLM 节点
- 其他节点保持不动
- 逐步把 artifact / approval 接进去

---

## 18. 重构完成后的目标状态

当本次重构完成后，SOIT 应达到以下状态：

1. Chat、Agent、Workflow 全部共享同一 Run Runtime
2. 前端全部消费统一语义事件流
3. 模型调用全部经过 Provider Adapter
4. 工具调用全部经过 Tool Router
5. MCP 成为 Tool Source 的一种
6. Memory、Knowledge、Approval 均有统一接入位
7. Trace、Cost、Replay 具备统一底座

---

## 19. 最终落地原则

本次重构建议始终坚持以下原则：

- 先统一执行抽象，再统一产品功能
- 先统一运行时，再统一接口表现
- 先新增兼容层，再淘汰旧逻辑
- 所有模型调用统一收口
- 所有工具调用统一收口
- 所有流式输出统一语义事件化

---

## 20. 一句话重构目标

可以将本次重构的目标总结为：

**将 SOIT 当前分散的 chat / agent / workflow 响应体系，统一重构为以 Run / RunStep 为执行真相源、以 Responses 为北向资源层、以事件流为对外语义协议、以 Tool/MCP 为扩展层、以 Provider Adapter 为解耦层的新一代运行时。**

---

## 21. 建议的执行顺序

建议研发推进顺序如下：

1. 建 Response 资源协调层
2. 建 Run/RunStep/ResponseEvent 核心表
3. 建 OpenAI Adapter
4. 建统一 SSE 事件协议
5. 旧 chat 接口转调新内核
6. Chat 页面试点切到 `/v1/responses`
7. Workflow LLM 节点切换
8. Agent 运行时切换
9. 接入 MCP / Memory / Knowledge / Approval
10. 清理旧协议和旧 service

这样推进，既不会一开始重构过猛，也能逐步形成真正统一的数据流底座。
