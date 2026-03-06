# SOIT 后端清库重建重构开发清单（基于最新代码｜统一 Apps / AppVersions｜前端不改）

> 输入：你提供的最新 `soit-pro.zip`（后端 `app/` + 前端 `web/`）。  
> 要求：**不考虑数据迁移，直接清库重建**；后端统一为 `apps` / `app_versions`；**前端不做任何重构**（沿用现有 `/api/v1/workflow/*`、`/api/v1/chat/*` 等接口与字段契约）。  
> 结果：新环境 `docker compose up -d` 后即可登录使用；workflow/chat 页面正常；执行统一落 `Run/Step/Cost`。

---

## 1. 当前代码基线要点（你仓库现状）

- 后端目录：`app/app/`
- 业务模块：`app/app/modules/{workflow,chat,bot,agent,appcenter,...}`
- 已存在 AppCenter 模型：`app/app/modules/appcenter/domain/models.py`
  - 已定义 `App`（__tablename__ = `apps`）
  - 已定义 `AppVersion`（__tablename__ = `app_versions`）
- 现有 Run 表已含 `app_version_id`（`20250101000000_kernel_v1_tables.py`），但目前语义未统一，且缺少 `app_id`。
- Workflow / Chat 都有独立表迁移文件（`20250101000001_workflow_tables.py`、`20250101000003_chat_tables.py` 等）。

> **重构策略**：复用并升级 `modules/appcenter` 的 `apps/app_versions`，让它成为唯一“定义类”主模型；保留 Chat 的 session/message 等“运行记录类”表（如已存在），但将其与 `app_id` 关联。

---

## 2. 目标交付标准（Run-ready DoD）

### 平台级
- [ ] 清库后首次启动：自动完成 alembic migrate + bootstrap（默认 tenant/workspace/admin）。
- [ ] `apps/app_versions` 成为 workflow/chat/bot/agent 的唯一配置来源。
- [ ] 任意执行必须写 Run/Step/Cost，并绑定 `app_id/app_version_id`。
- [ ] SSE 监控页（workflow monitor）不需要改前端即可看到 step 状态变化（沿用现有事件机制）。

### 业务闭环（必须过）
- [ ] Workflow：build → publish → run → monitor/log → retry（前端页面不改）
- [ ] Chat：对话正常（若前端 chat 页面当前在用），run/cost 可查
- [ ] Dataset（如你当前交付范围包含 RAG）：upload → ingest worker → search（保持现状即可）

---

## 3. 清库重建方案（强制、无迁移）

> 你有两种方式，建议选 **A**（更干净、更符合“强制重构”）。

### A) 重置 Alembic 为单一 Baseline（推荐）
- 删除历史 migration（`app/alembic/versions/*.py`）并新建一个 baseline migration：
  - 创建“保留表”（kernel/run/identity/dataset 等你仍要用）
  - 创建/升级 `apps/app_versions` 为新结构
  - 不创建旧 workflow/chat/bot/agent 定义表
- 清空数据库后直接 `alembic upgrade head`

### B) 保留历史 migration，新增终局 Migration（不推荐）
- 追加一个“终局迁移”：先 drop 旧表再 create 新表  
- 缺点：升级链路会先 create 一堆旧表再 drop，时间浪费且易引入依赖问题

---

## 4. 开发清单（按 P0/P1/P2 优先级）

### P0（必须完成：让前端不改也能跑通 workflow）

#### P0-01 升级 AppCenter 的数据模型为“统一 App 定义模型”
**文件**：`app/app/modules/appcenter/domain/models.py`

- [ ] `App` 增加字段：
  - `type`：`WORKFLOW | CHAT | BOT | AGENT`
  - `status`：`active | archived`
  - `visibility`（可选）：`private | workspace | public`
  - （保留）`current_version_id`
- [ ] `AppVersion` 重构字段（把 “market manifest” 变成 “runtime spec”）：
  - `version`：建议改为 `int`（自增）或保留 string 但统一语义
  - `status`：`draft | published | deprecated`
  - `spec_schema`：`workflow.v1 | chat.v1 | bot.v1 | agent.v1`
  - `spec_json`：JSONB（由旧 `manifest_json` 改名或复用）
  - 删除/废弃：`workflow_version_id`（不再指向旧 workflow_versions 表）
- [ ] 约束与索引：
  - `unique(app_id, version)`
  - `index(app_id, status)`

**DoD**
- 仅靠 `apps/app_versions` 就能表示 workflow/chat/bot/agent 的定义与版本。

---

#### P0-02 新增/调整 Spec Schema（复用现有 specs）
**目录现状**：`app/app/kernel/specs/v1/` 已有 `workflow_spec.schema.json`、`app_spec.schema.json`

- [ ] 以现有 schema 为基础定义统一 spec_schema：
  - `workflow.v1` → 对应 `workflow_spec.schema.json`
  - 新增 `chat_spec.schema.json`（生成 `chat.v1`）
  - 新增 `bot_spec.schema.json`（生成 `bot.v1`，可先继承 chat 字段 + trigger 占位）
  - 新增 `agent_spec.schema.json`（生成 `agent.v1`，可先最小 planner/executor 占位）
- [ ] 新增校验器：`app/app/kernel/specs/validator.py`
  - `validate(spec_schema, spec_json)`：发布时强校验，失败返回 422 + path/message

**DoD**
- 发布 app_version 时必校验通过；错误可定位字段路径。

---

#### P0-03 Run 绑定 App（app_id/app_version_id 必填）
**现状**：`runs` 已含 `app_version_id`（nullable），缺少 `app_id`

- [ ] 修改 Run 模型（按你实际位置，一般在 `app/app/kernel/trace/*` 或 run 模块）
  - 增加 `app_id`（必填）
  - `app_version_id` 改为必填（不再 nullable）
  - （可选冗余）`app_type`
- [ ] 更新相关索引：`(tenant_id, workspace_id, app_id, started_at)`

**DoD**
- 任意执行都能通过 run 追溯到 app/version。

---

#### P0-04 新增统一执行路由：AppRuntimeRouter
**新增文件**：`app/app/kernel/execution/app_runtime_router.py`（当前目录存在 `kernel/execution/`）

- [ ] `execute(app_id, version_id|use_current, inputs) -> run_id, outputs`
- [ ] 依据 `App.type + AppVersion.spec_schema` 路由到 executor
- [ ] 全链路写入：
  - Run（start/end/status）
  - Step（workflow 节点、chat 生成、tool 调用等）
  - Cost（模型 token、工具消耗等，复用现有 cost writer）

**DoD**
- router 能跑通 workflow，并能在 Runs 页面看到 step/cost。

---

#### P0-05 WorkflowExecutorV1：从 AppVersion.spec_json 取 WorkflowSpec
**复用路径**：`app/app/modules/workflow/runtime/`（现有 `engine.py/executor.py/executors/`）

- [ ] 改造 workflow 执行入口：输入不再来自 workflow 表，而来自：
  - `AppVersion.spec_json`（校验后视为 WorkflowSpec）
- [ ] 每节点写 Step（node_id/status/error_details）
- [ ] 支持 retry/replay（复用现有 API 语义）

**DoD**
- 一个 5 节点示例 workflow：build→publish→run→monitor/log 全链通过。

---

#### P0-06 Workflow API Facade：接口不变，内部改走 apps/app_versions
**文件**：`app/app/api/v1/workflow/handlers.py`（现状依赖 `WorkflowService`）

- [ ] 替换 `WorkflowService` 的实现（或新增 `WorkflowAppFacadeService`）：
  - create_workflow → create `App(type=WORKFLOW)` + create draft `AppVersion(spec_schema=workflow.v1)`
  - update_workflow/build → 更新 draft 版本 spec_json（或新建 draft + 指针）
  - list_versions → 读 app_versions 并适配前端旧字段（version/status/created_at 等）
  - publish_version → 设置 `apps.current_version_id`
  - run/retry/replay → 调 `AppRuntimeRouter.execute(...)`
- [ ] 返回结构保持前端需要的字段（**字段名不改**）

**DoD**
- 前端 workflow 页无改动可用：build/log/monitor/publish/setting 全绿。

---

#### P0-07 Alembic Baseline（清库后一次升级到位）
**目录**：`app/alembic/versions/`

- [ ] 执行“方案 A：重置为 baseline”：
  - 删除旧 migration 文件
  - 新建 `YYYYMMDDHHMMSS_baseline_apps.py`
  - 在 baseline 中：
    - 创建必须保留的 kernel/identity/dataset/run 表
    - 创建升级后的 `apps/app_versions`（新结构）
    - **不创建旧 workflow/workflow_versions 定义表**
- [ ] 更新 `app/alembic/env.py` 确保 metadata 指向当前模型集合

**DoD**
- 清库后 `alembic upgrade head` 成功；数据库只包含新结构需要的表。

---

#### P0-08 一键启动：migrate + bootstrap
**目录**：`app/docker-compose.yml` + `app/scripts/`

- [ ] `migrate` 一次性 job：`alembic upgrade head`
- [ ] `bootstrap` 一次性 job：
  - 创建默认 tenant/workspace/admin（幂等）
- [ ] API/worker 依赖健康检查后启动（postgres/redis/minio/milvus/vault）

**DoD**
- 新环境 `docker compose up -d` 后可直接登录并运行 workflow demo。

---

### P1（让 chat/bot/agent 也纳入 apps 统一模型；仍不改前端）

#### P1-01 Chat 配置从 AppVersion.spec_json 获取（chat.v1）
- [ ] 设计 `chat.v1` spec（system_prompt/model/tools/rag/limits）
- [ ] 在 `modules/chat` 中新增/重构 “ChatConfigProvider”：
  - 从 `apps.current_version_id` → `app_versions.spec_json` 读取配置
- [ ] 执行链路写 Run/Step/Cost

**DoD**
- 任意 chat 对话的 run 归属到某个 chat app/version。

---

#### P1-02 Chat API Facade（接口不变）
**目录**：`app/app/api/v1/chat/*`

- [ ] 若前端存在“chat 配置/预设”接口：
  - create chat preset → create `App(type=CHAT)` + draft version（chat.v1）
  - publish → 设置 current_version_id
- [ ] session/message 仍作为“运行记录表”保留（不属于 apps 定义），但需要：
  - session 增加 `app_id` 以便归档与检索

**DoD**
- 前端 chat 无改动可用；会话不丢；run/cost 可查。

---

#### P1-03 Bot/Agent 最小纳入（若前端暂未使用，可先只做 CRUD）
- [ ] `App(type=BOT/AGENT)` 创建 + draft version + publish
- [ ] executor 可先占位（返回 501 或 simple echo），但 schema/版本要完整

**DoD**
- 后端统一模型可扩展；不会阻塞 workflow/chat 交付。

---

### P2（质量保障与清理）

#### P2-01 Contract Tests（用前端 services 作为契约来源）
- [ ] 从 `web/src/services/*` 生成 endpoint 契约清单（请求/响应字段）
- [ ] 为 workflow/chat 关键接口写回归测试（字段级断言）

#### P2-02 Smoke Tests（发布必过）
- [ ] Demo-1：workflow build→publish→run→monitor/log→retry
- [ ] Demo-2：chat 对话（如在交付范围）
- [ ] Demo-3：secrets 注入工具调用（若交付范围包含 tools）

#### P2-03 删除旧定义模块残留
- [ ] 删除旧 workflow/chat/bot/agent 定义表相关 ORM、repo、migration
- [ ] 仅保留 runtime 与 façade 所需代码

---

## 5. 建议实现顺序（最少返工）

1) P0-01~P0-03：升级 apps/app_versions + run 绑定  
2) P0-02：spec schema + validator（先 workflow）  
3) P0-04~P0-06：router + workflow executor + workflow façade（确保前端 workflow 全绿）  
4) P0-07~P0-08：baseline migration + compose 一键启动  
5) P1：chat 纳入 apps（不影响 workflow 交付）  
6) P2：contract/smoke + 清理

---

## 6. 发布验收（Release Checklist）
- [ ] 数据库清空后 `alembic upgrade head` 一次成功
- [ ] `apps/app_versions` 为唯一配置来源（无 workflow_versions 等定义表）
- [ ] 前端 workflow 页面不改能跑通全链
- [ ] Run 绑定 app/app_version，cost 可聚合查询
- [ ]（如适用）前端 chat 页面不改可对话，session 绑定 app_id

---
