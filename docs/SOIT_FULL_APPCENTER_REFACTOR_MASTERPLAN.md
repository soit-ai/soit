# SOIT 全量改造总计划（统一 AppCenter：apps/app_versions + refs + components 投影）

> 目标：把 SOIT 平台所有“可交付的产品形态（workflow/chat/bot/agent/未来类型）”统一到 **AppCenter** 的 `apps/app_versions` 体系；  
> - **canonical 真相**：`app_versions.spec_json`（不可变发布版本）  
> - **依赖索引**：`app_version_refs`（只存外部依赖：tool/dataset/model/plugin/secret/app）  
> - **组件图投影**：`app_components/app_component_edges`（发布时生成；workflow 必做；chat/bot 可选；未来 pipeline/agent 可复用）  
> - **执行统一**：Run/Step/Artifact/Cost 必须绑定 `app_id/app_version_id`  
> - **前端不改**：保留现有 API 契约，仅后端实现切换（除非你明确允许前端同步调整）

---

## 0. 已覆盖（你已要求并已有清单的部分）
- ✅ Workflow → AppCenter（spec_json 为真相 + components/edges 投影 + refs）
- ✅ Chat/Bot → AppCenter（spec_json + refs；components 可选）

> 本总计划重点：**除了 workflow/chat/bot 以外，平台还需要改造哪些地方**，以及如何一次性“彻底统一”。

---

## 1. 改造范围全景（需要纳入的所有模块/能力）

### A. 应用形态（必须纳入 apps/app_versions）
- [ ] **Agent**（执行型智能体）
- [ ] **App（独立应用）/Pipeline（编排管道）**（未来扩展类型，先把框架占位）
- [ ] **Tool App / Integration App**（可选：把“工具集合/集成连接器”也作为 app 形态管理）

### B. 平台基础设施（必须对齐 app 体系）
- [ ] **执行路由与运行归属**：AppRuntimeRouter + Run 绑定 app/version
- [ ] **发布管线**：validate + checksum + refs + projections 的统一 publish pipeline
- [ ] **权限与多租户**：tenant/workspace + app 级 ACL
- [ ] **插件系统**：插件安装与启用状态必须影响 app_version_refs 的预检
- [ ] **Secrets/Vault**：secret 引用与注入规范，refs 可追踪
- [ ] **ModelHub/Providers**：模型引用规范化（ref_key），成本核算一致
- [ ] **Dataset/RAG**：dataset 引用纳入 refs，删除前检查
- [ ] **事件与调度**：bot schedule/event 触发、workflow 定时触发、agent cron 等
- [ ] **观测与成本**：Run/Step/Cost API 按 app 聚合、可定位错误
- [ ] **导入导出与分享**：app_version spec 可导出/导入/复制/回滚
- [ ] **测试、文档、脚本**：smoke/contract tests、projection rebuild、release checklist

---

## 2. 统一“类型扩展”策略（避免巨石表）

> 统一模型不是把所有字段塞进 apps/app_versions，而是把差异放在 spec_json，并用投影/refs支持平台能力。

- `apps`：生命周期 + 权限 + 元数据（type/kind/name/status/visibility/current_version_id）
- `app_versions`：版本化配置（spec_schema/spec_json/status/checksum）
- `app_version_refs`：外部依赖（tool/dataset/model/plugin/secret/app）
- `app_components/app_component_edges`：可选的“结构投影”（workflow 必做；其他类型按需）
- 运行记录（session/message、webhook logs、delivery logs）属于运行态，不属于 app 定义，但必须绑定 app_id/version_id/run_id

---

## 3. 全量改造清单（按模块逐项列出）

---

# 3.1 Agent 改造到 AppCenter（必做）

## A1. 定义 agent.v1 spec + schema
- [ ] 新增 `kernel/specs/apps/v1/agent.v1.schema.json`
- [ ] spec 建议字段：
  - `runtime`: `"agent_runtime_v1"`
  - `planner`: `{ type, params }`（如 react/plan-and-execute）
  - `model`: `ref_key` 或 `{provider, model, params}`
  - `tools`: allowlist + tool configs
  - `memory`: long/short memory 策略（可选）
  - `rag`: datasets + retrieval params（可选）
  - `limits`: max_iterations/max_tool_calls/timeout/budget
  - `policies`: safety/guardrails（可选）
- [ ] 发布时强校验

## A2. AgentRefExtractor（生成 app_version_refs）
- [ ] 提取 model/tool/dataset/secret/plugin/app 引用 + spec_path

## A3. AgentExecutorV1（走统一执行路由）
- [ ] `AgentExecutorV1.execute()` 读取 agent.v1 spec_json
- [ ] 迭代执行写 Step：
  - `plan`
  - `tool.call.*`
  - `llm.generate.*`
  - `finalize`
- [ ] Run/Step/Cost 绑定 app/version

## A4. Agent API Facade（前端不改）
- [ ] create/update/publish/execute 映射到 apps/app_versions + publish pipeline

**DoD**
- agent 可创建/发布/执行；run 可追踪 steps，成本可查。

---

# 3.2 AppRuntimeRouter 全平台统一（必做）

## R1. Router 路由表（type/schema → executor）
- [ ] 注册：
  - `workflow.v1` → WorkflowExecutorV1
  - `chat.v1` → ChatExecutorV1
  - `bot.v1` → BotExecutorV1
  - `agent.v1` → AgentExecutorV1
  - 未来：`pipeline.v1` 等

## R2. 统一输出协议（ExecutionResult）
- [ ] `{ run_id, status, outputs, artifacts?, warnings? }`
- [ ] 统一错误结构：`error_code/error_message/error_details`

## R3. 执行前预检（PreflightChecker）统一接入
- [ ] 读取 `app_version_refs` 检查：
  - tool 是否存在且启用
  - dataset 是否存在且有权限
  - model 是否允许（ModelHub policy）
  - secret 是否可读取（Vault policy）

---

# 3.3 发布管线统一（必做）

## P1. AppPublishService 标准化
- [ ] `validate(spec_schema, spec_json)`
- [ ] `checksum = sha256(canonical_json(spec_json))`
- [ ] 发布时：
  - draft → published
  - old published → deprecated
  - 更新 `apps.current_version_id`
  - build refs
  - build components/edges（按 schema 分发）
- [ ] 幂等：checksum 不变不重复生成；投影可重建

## P2. ProjectionBuilder 分发
- [ ] workflow: components+edges+refs
- [ ] chat: refs（components 可选）
- [ ] bot: refs（components 可选）
- [ ] agent: refs（components 可选：可把 agent 看成“迭代组件图”，不建议前期做）

---

# 3.4 AppCenter 管理能力补齐（必做）

## M1. App CRUD + 过滤检索
- [ ] list apps（type/status/visibility/tags）
- [ ] app detail（含 current/published version 摘要）
- [ ] archive/unarchive
- [ ] copy app（生成新 app + draft version）

## M2. Version 管理
- [ ] list versions（分页 + status）
- [ ] set current version（显式回滚/切换）
- [ ] create version from published（fork）
- [ ] delete draft version（可选）
- [ ] compare versions（diff：可先返回 checksum + 简单字段差异）

## M3. 导入导出/分享
- [ ] export app_version spec（json/yaml）
- [ ] import spec → 新建 app + version（支持覆盖/新建策略）
- [ ] share link（public token 可选，后期）

---

# 3.5 Dataset/RAG 对齐 AppRefs（必做）

## D1. DatasetRefExtractor 支持各类型
- [ ] workflow retrieval node
- [ ] chat.rag.datasets
- [ ] agent.rag.datasets
- [ ] bot.chat.rag.datasets

## D2. 删除前检查与影响分析
- [ ] 删除 dataset 前查询 `app_version_refs(ref_type=dataset, ref_id=...)`
- [ ] 提供影响分析 API：`/refs/impact`

## D3. 检索 API 稳定化
- [ ] `query -> top_k chunks`
- [ ] 引用 dataset 的权限校验：tenant/workspace 维度一致

---

# 3.6 Tools / Plugin / Integration Hub 对齐（必做）

## T1. ToolRef 规范
- [ ] 统一 `tool_ref` 为：
  - 内置 tool：`tool_id`
  - 插件 tool：`plugin_id:tool_name` 或 tool_id 映射
- [ ] refs 抽取能定位到具体 tool

## T2. 插件安装/启用状态影响执行
- [ ] app_version_refs 预检时验证 plugin/tool enable 状态
- [ ] 插件升级影响分析：查引用到的 app_versions

## T3. Integration Hub（可选但建议）
- [ ] 把“连接器/集成配置”作为 tool/plugin 的一种
- [ ] secret 引用统一从 Vault 注入（不允许明文）

---

# 3.7 Secrets/Vault 对齐（必做）

## S1. Secret 引用规范（出现在 spec_json 中）
- [ ] 统一 secret 引用形态：`{"secret_ref": "vault://path#key"}` 或 `{secret_id}`
- [ ] refs 抽取 secret 并记录 spec_path

## S2. 注入策略统一
- [ ] tool headers/signature 由 runtime 注入
- [ ] run 日志严禁输出 secret 明文（增加 redaction）

---

# 3.8 ModelHub/Provider 对齐（必做）

## L1. 模型引用统一（ref_key）
- [ ] 建议 `ref_key = "{provider}:{model}"`（如 `openai:gpt-5`）
- [ ] chat/bot/agent/workflow llm node 全部使用同一引用方式

## L2. 成本核算统一
- [ ] `RunCostEntry` 统一落：tokens、unit_price、amount、currency
- [ ] ModelHub 提供单价配置与禁用策略（按 workspace/tenant）

---

# 3.9 运行记录与业务数据对齐（必做）

> 运行记录（不是 app 定义）必须能追溯到 app/version/run

## H1. Chat Session/Message
- [ ] session 绑定 `app_id`
- [ ] message 绑定 `run_id`（强烈建议）
- [ ] 回放：从 run/steps 还原（可选）

## H2. Bot Trigger/Delivery Logs
- [ ] webhook 收到的 payload 落 `bot_events`（运行记录表）
- [ ] delivery 结果落 `bot_deliveries`
- [ ] 均绑定 `app_id/app_version_id/run_id`

## H3. Workflow Run Records
- [ ] run/step 的 external_id 统一用 node_id
- [ ] artifacts 指向 minio keys（不保存大 JSON 到 db）

---

# 3.10 事件总线与调度（P1/P2，但应规划）

## E1. Scheduler
- [ ] 支持 bot.schedule、workflow schedule、agent cron
- [ ] 定义统一 TriggerSpec（可作为 bot.v1 / workflow.v1 扩展字段）

## E2. Event Bus
- [ ] 内存模式（dev）
- [ ] Redis stream/pubsub（prod）
- [ ] event → 触发 app 执行（生成 run）

---

# 3.11 Observability 对齐（必做）

## O1. Runs API 能按 app 维度聚合
- [ ] list runs filter：tenant/workspace/app_id/app_type/date
- [ ] run detail：steps/artifacts/costs
- [ ] cost 聚合：按 app/version/model

## O2. SSE/Streaming
- [ ] 执行过程推送 step 状态，包含 app_id/version_id/run_id

---

# 3.12 删除旧模型与代码清理（清库重建必做）

## C1. 删除旧“定义类”表/模型/服务
- [ ] workflow_def / workflow_versions（如果仍存在）
- [ ] chat_presets（若已迁移到 apps/app_versions 则删除）
- [ ] bot_def（若存在）
- [ ] agent_def（若存在）

## C2. 仅保留运行记录表
- [ ] session/message、deliveries、events 等运行态表保留

---

# 3.13 工程化：测试/脚本/文档（必做）

## Q1. Projection Rebuild 脚本（统一）
- [ ] `scripts/rebuild_projections.py` 支持 workflow/chat/bot/agent
- [ ] 支持全量 rebuild（按 tenant/workspace）

## Q2. Contract Tests（基于前端 services）
- [ ] 提取 `web/src/services/*` → 生成契约
- [ ] workflow/chat/bot 关键 endpoints 回归

## Q3. Smoke Tests（compose 一键）
- [ ] 启动后轮询 health ready
- [ ] demo：create workflow -> publish -> run
- [ ] demo：create chat -> publish -> send message
- [ ] demo：create bot -> publish -> execute (manual)
- [ ] demo：create agent -> publish -> execute

## Q4. 文档
- [ ] SPEC_GUIDE：workflow/chat/bot/agent spec
- [ ] RUN_GUIDE：compose/环境变量/默认账号
- [ ] MIGRATION_GUIDE（即使清库也要说明）

---

## 4. 分阶段实施顺序（建议里程碑）

### Milestone A（P0：统一底座）
- apps/app_versions 强化（checksum + publish 不可变）
- app_version_refs + publish pipeline + refs extractor（workflow/chat/bot/agent）
- AppRuntimeRouter + Run 绑定 app/version
- Workflow/Chat/Bot/Agent API facade 接入
- smoke tests 跑通

### Milestone B（P1：查询/影响分析/预检）
- 影响分析 API（refs/impact）
- PreflightChecker（缺依赖提前失败）
- AppCenter 管理能力补齐（版本切换/复制/导入导出）

### Milestone C（P2：生态与工程化）
- Scheduler/EventBus（bot/workflow/agent 触发）
- Node Catalog 统一（插件节点）
- 全量 contract tests + CI
- 删除旧代码与模块清理

---

## 5. 最终交付验收清单（总）
- [ ] workflow/chat/bot/agent 的定义全部在 `apps/app_versions`（无独立定义表）
- [ ] publish 生成 `checksum + refs +（workflow 必有 components/edges）`
- [ ] execute 全部走 AppRuntimeRouter，run/step/cost 可追溯 app/version
- [ ] 资源变更前可做影响分析（tool/dataset/model/plugin/secret）
- [ ] 前端无需改动，核心页面可用（workflow/chat）
- [ ] 可重建：refs/components/edges 可从 spec_json 一键 rebuild
- [ ] 清库重建 baseline 迁移稳定（compose 一键）

---
