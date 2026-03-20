# SOIT 1.0 研发任务清单

## 文档目标

本清单用于指导 SOIT 1.0 阶段的研发推进、范围控制、任务优先级划分与版本验收。

SOIT 1.0 的核心目标不是做成一个大而全的平台，而是先把平台的主轴能力打通，让真实用户能够完成核心任务并稳定使用。

---

## 一、1.0 总体目标

SOIT 1.0 聚焦于构建一个可用的 Agent / Workflow / Knowledge 平台，支持以下两条核心链路：

### 核心链路 A
创建知识库 → 上传文档并完成索引 → 创建 Agent → 绑定模型、知识库、工具 → 发起对话 / 执行任务 → 查看运行结果与日志

### 核心链路 B
创建 Workflow → 配置节点 → 发布 → 执行 → 查看运行记录与结果

只要这两条链路可稳定运行，SOIT 1.0 即具备进入试用与小范围上线的基础条件。

---

## 二、1.0 执行总约束

### 约束 1：必须严格按照 SOIT 1.0 规划推进
所有研发工作必须严格围绕 SOIT 1.0 当前规划执行，不得偏离 1.0 的目标边界。

### 约束 2：禁止做过多扩展
在 1.0 阶段，任何不直接提升主链路闭环能力的扩展性开发、展示型开发、预研型开发、概念型开发，原则上都不进入主研发计划。

### 约束 3：先闭环，后扩展
优先保证以下能力闭环：
- 可创建
- 可配置
- 可发布/启用
- 可执行/使用
- 可查看结果
- 可定位问题

在未完成闭环之前，不进行大范围功能扩展。

### 约束 4：不追求大而全
SOIT 1.0 不追求一次性覆盖商店、安全控制台、Memory 产品化、复杂运营体系、复杂商业化能力等非核心模块。

### 约束 5：所有任务都必须服务于主轴
仅保留以下 6 条主轴作为 1.0 核心范围：
- Agent
- Workflow
- Knowledge
- Chat / Responses Runtime
- Tasks
- Run / Observability
- ModelHub

Workspace / Settings 作为基础支撑模块纳入 1.0，但不做重平台化扩展。

### 约束 6：历史遗留概念不得继续扩张
以下概念仅允许清理、兼容、下线或收敛，不允许继续扩张为主线模块：
- Bot
- AppCenter
- PluginMarket
- Store
- Safe 独立控制台
- Dataset 旧语义

### 约束 7：先面向“真实用户可用”，再面向“平台完整度”
所有设计与实现判断，以“首批真实用户是否能顺利用起来”为优先，而不是以“看起来模块是否完整”为优先。

---

## 三、1.0 研发原则

### 1. 只做主轴，不再发散
当前 1.0 阶段只保留：
- Agents
- Workflows
- Knowledge
- Chat
- Tasks
- Runs
- Models
- Settings
- Dashboard（轻量）

### 2. 页面不是目标，闭环才是目标
每个模块至少满足：
- 可创建
- 可编辑
- 可发布/启用
- 可执行/使用
- 可查看结果
- 可定位问题

### 3. 前后端统一围绕真实对象收敛
1.0 统一围绕以下平台对象建设：
- Workspace
- Model Provider / Model
- Knowledge / Document / Chunk / Ingest Task
- Agent / Agent Version
- Workflow / Workflow Version
- Thread / Response / Run / Event

---

## 四、P0 任务清单

### P0-1 平台对象与导航收敛
目标：让用户进入系统后看到的是一套清晰、聚焦、可用的平台。

任务：
- 收敛前端一级导航，仅保留 Dashboard / Agents / Workflows / Knowledge / Chat / Tasks / Runs / Models / Settings
- 隐藏或下线 Safe / Store / AppCenter / Bot / PluginMarket 等入口
- 统一 dataset 对外命名为 knowledge
- 将 chat 定义为对话入口，而不是独立业务中心
- 清理前后端无效占位路由、菜单和历史兼容入口
- 提供轻量 Dashboard 展示核心统计和最近运行

验收：
- 用户首次进入后不会被无关模块干扰
- 菜单与后端对象模型一致
- 无明显命名冲突与多概念并存问题

### P0-2 Agent 主链路打通
目标：让用户能真正创建并使用 Agent。

任务：
- 完善 Agent 基础模型：基本信息、系统提示词、默认模型、绑定知识库、绑定工具/MCP、草稿/发布状态
- 明确 Agent Version：编辑版本、发布版本
- 完善 Agent CRUD 与发布接口
- 打通 Agent 运行入口与 Responses Runtime
- 增加依赖校验：模型、知识库、工具是否可用
- 完成 Agent 列表/创建/编辑/详情页
- 提供“在 Chat 中使用该 Agent”入口
- 提供发布、查看最近运行结果入口

验收：
- 用户可创建 Agent
- 可绑定模型与知识库
- 可发布 Agent
- 可在 Chat 中调用 Agent 并返回结果

### P0-3 Knowledge 主链路打通
目标：让知识库真正可上传、索引、被调用。

任务：
- 完善 Knowledge / Document / Chunk / Ingest Task 数据模型
- 打通 uploaded / parsing / chunking / embedding / indexed / failed 状态流转
- 提供 ingest task 查询接口
- 统一重建索引、重新切块、删除文档逻辑
- 提供 query 测试接口
- 提供 Knowledge 与 Agent / Workflow 的引用关系接口
- 完成 Knowledge 列表/详情页
- 完成文档上传、状态展示、失败重试、query 测试页

验收：
- 用户可创建知识库
- 可上传文档并看到处理进度
- Agent 可引用该知识库
- 失败文档支持重试

### P0-4 Chat / Responses Runtime 打通
目标：让对话成为 Agent 的真实使用入口。

任务：
- 统一 Thread / Response / SSE 事件流接口
- 明确 Response 生命周期：created / streaming / completed / failed / cancelled
- 统一 tool call、检索、模型响应事件结构
- 增加失败原因、取消原因字段
- 打通 Agent → Response → Run 关联
- 聊天页支持选择 Agent、创建 Thread、SSE 流式输出、中断生成、消息历史
- 支持普通回复、检索中、工具调用中、错误提示等基础事件可视化
- 支持历史线程查看

验收：
- 用户可选择 Agent 发起会话
- 结果支持流式展示
- 会话失败能看到原因
- 会话结果能关联到运行记录

### P0-5 Workflow 主链路打通
目标：让 Workflow 成为 1.0 的第二条核心使用链路。

任务：
- 统一 workflow DSL / schema
- 完善 Workflow CRUD、版本、发布接口
- 完成 workflow 执行入口
- 完善运行时节点事件记录
- 支持最小可用节点集：Start / LLM / Knowledge Retrieve / Code / Transform / Condition / End
- 完成 Workflow 列表页、Builder 基础能力、发布、运行测试、结果查看
- 提供草稿与已发布版本展示

验收：
- 用户可创建 Workflow
- 可配置基本节点并保存
- 可发布 Workflow
- 可运行并看到结果

### P0-6 Runs / Observability 最小闭环
目标：让平台具备基础排障能力。

任务：
- 统一 Run 数据模型
- 提供 run list / run detail / run events 接口
- 记录对象类型：agent / workflow / response
- 记录运行状态：queued / running / completed / failed / cancelled
- 记录错误信息、耗时、模型调用、工具调用摘要
- 完成 Runs 列表页与详情页
- 支持按对象类型、状态、时间筛选
- 提供从 Agent / Workflow / Chat 跳转至 Run 详情

验收：
- 用户可看到最近运行记录
- 失败任务可看到失败位置与错误原因
- 各主轴都能关联到 Run 详情

### P0-7 ModelHub 可用化
目标：让模型管理真正支撑主链路。

任务：
- 完善 Provider 管理接口
- 稳定 Model 列表同步/注册逻辑
- 提供模型可用性校验
- 支持默认模型配置
- 标准化模型调用失败信息
- 完成 Providers / Models 页面
- 支持新增 Provider、配置 API Key、测试连接、查看模型列表、启用/禁用模型、设置默认模型

验收：
- 平台至少支持 2 类主流模型源
- Agent / Workflow / Chat 可稳定引用模型
- 模型异常时前端能给出明确提示

### P0-8 Workspace / Settings 基础可用
目标：提供 1.0 必要的基础配置能力。

任务：
- Workspace 基础信息页
- API Key / Secret 基础配置
- 成员与角色最小实现
- 个人设置基础页
- 系统默认配置页：默认模型、文件上传限制、索引配置（如适用）

验收：
- 单租户或基础多租户可用
- 至少具备 admin / member 两级角色
- 基础配置能被主链路正常引用

---

## 五、P1 任务清单

### P1-1 Agent 能力增强
- Agent 版本历史
- Agent 发布回滚
- Agent 调试模式
- Agent 工具细粒度配置
- Agent 模板化

### P1-2 Workflow 能力增强
- 更多节点类型
- Workflow 调试断点
- Replay / Retry
- 输入输出映射可视化
- Workflow 模板

### P1-3 Knowledge 能力增强
- 切块策略配置化
- 检索参数配置化
- 召回测试对比
- 文档标签、目录、权限控制
- 引用统计与成本分析

### P1-4 Plugin / MCP 接入
- MCP Server 管理页
- Tool Catalog 展示页
- Agent / Workflow 绑定 MCP 工具
- 插件安装与启停
- 凭证绑定与调用审计

### P1-5 安全与审计补强
- 审计日志
- Egress Policy
- 模型 / 工具 / 知识库引用权限
- Secrets 引用分析

### P1-6 运营与引导能力
- 新手引导
- 示例 Agent / Workflow
- 空状态页面优化
- Demo Workspace 初始化数据

---

## 六、P2 任务清单（暂缓）

以下内容不进入 1.0 核心范围：
- Store / Marketplace
- Safe 独立大控制台
- Memory 产品化
- 复杂计费系统
- 高级多组织管理
- 大量运营图表页
- 历史兼容层的大范围包装

---

## 七、推荐研发顺序

### 第一阶段：让平台能对话、能跑知识库
1. ModelHub 可用化
2. Knowledge 主链路打通
3. Agent 主链路打通
4. Chat / Responses Runtime 打通
5. Tasks 主链路打通
6. Run 详情页最小可用

阶段结果：
- 配模型
- 建知识库
- 建 Agent
- 用 Agent 对话
- 看运行记录

### 第二阶段：补 Workflow 主线
1. Workflow DSL / schema 统一
2. Workflow Builder 最小可用
3. Workflow 发布
4. Workflow 执行
5. Workflow Run 详情

阶段结果：
平台从问答平台升级为 Agent + Workflow 平台。

### 第三阶段：补基础平台能力
1. Settings / Workspace 权限基础
2. Plugin / MCP 接入
3. Secrets / Security 基础治理
4. Demo 模板与引导体验

阶段结果：
平台具备初步扩展性和交付友好性。

---

## 八、1.0 验收标准

### Agent 场景
- 能创建 Agent
- 能绑定模型和知识库
- 能发布
- 能在 Chat 中调用
- 能看到运行记录

### Knowledge 场景
- 能创建知识库
- 能上传文档
- 能看到处理状态
- 能用于 Agent 问答
- 失败可重试

### Workflow 场景
- 能创建 Workflow
- 能配置基本节点
- 能发布
- 能执行
- 能查看运行结果

### 平台能力
- 能配置模型
- 能看运行日志
- 能定位基础错误
- 有基础 Workspace / Settings

---

## 九、执行结论

SOIT 1.0 的关键不是继续扩模块，而是把平台从“模块很多的在建平台”收敛成“用户能真实完成任务的平台”。

所有研发任务必须先回答一个问题：

**它是否直接提升 Agent / Workflow / Knowledge / Runtime 的可用闭环？**

如果不能直接提升，应降级到 P1 / P2，而不是抢占 1.0 的 P0 资源。
