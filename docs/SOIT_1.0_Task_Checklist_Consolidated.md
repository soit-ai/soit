# SOIT 1.0 Consolidated Task Checklist

## Purpose

本清单基于以下材料整理：
- `docs/SOIT_1.0_RnD_Task_List_v1.md`
- `docs/SOIT_1.0_Task/` 下 9 份阶段计划

目标是将 SOIT 1.0 的范围、优先级、阶段顺序、验收口径整理为一份可直接执行的任务清单。

## 1.0 Core Goal

SOIT 1.0 只聚焦两条核心链路：

### Core Chain A
Create Knowledge -> Upload and index documents -> Create Agent -> Bind model, knowledge, tools -> Start chat or run task -> View results and logs

### Core Chain B
Create Workflow -> Configure nodes -> Publish -> Execute -> View run records and results

1.0 的判断标准不是模块是否齐全，而是用户是否能稳定完成以上链路。

## Scope Boundaries

### In Scope
- Dashboard
- Agents
- Workflows
- Knowledge
- Chat / Responses Runtime
- Tasks
- Runs / Observability
- Models / ModelHub
- Workspace / Settings

### Out of Scope for 1.0
- Store / Marketplace
- Safe 独立控制台
- Memory 产品化
- 复杂计费系统
- 高级多组织管理
- 大量运营图表页
- 历史兼容层的大范围包装

## P0 Execution Checklist

### 1. Navigation and Scope Convergence
Source:
- `docs/SOIT_1.0_Task/SOIT_Codex_Phase_1_Navigation_and_Scope_Convergence.md`

Checklist:
- [ ] 审计现有前端一级导航、路由、面包屑、守卫逻辑
- [ ] 一级导航仅保留 Dashboard / Agents / Workflows / Knowledge / Chat / Tasks / Runs / Models / Settings
- [ ] 隐藏或移除 Safe / Store / AppCenter / Bot / PluginMarket 入口
- [ ] 对外统一 `dataset -> knowledge`
- [ ] 将 Chat 收敛为交互入口，而不是独立业务中心
- [ ] 清理死路由、空页面、历史兼容菜单和无效 import
- [ ] Dashboard 简化为核心统计、最近运行、最近失败

Acceptance:
- [ ] 主导航与 1.0 范围一致
- [ ] 没有明显坏链路或残留历史命名

### 2. ModelHub 1.0
Source:
- `docs/SOIT_1.0_Task/SOIT_Codex_Phase_2_ModelHub_1.0.md`

Checklist:
- [ ] 审查并统一 Provider / Model 领域模型
- [ ] 标准化 Provider 创建、更新、连通性测试 API
- [ ] 稳定模型同步或注册流程
- [ ] 增加模型可用性校验与标准错误结构
- [ ] 支持默认模型配置
- [ ] 完成 Providers 页面
- [ ] 完成 Models 页面，支持启用、禁用、默认设置
- [ ] 验证 Agent / Workflow / Chat 均可读取可用模型

Acceptance:
- [ ] 至少支持 2 类主流模型源
- [ ] UI 可测试模型连通性
- [ ] 主链路可稳定选择可用模型

### 3. Knowledge 1.0
Source:
- `docs/SOIT_1.0_Task/SOIT_Codex_Phase_3_Knowledge_1.0.md`

Checklist:
- [ ] 统一 Knowledge / Document / Chunk / Ingest Task 模型
- [ ] 打通 `uploaded -> parsing -> chunking -> embedding -> indexed / failed` 状态流
- [ ] 完成 ingest task 查询接口
- [ ] 支持 retry / re-index / delete document
- [ ] 提供基础 query test 接口
- [ ] 提供 Agent / Workflow 引用关系查询
- [ ] 完成 Knowledge 列表页
- [ ] 完成 Knowledge 详情页，展示文档、状态、计数、处理进度
- [ ] 完成上传流程与进度渲染
- [ ] 为失败文档提供重试能力
- [ ] 完成基础 query test UI

Acceptance:
- [ ] 用户可创建知识库
- [ ] 用户可上传文档并看到处理状态
- [ ] 失败文档可重试
- [ ] 已索引知识库可绑定 Agent

### 4. Agent 1.0
Source:
- `docs/SOIT_1.0_Task/SOIT_Codex_Phase_4_Agent_1.0.md`

Checklist:
- [ ] 统一 Agent 领域模型
- [ ] 明确基础字段：基本信息、提示词、模型绑定、知识库绑定、状态
- [ ] 明确 draft / published 版本语义
- [ ] 完成 Agent CRUD API
- [ ] 完成发布 API 与发布前校验
- [ ] 增加模型、知识库可用性校验
- [ ] 完成 Agent 列表页
- [ ] 完成 Agent 创建 / 编辑页
- [ ] 完成 Agent 详情页，展示配置、绑定关系、发布状态、最近运行
- [ ] 提供“在 Chat 中打开该 Agent”入口
- [ ] 提供最近运行跳转 Runs 能力

Acceptance:
- [ ] 用户可创建 Agent
- [ ] Agent 可绑定模型和知识库
- [ ] Agent 可发布
- [ ] Agent 可在 Chat 中被调用

### 5. Responses Runtime and Chat 1.0
Source:
- `docs/SOIT_1.0_Task/SOIT_Codex_Phase_5_Responses_Runtime_Chat_1.0.md`

Checklist:
- [ ] 统一 Thread / Response API 合约
- [ ] 明确 Response 生命周期：`created / streaming / completed / failed / cancelled`
- [ ] 统一模型输出、检索、工具调用、错误事件结构
- [ ] 增加失败原因、取消原因字段
- [ ] 建立 Agent / Response / Run 关联
- [ ] 完成 Chat 页面 Agent 选择能力
- [ ] 支持 Thread 创建和历史查看
- [ ] 支持 SSE 流式输出与取消
- [ ] 支持基础事件状态可视化
- [ ] 支持从会话查看关联 Run

Acceptance:
- [ ] 用户可选择 Agent 发起会话
- [ ] 流式输出端到端可用
- [ ] 失败状态可见
- [ ] Response 可关联 Run 详情

### 6. Runs and Observability 1.0
Source:
- `docs/SOIT_1.0_Task/SOIT_Codex_Phase_6_Runs_Observability_1.0.md`

Checklist:
- [ ] 统一 Run 数据模型
- [ ] 支持对象类型：`agent / workflow / response`
- [ ] 支持运行状态：`queued / running / completed / failed / cancelled`
- [ ] 补充耗时、模型调用、工具调用、错误摘要字段
- [ ] 完成 run list API 与筛选
- [ ] 完成 run detail API 与事件时间线
- [ ] 完成 Runs 列表页
- [ ] 完成 Run 详情页，展示摘要、时间线、失败信息
- [ ] 从 Agent / Workflow / Chat 提供 Run 跳转

Acceptance:
- [ ] 用户可查看最近运行记录
- [ ] 失败运行可查看错误原因和失败位置
- [ ] Agent / Workflow / Chat 均可跳转关联 Run

### 7. Workflow 1.0
Source:
- `docs/SOIT_1.0_Task/SOIT_Codex_Phase_7_Workflow_1.0.md`

Checklist:
- [ ] 统一 Workflow schema / DSL
- [ ] 完成 Workflow CRUD 与发布 API
- [ ] 打通 Workflow 执行入口
- [ ] 补齐节点级运行事件记录
- [ ] 节点集限制为 Start / LLM / Knowledge Retrieve / Code or Transform / Condition / End
- [ ] 完成 Workflow 列表页
- [ ] 完成 Builder 最小能力：拖拽、连线、配置、保存
- [ ] 完成发布动作
- [ ] 完成测试运行动作
- [ ] 支持结果查看和跳转 Runs
- [ ] 展示草稿版与发布版状态

Acceptance:
- [ ] 用户可创建 Workflow
- [ ] 用户可配置最小节点集
- [ ] 用户可发布并执行 Workflow
- [ ] 用户可查看 Workflow 运行结果

### 8. Workspace and Settings 1.0
Source:
- `docs/SOIT_1.0_Task/SOIT_Codex_Phase_8_Workspace_Settings_1.0.md`

Checklist:
- [ ] 审查 Workspace / Settings 领域模型
- [ ] 完成 Workspace 基础信息页
- [ ] 完成 Secrets / API Key 基础配置页
- [ ] 实现最小角色：`admin / member`
- [ ] 若数据模型已存在，补齐基础成员管理
- [ ] 增加默认模型、上传限制、关键运行配置
- [ ] 验证主链路可正确读取默认配置

Acceptance:
- [ ] Admin 可配置工作空间基础信息
- [ ] 平台具备最小角色区分
- [ ] 主链路可读取默认配置并正常工作

### 9. Stabilization and Release Gate
Source:
- `docs/SOIT_1.0_Task/SOIT_Codex_Phase_9_1.0_Stabilization_and_Release_Gate.md`

Checklist:
- [ ] 联调验证 `ModelHub -> Knowledge -> Agent -> Chat -> Runs`
- [ ] 联调验证 `Workflow -> Execute -> Runs`
- [ ] 修复坏链路、缺失状态、加载异常、明显 UI 不一致
- [ ] 统一核心页面空态、加载态、错误态、重试态
- [ ] 验证 Agent / Workflow 发布流程
- [ ] 验证文档 ingest 和运行时失败可见性
- [ ] 复核导航一致性
- [ ] 产出 1.0 release checklist
- [ ] 产出 known limitations / deferred backlog

Acceptance:
- [ ] 核心链路通过手工端到端验证
- [ ] 不存在阻断主链路的坏路由或不可用页面
- [ ] 主要失败场景可见且可处理
- [ ] 延后项被明确记录，而不是半成品落地

## Missing Item to Resolve

在总纲文档中，`Tasks` 被列为 1.0 主轴之一，并出现在推荐研发顺序中，但当前：
- 没有单独的 `P0-Tasks` 小节
- `docs/SOIT_1.0_Task/` 中没有对应阶段文档

建议在正式排期前补齐以下决策，避免范围口径不一致：
- [ ] 明确 `Tasks` 是否是独立模块，还是 `Runs` / 异步任务的视图层
- [ ] 明确 `Tasks` 与 Knowledge ingest、Workflow execute、Response run 的关系
- [ ] 明确是否需要独立页面、筛选项、详情页和操作能力
- [ ] 如果 1.0 不单独建设 `Tasks`，应在总纲中移出主轴表述或合并到 `Runs`

## Recommended Execution Order

基于总纲中的推荐顺序，以及 9 份阶段计划的依赖关系，建议按以下顺序推进：

1. Navigation and Scope Convergence
2. ModelHub 1.0
3. Knowledge 1.0
4. Agent 1.0
5. Responses Runtime and Chat 1.0
6. Resolve `Tasks` scope gap
7. Runs and Observability 1.0
8. Workflow 1.0
9. Workspace and Settings 1.0
10. Stabilization and Release Gate

## P1 Backlog

- Agent version history / rollback / debug / template
- Workflow more node types / breakpoint / replay / retry / template
- Knowledge chunk and retrieval strategy configuration
- MCP server management / tool catalog / plugin install / credential binding
- Audit log / egress policy / permissions / secret reference governance
- Onboarding / sample Agent and Workflow / empty-state polish / demo workspace data

## P2 Deferred

- Store / Marketplace
- Safe 独立大控制台
- Memory 产品化
- 复杂计费系统
- 高级多组织管理
- 大量运营图表页
- 大范围历史兼容包装

## 1.0 Release Criteria

- [ ] 能配置模型
- [ ] 能创建知识库并上传文档
- [ ] 能创建并发布 Agent
- [ ] 能在 Chat 中调用 Agent
- [ ] 能创建、发布、执行 Workflow
- [ ] 能查看 Runs 和错误信息
- [ ] 有基础 Workspace / Settings
- [ ] 首批真实用户可在不依赖隐藏入口和历史模块的前提下完成核心任务
