# SOIT 平台新蓝图（Agent 中心版）

> Blueprint note
> 本文档描述长期目标蓝图，用于指导后续演进方向。
> 若与当前仓库实现存在差异，请以 `README.md`、`app/docs/architecture/*`、`web/docs/*` 为当前事实来源。

## 1. 文档目的

本文档用于定义 SOIT 平台在新阶段的统一架构蓝图，作为后续大规模重构、模块迁移、代码生成、架构审查、功能扩展的总基线。

本蓝图的核心目标是：

- 去掉前后端 `App` 概念
- 全面转向 **Agent 中心化**
- 建立统一 Runtime 内核
- 明确 Workflow / Skill / Knowledge / Plugin / MCP 的边界
- 为后续 Codex 长期迭代提供稳定蓝图

---

## 2. 平台定位

SOIT 不是一个传统模块拼盘式平台，也不是单纯的聊天系统。

SOIT 的目标定位是：

> **一个以 Agent 为中心的企业级 AI 平台。**

平台应围绕 Agent 提供两类核心能力：

- **Chat 模式**：用户与 Agent 的即时对话交互
- **Task 模式**：用户提交任务，由 Agent 在后台持续执行

同时，平台应具备以下支撑层：

- Workflow：编排设计层
- Skill：能力复用层
- Knowledge：知识资源层
- Tool：动作能力层
- Plugin：扩展安装层
- MCP：标准接入层
- Runtime / Trace / Artifact / Policy / Observability：平台内核层

---

## 3. 总体架构原则

### 3.1 Agent 是唯一中心对象
前台产品层、后端核心模型、运行时入口，都围绕 Agent 组织。

### 3.2 Chat 不是独立中心，而是 Agent 的默认交互模式
Chat 必须保留，但不再是单独产品中心。

### 3.3 后台执行能力是平台长期价值核心
SOIT 的差异化不只是会对话，而是可以后台执行、持久运行、可审计、可追踪。

### 3.4 Workflow 是高级设计器，不是平台唯一中心
Workflow 必须保留前台入口，但它的职责是服务 Agent，而不是替代 Agent。

### 3.5 Skill 是能力复用层，不是 Prompt 仓库
Skill 应沉淀业务能力、流程能力、策略能力，而不是仅保存提示词。

### 3.6 Plugin 是扩展安装层
Plugin 只负责安装、配置、升级、权限声明、能力导出，不再和 Tool / Skill 争夺运行时地位。

### 3.7 MCP 是标准接入层
MCP 不应成为独立业务中心模块，而应作为 Tool / Plugin 之间的标准接入协议层。

### 3.8 所有执行统一进入 Runtime Core
不能再保留 chat / workflow / agent 各自独立 executor 的长期结构。

---

## 4. 新平台核心结构

新的 SOIT 平台结构应收敛为：

### 用户可见层
- Agents
- Chat
- Workflows
- Knowledge
- Plugin
- Models
- Tasks
- Observability
- Settings

### 平台核心层
- Agent
- Thread
- Run
- RunStep
- Task
- Artifact
- Feedback

### 能力层
- Workflow
- Skill
- Knowledge
- Tool

### 扩展接入层
- Plugin
- MCP Connector
- External Integration

### 基础内核层
- Runtime Core
- Trace
- Policy
- Security
- Identity
- Observability Infra

---

## 5. 核心对象模型

## 5.1 Agent
Agent 是平台唯一主对象，也是最终面向用户的智能体对象。

Agent 必须承载：

- instructions
- model bindings
- workflow bindings
- skill bindings
- knowledge bindings
- tool bindings
- plugin provided capabilities
- policies
- runtime preferences
- publish config

Agent 必须支持两种运行模式：

- Chat Mode
- Task Mode

---

## 5.2 Thread
Thread 表示 Agent 的对话上下文。

Thread 负责：

- 会话上下文承载
- 消息流组织
- 与 Run 的关联
- Chat 模式的上下文管理

---

## 5.3 Run
Run 是统一执行实例，是平台最核心的运行时对象。

所有执行都必须抽象为 Run，包括：

- Chat 交互执行
- Agent 后台任务执行
- Workflow 执行
- Skill 调用
- Tool 调用链路
- Retrieval 过程

Run 应包含：

- input
- output
- status
- steps
- trace
- cost
- latency
- artifacts
- approvals
- errors

---

## 5.4 RunStep
RunStep 表示执行过程中的步骤单元。

RunStep 可对应：

- LLM 调用
- Tool 调用
- Workflow 节点
- Skill 执行
- Retrieval 执行
- Approval 阶段
- Planner / Executor / Verifier 阶段

---

## 5.5 Task
Task 是后台执行包装对象。

Task 负责：

- 调度
- 状态管理
- 长任务运行
- 暂停 / 恢复 / 重试 / 取消
- checkpoint 管理
- 后台进度查询

Task 是企业级后台 Agent 执行的重要基础对象。

---

## 5.6 Artifact
Artifact 表示执行产物。

Artifact 类型包括但不限于：

- 文本
- 结构化 JSON
- 文件
- 报告
- 表格
- 中间快照

Artifact 必须统一归属于 Run / Task / Agent。

---

## 5.7 Workflow
Workflow 是高级编排对象。

Workflow 的职责是：

- 提供可视化流程设计
- 作为 Agent 的编排逻辑
- 作为 Skill 的实现方式
- 作为 Task 模板来源

Workflow 不是平台主对象，但它是重要的高级设计器。

---

## 5.8 Skill
Skill 是可复用业务能力对象。

Skill 的本质是：

> 对 tools、workflow、knowledge、instructions、policy 的高层封装。

Skill 可封装：

- instructions
- workflow/subflow
- tool chains
- knowledge scope
- output schema
- approval rules
- policy constraints

Skill 可被：

- Agent 挂载
- Workflow 调用
- Plugin 导出

---

## 5.9 Tool
Tool 是最底层的可调用动作能力。

例如：

- 调用 API
- 查询数据库
- 创建工单
- 检索外部数据
- 文件转换
- 系统动作执行

Tool 只负责动作，不负责业务流程抽象。

---

## 5.10 Knowledge
Knowledge 是企业知识资源层。

Knowledge 应组织为：

- knowledge base
- document
- chunk
- index
- retrieval profile
- ingestion run

Knowledge 服务于：

- Agent 检索增强
- Chat 上下文补充
- Workflow 检索节点
- Skill 知识作用域

---

## 5.11 Plugin
Plugin 是扩展安装层对象。

Plugin 的职责是：

- install / uninstall
- enable / disable
- config
- upgrade
- permissions
- capability registration

Plugin 可导出：

- tools
- skills
- connectors
- resources
- templates

Plugin 是安装包，不是业务执行对象。

---

## 5.12 MCP Connector
MCP Connector 是标准接入对象。

MCP 相关能力不单独作为产品主中心，而是作为标准接入层存在。

MCP Connector 负责：

- 连接远端或本地 MCP Server
- 鉴权
- 能力同步
- tool/resource/prompt 映射
- 连接健康检查
- 权限范围控制

MCP Connector 输出的能力可以进入：

- Tool Registry
- Knowledge/Resource Registry
- Skill 构建来源
- Plugin 导出能力

---

## 6. 去 App 后的新关系定义

原来的 `App / AppVersion / AppBinding / AppPublish` 不再保留为独立中心概念。

统一替换为：

- `Agent`
- `AgentVersion`
- `AgentBinding`
- `AgentPublish`

关系改为：

- Chat = Agent 的交互模式
- Workflow = Agent 的编排资源
- Skill = Agent 的能力资源
- Knowledge = Agent 的知识资源
- Tool = Agent 的动作资源
- Plugin = Agent 可安装扩展来源
- Task = Agent 的后台执行实例
- Run = Agent 的统一执行记录

---

## 7. 模块职责重定义

## 7.1 Agents
Agent 是平台前台主中心。

前台围绕 Agent 提供：

- 创建
- 配置
- 发布
- 对话
- 任务执行
- 编排查看
- 技能绑定
- 知识绑定
- 工具绑定
- 运行记录查看

---

## 7.2 Chat
Chat 保留，但职责收敛为：

- Agent 默认交互入口
- Thread 视图
- 消息流展示
- 任务触发入口
- Tool / Retrieval / Artifact / Task 状态展示入口

Chat 不再是独立产品中心。

---

## 7.3 Workflows
Workflow 保留一级入口，但职责明确为：

- 高级流程设计工作台
- Agent 编排设计器
- Skill 组合设计器
- Task 模板设计器

普通用户不一定直接使用 Workflow，高级用户和实施人员会使用。

---

## 7.4 Knowledge
Dataset 产品语义正式升级为 Knowledge。

Knowledge 模块负责：

- 文档接入
- 索引构建
- 检索配置
- 知识管理
- 引用能力支持

后端可分阶段迁移，但前台统一以 Knowledge 表达。

---

## 7.5 Plugin
Plugin 模块名可以保留。

但其功能必须重构为：

- 扩展安装中心
- 插件启停中心
- 权限管理中心
- 导出能力展示中心
- MCP 连接能力管理入口之一

Plugin 下可以管理：
- 本地扩展包
- 第三方扩展包
- MCP Connector 型扩展

---

## 7.6 MCP
MCP 不建议作为一级业务模块和 Workflow / Skill 并列。

更合理的方式是：

- 后端作为标准接入层
- 前端作为 Plugin 模块下的子能力管理页，或未来单独放到 Integrations 子域

一句话定义：

> MCP 是标准接入协议层，不是业务主对象层。

---

## 7.7 Bot
Bot 不再作为长期核心对象继续扩张。

后续可处理为：

- Agent 模板
- 历史兼容概念
- 渐进迁移层

---

## 8. Runtime Core 蓝图

## 8.1 Runtime Core 的定位
Runtime Core 是整个平台最核心的技术底座。

Runtime Core 必须统一以下职责：

- run lifecycle
- step lifecycle
- task orchestration
- checkpoint
- retry / resume / cancel
- artifact writing
- trace writing
- policy interception
- approval waiting
- timeout handling
- cost collection

---

## 8.2 统一执行模式

### Chat Mode
- 基于 thread
- 面向即时交互
- 可调用 tool / retrieval / skill / workflow
- 可在交互过程中转为 Task

### Task Mode
- 基于 task
- 面向后台异步执行
- 支持长任务与批处理
- 支持审批、中断恢复与结果产出

---

## 8.3 统一状态机
Run / Task 应共享统一状态语义：

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

---

## 8.4 统一 Trace 结构
Trace 应覆盖：

- run started
- step started
- llm called
- tool called
- tool result
- retrieval called
- retrieval result
- skill executed
- workflow node executed
- artifact created
- approval requested
- approval resolved
- run finished

---

## 8.5 统一 Artifact 结构
Artifact 必须支持：

- typed storage
- preview
- download
- relation to run/task/agent
- replay reference
- lineage tracking

---

## 8.6 统一 Feedback 结构
Feedback 应支持：

- 用户反馈
- 管理员标注
- 调试标签
- 评测样本回流

---

## 9. Agent 蓝图

## 9.1 Agent 的最终形态
Agent 是用户真正使用的平台对象。

Agent 必须具备：

- 可对话
- 可调用知识
- 可调用技能
- 可触发工作流
- 可执行后台任务
- 可查看运行记录
- 可配置权限策略
- 可挂载扩展能力

---

## 9.2 Agent 页面建议结构
建议页签：

- 对话
- 任务
- 知识
- 技能
- 编排
- 工具
- 运行记录
- 配置

---

## 9.3 Agent 绑定模型
一个 Agent 可以绑定：

- 1..n models
- 0..n workflows
- 0..n skills
- 0..n knowledge bases
- 0..n tools
- 0..n policies
- 0..n plugin provided capabilities
- 0..n mcp provided capabilities

---

## 10. Workflow 蓝图

## 10.1 Workflow 新定位
Workflow 是高级设计器，不是最终用户主对象。

## 10.2 Workflow 发布目标
Workflow 可发布为：

- Agent internal orchestration
- Skill implementation
- Task template

## 10.3 Workflow 节点建议
支持以下节点：

- LLM Node
- Tool Node
- Retrieval Node
- Skill Node
- Approval Node
- Agent Node
- Condition Node
- Transform Node
- MCP Tool Node（本质仍归 Tool 类）

---

## 11. Skill 蓝图

## 11.1 Skill 定义
Skill 是业务能力抽象，不是 Prompt 收藏夹。

## 11.2 Skill 的组成
可由以下内容组合而成：

- instructions
- tools
- workflows
- knowledge scope
- output schema
- policies
- approvals

## 11.3 Skill 的作用
- 为 Agent 提供可复用能力
- 为 Workflow 提供复用节点能力
- 为 Plugin 提供导出业务能力
- 为组织沉淀最佳实践

---

## 12. Plugin 蓝图

## 12.1 Plugin 定义
Plugin 是扩展安装包与能力分发容器。

## 12.2 Plugin 职责
- 安装
- 卸载
- 配置
- 升级
- 权限声明
- 导出能力注册
- 生命周期管理

## 12.3 Plugin 可提供内容
- tools
- skills
- connectors
- resources
- templates
- mcp connectors
- admin config pages（后续可选）

---

## 13. MCP 蓝图

## 13.1 MCP 的平台定位
MCP 是标准接入层，不是业务主中心层。

## 13.2 MCP 的职责
- 接入外部系统能力
- 暴露标准化 tools / resources / prompts
- 向上适配到 SOIT 的 Tool / Knowledge / Skill 体系
- 提供标准连接方式与能力同步机制

## 13.3 MCP 在 SOIT 中的位置
MCP 位于：

- Plugin 与 Tool 之间
- Integration Layer 中
- Runtime 之下、Agent 能力层之上

## 13.4 MCP 能力映射
- MCP Tool → SOIT Tool
- MCP Resource → SOIT Knowledge/Context Resource
- MCP Prompt → Skill/Template 构建来源
- MCP Server → Connector/Plugin 管理对象

## 13.5 MCP 的前端入口建议
短期不作为一级导航。  
更建议放在：

- Plugin 模块下的 `MCP Connectors`
- 或未来 `Integrations` 子域中

---

## 14. Knowledge 蓝图

## 14.1 Knowledge 的职责
- 数据接入
- 文档清洗
- 分段
- 索引
- 检索
- 引用
- 权限范围控制

## 14.2 Knowledge 内部分层
建议逐步拆分为：

- ingestion pipeline
- knowledge store
- retrieval service

## 14.3 Knowledge 的服务对象
- Agent
- Chat
- Workflow
- Skill

---

## 15. ModelHub 蓝图

ModelHub 继续保留，但要强化为平台基础能力层。

应支持：

- provider 管理
- tenant model sync
- capability tags
- route / fallback
- quota / budget
- 成本治理
- 不同模型能力矩阵管理

ModelHub 由 Agent 使用，不再独立抢产品中心。

---

## 16. Observability 蓝图

Observability 是平台长期稳定性的核心保障。

必须支持：

- run list
- run detail
- step timeline
- tool trace
- retrieval trace
- skill trace
- workflow trace
- artifact preview
- cost / latency
- success / failure rate
- feedback
- replay / inspect

---

## 17. 前台信息架构蓝图

长期建议导航：

- Agents
- Chat
- Workflows
- Knowledge
- Plugin
- Models
- Tasks
- Observability
- Settings

说明：

- Agents：平台中心
- Chat：默认交互入口
- Workflows：高级设计器
- Knowledge：知识中心
- Plugin：扩展安装中心
- Models：模型基础设施入口
- Tasks：后台执行中心
- Observability：运行分析中心

MCP 不单列一级导航。

---

## 18. 后端目录演进方向

后端建议逐步收敛为这些核心域：

- `kernel/runtime`
- `kernel/trace`
- `kernel/policy`
- `kernel/security`
- `modules/agent`
- `modules/workflow`
- `modules/knowledge`
- `modules/skill`
- `modules/modelhub`
- `modules/plugin`
- `modules/integrations/mcp`
- `modules/observability`
- `modules/identity`

原则：

- 以 Agent 为中心
- 以 Runtime 为唯一执行内核
- 以 MCP 为集成协议层
- 不再保留 AppCenter 作为长期中心域

---

## 19. 重构原则

### 19.1 去 App，全面 Agent 化
前后端统一去掉 App 概念。

### 19.2 先统一内核，再迁前台
优先做 Runtime、Run、Task、Trace、AgentBinding 的统一。

### 19.3 不再增加新孤岛模块
任何新能力都必须归属到：
- Agent
- Workflow
- Skill
- Knowledge
- Plugin
- MCP
- Runtime
这些既定蓝图对象中。

### 19.4 MCP 只能作为接入层，不可膨胀成新的业务主中心
防止平台再次出现概念膨胀。

### 19.5 所有执行统一归 Run
这是可审计、可调试、可回放、可治理的底线。

---

## 20. 给 Codex 的长期约束

后续所有 Codex 迭代都应遵守：

- 不再创建新的 App 概念与对象
- 不再创建平行执行内核
- Chat 只能是 Agent 交互模式
- Workflow 只能是高级编排设计器
- Skill 必须是业务能力层，不是 Prompt 仓库
- Plugin 必须是扩展安装层
- MCP 必须是标准接入层
- Dataset 必须统一向 Knowledge 迁移
- 所有执行必须接入 Run / Trace / Artifact / Task 体系

---

## 21. 总结

SOIT 的新方向应明确为：

> **以 Agent 为中心，以 Runtime 为内核，以 Workflow / Skill / Knowledge 为能力层，以 Plugin 为扩展层，以 MCP 为标准接入层的企业级 AI 平台。**

平台从旧形态：

- chat / bot / dataset / workflow / agent 并列

收敛为新形态：

- **Agent 中心**
- **Chat 交互**
- **Task 执行**
- **Workflow 编排**
- **Skill 复用**
- **Knowledge 增强**
- **Plugin 扩展**
- **MCP 接入**
- **Runtime 统一**
- **Observability 治理**

这就是 SOIT 后续长期演进最稳定、也最不容易跑偏的蓝图。
