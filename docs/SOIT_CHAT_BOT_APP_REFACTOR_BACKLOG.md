# SOIT：Chat/Bot 统一纳入 AppCenter 的后端改造开发清单（与 Workflow 同一模型）

> 目标：在既定“最优建议”基础上，把 **Chat** 和 **Bot** 也完全改造到 `apps/app_versions` 统一模型中：  
> - **canonical 真相**：`app_versions.spec_json`（chat/bot 版本完整配置）  
> - **通用组件图投影（可选）**：`app_components/app_component_edges`（仅当你希望把 chat/bot 也表示成“可编排组件图”时启用；否则可以只用 refs）  
> - **外部引用索引**：`app_version_refs`（model/tool/dataset/plugin/secret/app 等）  
> - **前端不改**：保留现有 `/chat/*`、`/bot/*` API（若前端在用），内部改为 AppCenter + publish pipeline

> 注意：本清单默认你已按上一份 backlog 完成：  
> - `app_versions.checksum`、`app_version_refs`、`app_components/app_component_edges`、`AppPublishService`、`SpecValidator`、`WorkflowProjectionBuilder` 等基础设施已经存在。

---

## 0. 统一原则（对齐 Workflow）

- **所有类型的“定义/配置”都只存在于 `app_versions.spec_json`**
- **所有类型的“外部依赖”都抽取到 `app_version_refs`**
- **发布是唯一稳定态**：draft 可频繁改；published 不可变；执行默认指向 published/current
- **执行链路统一落 `Run/Step/Cost`，并绑定 `app_id/app_version_id`**
- **前端 API 契约不变**：只做后端内部替换

---

## 1. Spec 规范与 JSON Schema（P0）

### P0-01 定义 chat.v1 schema（必须）
**新增**：`app/app/kernel/specs/apps/v1/chat.v1.schema.json`

- [ ] `chat.v1` 必须字段建议：
  - `runtime`: `"chat_runtime_v1"`
  - `model`: `{ provider, model, params }`（或 `ref_key: "openai:gpt-5"`）
  - `system_prompt`
  - `tools`: `{ allowlist: [], configs: {} }`（可选）
  - `rag`: `{ datasets: [], top_k, filters, citation }`（可选）
  - `memory`: `{ enabled, type, policy }`（可选）
  - `limits`: `{ max_tokens, timeout_ms, budget }`（可选）
  - `ui`: `{ opening, quick_actions }`（可选，纯展示）
- [ ] 校验器接入：`SpecValidator.validate("chat.v1", spec_json)`

**DoD**
- publish chat 版本时强校验通过；错误回显 path 可定位。

---

### P0-02 定义 bot.v1 schema（必须）
**新增**：`app/app/kernel/specs/apps/v1/bot.v1.schema.json`

- [ ] `bot.v1` 推荐结构（bot 是 chat + triggers/channels 的扩展）：
  - `runtime`: `"bot_runtime_v1"`
  - `chat`: **内嵌 chat.v1 子结构**（或引用 `chat_config`）
  - `triggers`: 
    - `webhook`（可选）
    - `schedule`（可选）
    - `event`（可选：内部事件总线）
  - `channels`: `{ slack?, wecom?, telegram?, email? }`（可选，先占位）
  - `limits`: 同 chat（可选）
- [ ] bot schema 校验器接入

**DoD**
- publish bot 版本可校验通过，结构可扩展（未来加 channel 不需要改表）。

---

## 2. AppCenter：Chat/Bot 的类型化建模（P0）

### P0-03 apps.type 扩展与约束
- [ ] `apps.type` 允许：`CHAT`、`BOT`（已有 WORKFLOW/AGENT）
- [ ] 若你有 `apps.kind`：可选细分（如 `chat:rag`, `bot:slack`）

**DoD**
- `apps` 可创建 CHAT/BOT 类型，且受 tenant/workspace 隔离。

---

### P0-04 AppVersion 创建与发布行为统一
- [ ] Chat/Bot 版本状态：`draft -> published -> deprecated`
- [ ] `apps.current_version_id` 指向当前发布版本
- [ ] published 版本 `spec_json` 不可变（应用层强制）

**DoD**
- chat/bot 发布后不可覆盖；必须创建新 version 才能修改。

---

## 3. Publish Pipeline：Chat/Bot 的 refs 投影生成（P0）

### P0-05 增加 ChatRefExtractor（必做）
**新增**：`app/app/kernel/projections/chat_projection.py`

- [ ] 从 `chat.v1 spec_json` 提取 refs：
  - model → `ref_type=model`, `ref_key="openai:gpt-5"`（或 provider+model 拼接）
  - tools.allowlist/tool_refs → `ref_type=tool`, `ref_id=...`
  - rag.datasets → `ref_type=dataset`, `ref_id=...`
  - secret 引用（如 tool headers/signature）→ `ref_type=secret`
  - plugin（工具来自插件时）→ `ref_type=plugin`
  - app（嵌套应用，如 bot 引用 chat app）→ `ref_type=app`（可选）
  - 写 `spec_path` 便于定位（强烈建议）

**DoD**
- publish chat 版本后，`app_version_refs` 能准确反映其依赖。

---

### P0-06 增加 BotRefExtractor（必做）
**新增**：`app/app/kernel/projections/bot_projection.py`

- [ ] bot refs 包含：
  - `bot.chat` 内嵌 chat 的所有 refs（复用 ChatRefExtractor）
  - channel config 相关 secrets（如 webhook token、slack signing secret）
  - schedule/event 相关引用（如内部事件源 id，可选）

**DoD**
- publish bot 版本后，refs 完整，能做影响分析（删 dataset/tool/secret 前检查）。

---

### P0-07 AppPublishService 接入 chat/bot refs 构建
- [ ] 在 `AppPublishService.publish()` 中：
  - 根据 `spec_schema` 分发到对应 extractor：
    - `workflow.v1` → WorkflowProjectionBuilder（已做）
    - `chat.v1` → ChatRefExtractor
    - `bot.v1` → BotRefExtractor
  - 统一写入 `app_version_refs`（checksum 幂等）

**DoD**
- 发布 chat/bot 版本时自动生成 refs，且幂等可重建。

---

## 4. 是否需要 components/edges 投影（P1 可选）

> “改造到 app 里”的核心是 apps/app_versions+refs。  
> **components/edges 对 chat/bot 不是必需**，除非你希望把 chat/bot 也表达成“可视化编排的组件图”。

### P1-01（可选）ChatComponentsBuilder：把 chat pipeline 投影成组件
**新增**：`app/app/kernel/projections/chat_components.py`

- [ ] 组件建议（最小）：
  - `retrieval`（有 rag 时）
  - `prompt`（system + user 拼装，可视为逻辑组件）
  - `llm.generate`
  - `tool.router`（有 tools 时）
  - `postprocess`（可选）
- [ ] edges：retrieval→prompt→llm→postprocess（tool/router 从 llm 分支）

**DoD**
- 如果启用：发布 chat 版本会生成 components/edges；否则跳过不生成。

---

### P1-02（可选）BotComponentsBuilder：bot = triggers + chat pipeline + delivery
- [ ] components：
  - trigger（webhook/schedule/event）
  - chat pipeline（复用 chat components）
  - delivery（channel sender）
- [ ] edges：trigger→chat→delivery

**DoD**
- 如果启用：bot 也能在“组件图”里表现整体链路。

---

## 5. 执行模型：Chat/Bot 统一通过 AppRuntimeRouter（P0/P1）

### P0-08 ChatExecutorV1：从 app_versions.spec_json 读取配置
- [ ] `ChatExecutorV1.execute(app_id, version_id, inputs)`：
  - 读取 `chat.v1 spec_json`
  - 调用 LLM gateway
  - 如启用 tools：走 ToolGateway
  - 如启用 rag：走 Dataset retrieval
  - 写 Run/Step/Cost
- [ ] Step 建议：
  - `retrieve`（可选）
  - `llm.generate`
  - `tool.call.*`（可选多次）
  - `finalize`

**DoD**
- chat 走统一 run/step/cost，可从 run 反查使用的 app/version。

---

### P1-03 BotExecutorV1（MVP）：先跑“触发器手动执行”，channel 可后置
- [ ] MVP：`POST /bot/{id}/execute` 或复用 `/apps/{id}/runs`：
  - 输入 messages 或 event payload
  - 内部调用 `ChatExecutorV1`（bot.chat 配置）
  - 输出 final_text + run_id
- [ ] channels 可以先只记录 artifact，不实际发出去（后续再实现）

**DoD**
- bot 能执行（至少手动），链路落 run/step/cost；channel 实发可后续增强。

---

### P1-04 执行前预检（建议）
- [ ] `PreflightChecker` 针对 chat/bot：
  - refs 中的 dataset/tool/secret/plugin 是否存在且可用
  - model 是否允许（ModelHub 限制）
  - budget/timeout 是否合理
- [ ] 失败返回统一 error_code（如 `MISSING_REF_DATASET`）

**DoD**
- 缺依赖时提前失败，错误明确可定位。

---

## 6. API Facade：前端不改（P0）

### P0-09 Chat API Facade 改造（不改接口）
- [ ] 若存在“chat preset/config”：
  - create preset → create `App(type=CHAT)` + draft version（chat.v1）
  - update preset → 更新 draft spec_json（或新建 version）
  - publish preset → `AppPublishService.publish()`
- [ ] 会话表（session/message）：
  - 保留为运行记录表
  - 新会话必须绑定 `app_id`（默认 Chat Default app）
  - message 记录 `run_id`（强烈建议）

**DoD**
- 前端 chat 无改动可用；run/cost 可追溯到 app/version。

---

### P0-10 Bot API Facade 改造（不改接口）
- [ ] create bot → create `App(type=BOT)` + draft version（bot.v1）
- [ ] publish bot → `AppPublishService.publish()`
- [ ] execute bot → 走 AppRuntimeRouter 或 BotExecutorV1

**DoD**
- bot 的配置与发布完全在 apps/app_versions 中完成。

---

## 7. 查询与运营能力（P1）

### P1-05 引用影响分析 API（通用）
- [ ] `GET /api/v1/refs/impact?ref_type=model&ref_key=openai:gpt-5`
- [ ] `GET /api/v1/refs/impact?ref_type=dataset&ref_id=...`
- [ ] `GET /api/v1/apps/{id}/versions/{vid}/refs`

**DoD**
- 任何资源变更前可快速查影响范围（chat/bot/workflow 全覆盖）。

---

## 8. 维护与重建（P1/P2）

### P1-07 投影重建脚本扩展
- [ ] `scripts/rebuild_projections.py` 支持：
  - `spec_schema=chat.v1` → rebuild refs（+ components 可选）
  - `spec_schema=bot.v1` → rebuild refs（+ components 可选）

**DoD**
- 任意时刻能从 spec_json 重建 refs/components。

---

## 9. 测试与验收（P0/P1）

### P0-11 单元测试：RefExtractor
- [ ] chat.v1 fixture：包含 model/tools/rag/secret 引用
- [ ] bot.v1 fixture：包含 triggers/channels secrets + chat 子结构
- [ ] 断言 refs 数量、ref_type、spec_path 正确

### P0-12 集成测试：publish chat/bot
- [ ] create app + create draft version + publish
- [ ] 断言：checksum 写入、refs 插入、status 变更、current_version 指针更新

### P1-08 集成测试：execute chat/bot
- [ ] chat：publish 后对话，run/step/cost 写入
- [ ] bot：手动 execute，run/step/cost 写入

**DoD**
- smoke 能跑通 publish + execute（chat 至少，bot MVP 可选）。

---

## 10. 实施顺序（推荐）

1) P0-01~P0-02：chat/bot schema + validator  
2) P0-05~P0-07：refs extractor + publish pipeline 接入  
3) P0-08：ChatExecutorV1 接入 AppRuntimeRouter  
4) P0-09：Chat API Facade（前端不改）+ session 绑定 app_id/run_id  
5) P0-10：Bot API Facade + BotExecutor MVP  
6) P1：预检、影响分析 API、投影重建脚本扩展  
7) P1（可选）：chat/bot components/edges 投影

---

## 11. 交付验收清单（Release Checklist）
- [ ] chat/bot 定义只存在于 `apps/app_versions`
- [ ] publish chat/bot 后生成 `checksum + app_version_refs`（幂等）
- [ ] chat/bot 执行统一走 run/step/cost，并绑定 app_id/app_version_id
- [ ] 前端 chat/bot（若存在）无改动可用
- [ ] 影响分析：model/tool/dataset/secret 可查引用到的 app_versions

---
