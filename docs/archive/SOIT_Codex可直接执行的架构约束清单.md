# SOIT Codex 可直接执行的架构约束清单

## 1. 目标

本清单用于约束 Codex 在 SOIT 重构与后续持续迭代中的架构方向，避免新增代码再次把平台带回旧的模块并行形态。

Codex 在执行任何重构、重命名、模块拆分、API 调整、前端迁移、数据模型调整时，都必须遵守本清单。

---

## 2. 总体约束

### 2.1 平台唯一中心对象是 Agent
- 不允许再引入新的平台主中心对象与 Agent 并列竞争。
- 前后端都必须围绕 Agent 建模。
- 用户最终使用对象统一是 Agent。

### 2.2 去掉 App 概念
- 不允许新增 `App`、`AppVersion`、`AppBinding`、`AppPublish` 等新对象。
- 旧的 App 相关概念应迁移为：
  - `Agent`
  - `AgentVersion`
  - `AgentBinding`
  - `AgentPublish`
- 不允许保留 App 与 Agent 双中心长期并存。

### 2.3 Chat 只能是 Agent 的交互模式
- 不允许把 Chat 再扩张成独立产品中心。
- Chat 页面、Chat API、Chat 会话都必须归属到 Agent。
- Chat 的本质是 Agent 的 Thread 视图与即时交互视图。

### 2.4 所有执行必须统一进入 Runtime Core
- 不允许新增新的平行 executor 内核。
- 不允许模块私自维护完整独立运行时。
- Chat、Task、Workflow、Skill、Tool 调用都必须进入统一 Run 体系。

### 2.5 Run 是统一执行记录
- 所有执行必须产生 `Run`。
- 所有 Run 必须具备统一状态、trace、artifact、error、cost、latency 信息。
- 不允许某个模块绕过 Run 直接写一套独立执行记录体系。

---

## 3. 核心对象约束

### 3.1 Agent
Agent 必须是唯一主对象，负责组织：

- model bindings
- workflow bindings
- skill bindings
- knowledge bindings
- tool bindings
- plugin provided capabilities
- mcp provided capabilities
- policies
- runtime preferences

### 3.2 Thread
- Thread 必须从属于 Agent。
- Thread 只负责上下文与消息流组织。
- 不允许 Thread 自己演化出新的业务执行中心。

### 3.3 Run
- Run 是统一执行实例。
- Run 必须统一承载：
  - Chat 执行
  - Task 执行
  - Workflow 执行
  - Skill 调用
  - Tool 调用
  - Retrieval 过程
- 所有可追踪执行都必须落到 Run。

### 3.4 Task
- Task 是后台执行包装对象。
- Task 必须关联 Run。
- Task 负责调度与状态控制，不负责替代 Run。

### 3.5 Artifact
- 所有重要结果必须沉淀为 Artifact。
- Artifact 必须与 Run / Task / Agent 可关联。
- 不允许各模块自造一套“结果文件”模型而不接入 Artifact。

---

## 4. 模块职责约束

### 4.1 Agent 模块
Agent 模块必须是平台中心模块。  
任何新功能优先考虑如何服务 Agent，而不是新增独立主模块。

### 4.2 Workflow 模块
Workflow 只能定位为：

- Agent 编排设计器
- Skill 实现方式
- Task 模板设计器

不允许 Workflow 再次演化为平台唯一中心。

### 4.3 Skill 模块
Skill 必须是业务能力层，而不是 Prompt 仓库。  
Skill 应封装：

- instructions
- tools
- workflows
- knowledge scope
- output schema
- policies
- approvals

不允许把 Skill 实现成仅保存 prompt text 的轻薄对象。

### 4.4 Knowledge 模块
- Dataset 必须逐步迁移为 Knowledge。
- 不允许继续强化 Dataset 作为长期产品语义。
- Knowledge 应负责 ingestion、index、retrieval、citation、scope control。

### 4.5 Tool 模块
- Tool 只能表示原子动作能力。
- Tool 不负责业务流程编排。
- Tool 不负责安装包分发。
- Tool 不等于 Skill，不等于 Plugin。

### 4.6 Plugin 模块
Plugin 只能定位为扩展安装层。  
Plugin 的职责只能包括：

- install / uninstall
- enable / disable
- config
- upgrade
- permission declaration
- exported capability registration

不允许 Plugin 再作为运行时业务主对象。

### 4.7 MCP 模块/能力
MCP 只能作为标准接入层存在。  
不允许把 MCP 做成一个与 Agent / Workflow / Skill / Knowledge 并列的业务主中心模块。

MCP 的职责只能包括：

- 连接 MCP Server
- 鉴权
- tool/resource/prompt 同步
- 能力映射
- 健康检查
- 权限范围控制

MCP 的输出应进入：
- Tool Registry
- Knowledge/Resource Registry
- Skill 构建来源
- Plugin 导出能力体系

---

## 5. Runtime Core 约束

### 5.1 统一执行模式
Runtime Core 只能支持两种主模式：

- Chat Mode
- Task Mode

不允许继续为每个业务模块创建独立主模式。

### 5.2 统一状态机
Run / Task 必须共享统一状态语义：

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

不允许各模块自定义一套难以对齐的状态枚举。

### 5.3 统一 Step 模型
每个 Run 的执行细节必须通过 RunStep 表达。  
RunStep 至少应覆盖：

- llm
- tool
- workflow node
- skill
- retrieval
- approval
- planner
- executor
- verifier

### 5.4 统一 Retry / Resume / Cancel
- 长任务必须可恢复。
- 失败任务必须具备重试机制。
- 后台任务必须支持取消。
- 不允许各模块各自写一套不兼容的重试恢复逻辑。

### 5.5 统一 Checkpoint
- 后台执行必须支持 checkpoint。
- 不允许长任务只靠内存态推进而无持久恢复能力。

---

## 6. Trace / Observability 约束

### 6.1 所有执行必须可追踪
必须统一生成 trace，至少覆盖：

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

### 6.2 所有执行必须可检查
必须支持：
- run detail
- step timeline
- error inspection
- artifact preview
- cost / latency 统计

### 6.3 不允许只写日志不落结构化 trace
纯文本日志不能替代统一 trace 体系。

---

## 7. 前端架构约束

### 7.1 一级导航约束
长期一级导航只能围绕以下对象组织：

- Agents
- Chat
- Workflows
- Knowledge
- Plugin
- Models
- Tasks
- Observability
- Settings

MCP 不单独作为一级导航。

### 7.2 Agent 必须是前台主中心
- Agent 列表与 Agent 详情必须成为前台主中心。
- 新功能优先挂到 Agent 详情页，而不是新增独立一级页面。

### 7.3 Chat 必须归属 Agent
- Chat 页面必须支持选择或绑定 Agent。
- 会话必须明确归属某个 Agent。
- Chat 中触发的任务必须回流到 Agent 的 Tasks。

### 7.4 Workflow 是高级设计入口
- Workflow 可以保留独立入口。
- 但 Workflow 只能作为高级设计器，不可再次成为平台唯一主中心。

### 7.5 Plugin 页面职责
Plugin 页面只能用于：
- 安装扩展
- 配置扩展
- 升级扩展
- 查看导出能力
- 管理 MCP connectors

不允许 Plugin 页面承担运行时主功能。

---

## 8. MCP 落位约束

### 8.1 MCP 不做业务主对象
MCP 不允许直接出现在前台“主业务对象”层。

### 8.2 MCP 必须落在 Integration Layer
MCP 后端目录应归属：
- `modules/integrations/mcp`
或等价的集成层目录。

### 8.3 MCP 能力映射必须标准化
- MCP Tool → SOIT Tool
- MCP Resource → SOIT Knowledge/Context Resource
- MCP Prompt → Skill/Template 构建来源

不允许 MCP 接入后直接绕过 Tool / Knowledge / Skill 体系被 Agent 特判调用。

### 8.4 MCP 管理入口建议
前端优先放在：
- Plugin 模块下的 `MCP Connectors`
- 或 Integrations 子域

---

## 9. 数据模型约束

### 9.1 去 App 化
Codex 在新增表或重构表时，不允许继续围绕 App 建模。  
相关模型统一 Agent 化。

### 9.2 Agent Binding
资源绑定必须优先通过 AgentBinding 表达，不允许为每个资源再单独发明一套平行绑定模型。

### 9.3 Result/Output 模型收敛
执行结果统一收敛到：
- Run
- RunStep
- Artifact
- Feedback

不允许各模块分别创建：
- xxx_result
- xxx_log
- xxx_output
- xxx_history
且不接入统一运行时体系。

---

## 10. 代码组织约束

### 10.1 后端核心目录方向
后端应逐步收敛为：

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

### 10.2 禁止新增平行中心域
不允许再引入：
- appcenter 式新中心域
- chat 自治运行时
- workflow 自治运行时
- plugin 自治运行时

### 10.3 优先抽公共内核
发现多个模块逻辑重复时，必须优先抽到 kernel/runtime 或通用 capability 层，而不是复制到各模块。

---

## 11. 重构执行顺序约束

Codex 进行大规模重构时，必须按以下顺序执行：

### 阶段 1：先统一内核
- 去 App 化
- 统一 Agent 核心对象
- 统一 Run / RunStep / Task / Artifact / Trace
- 统一状态机与 runtime core

### 阶段 2：再收敛能力层
- Workflow 重新定位
- Skill 正式落地
- Knowledge 语义升级
- Plugin 重新定位
- MCP 接入层落位

### 阶段 3：最后迁前端
- Agent 中心化导航
- Chat 归属 Agent
- Workflow 高级设计器化
- Plugin 页面转为安装中心
- MCP 放入 Plugin/Integrations 子域

不允许先大改前端页面、后补后端内核。

---

## 12. 验收判定标准

当 Codex 完成一轮重构后，应至少满足以下判定：

### 12.1 架构判定
- App 概念已退出主架构
- Agent 成为唯一主对象
- MCP 未膨胀为主业务中心
- Plugin 不再承担运行时主业务

### 12.2 运行时判定
- Chat / Task / Workflow / Skill / Tool 调用均进入统一 Run
- 存在统一状态机
- 存在统一 Trace / Artifact 体系

### 12.3 产品判定
- 前台围绕 Agent 组织
- Chat 归属 Agent
- Workflow 为高级设计器
- Knowledge 替代 Dataset
- Plugin 为安装中心

### 12.4 可持续性判定
- 新功能不需要再新增平行中心模块
- 新能力可自然落入 Agent / Workflow / Skill / Knowledge / Plugin / MCP / Runtime 之一
- 平台具备长期迭代的一致性

---

## 13. 最终一句话约束

> **SOIT 后续所有迭代，必须坚持：Agent 是中心，Runtime 是内核，Workflow / Skill / Knowledge 是能力层，Plugin 是扩展安装层，MCP 是标准接入层。**

任何偏离这条主线的实现，都应视为架构回退。
