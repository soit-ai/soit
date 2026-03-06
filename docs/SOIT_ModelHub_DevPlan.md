# SOIT ModelHub 开发计划清单（平台模型库 → 租户 Provider Models 同步）

> 目标：平台维护 **platform_models（平台模型库）**；每个租户/工作区维护 **providers（多 Provider）** 与 **provider_models（租户模型表）**。  
> 租户模型仅从平台库同步（但允许租户在本地 **增删改**），并且 **不引入 catalog_model**。

---

## 0. 当前代码现状（基于 zip 解压后路径核对）

### 前端
- 入口：`web/src/pages/model/*`
- 现状：
  - `pages/model/box.tsx` 存在 **mock providers 列表**（非真实 provider 管理）
  - `web/src/services/provider-service.ts`
    - `listProviders()` 是从 `/models` 结果里 **按 provider 字符串聚合**
    - `createProvider/updateProvider/deleteProvider` **直接抛错：API 不支持**
    - model 的 `baseUrl/apiKey` 被放在 model config 中（每模型一份）

### 后端
- 路由：`app/app/api/v1/modelhub/router.py`（仅 `/models` CRUD）
- 领域模型：`app/app/modules/modelhub/domain/models.py`
  - 当前表：`models`（字段：provider/model_ref/config_json 等）
  - 未存在 `providers`、`platform_models`、同步任务与日志表

---

## 1. 目标形态（数据结构与职责）

### 1.1 platform_models（平台全局模型库）
- 唯一键：`provider_kind + model_id`
- 保存：官方 model 列表、能力、上下文、生命周期、raw_meta
- 由平台任务定期同步更新（external → platform_models）

### 1.2 providers（工作区级 Provider）
- 每 workspace 可配置多个 provider：openai / anthropic / gemini / bedrock / openai_compat ...
- 保存：`kind/name/base_url/credential_ref/status/sync_policy`
- **凭据不落明文**：`credential_ref` 指向 secrets/vault

### 1.3 provider_models（租户模型表）
- 保存：该 workspace 下可用的模型（来源 platform 或 local）
- 关键字段：
  - `provider_id`
  - `source = platform | local`
  - `platform_model_id`（可空；source=platform 时有值）
  - `enabled`
  - `sync_status = in_sync | diverged | platform_removed | never_synced`
  - `user_overrides`：记录用户改动字段，避免下次平台同步覆盖
  - `last_synced_at`

### 1.4 同步链路（两级）
1) 平台同步：external → platform_models（按 provider_kind）
2) 租户同步：platform_models → provider_models（按 provider_id）
- 同步必须遵循「不覆盖用户改动」与「删除不复活」策略（见 P0）

---

## 2. 里程碑与优先级

- **P0：打通“多 Provider + 平台库同步到租户 + 前端可管理”闭环**
- **P1：同步可观测 + 测试控制台 + 策略化同步**
- **P2：商业化增强（成本/限制/默认模型别名等）**

---

## 3. P0（必须完成）——闭环最小可用版本

### P0-1 数据库迁移与模型重构（后端）
**目标**：新增平台库与 providers；将当前 `models` 演进为 `provider_models`（或新增并迁移）。

- [ ] 新增表 `platform_models`
  - 字段建议：
    - `id`
    - `provider_kind`
    - `model_id`
    - `display_name`
    - `capabilities_json`（jsonb）
    - `context_window`, `max_output_tokens`（nullable）
    - `lifecycle`（nullable）
    - `raw_meta`（jsonb）
    - `is_active`（bool）
    - `last_seen_at`, `created_at`, `updated_at`
  - 约束：`UNIQUE(provider_kind, model_id)`

- [ ] 新增表 `providers`
  - 字段建议：
    - `id`（provider_xxx）
    - `tenant_id`, `workspace_id`
    - `kind`（openai/anthropic/…）
    - `name`
    - `base_url`（可空；openai_compat 必填）
    - `credential_ref`（指向 secrets）
    - `status`（active/disabled/error）
    - `sync_policy_json`（jsonb，可空）
    - `last_healthcheck_at`, `last_healthcheck_error`
    - `created_at`, `updated_at`

- [ ] 演进 `models` 表为 `provider_models`（推荐新表 + 迁移，降低风险）
  - 新/补字段：
    - `provider_id`
    - `provider_kind`（冗余，便于筛选）
    - `model_id`（替代/并存 `model_ref`；最终以 model_id 为准）
    - `source`（platform/local）
    - `platform_model_id`（nullable）
    - `enabled`
    - `sync_status`
    - `user_overrides_json`（jsonb）
    - `last_synced_at`
  - 明确：模型调用凭据默认从 provider 来（不要每 model 存 apiKey）
  - 迁移策略：
    - 将旧 `provider` 字段映射到 `provider_kind`
    - 将旧 `model_ref` 映射到 `model_id`（若格式不一致，保留并新增字段逐步切换）

- [ ]（强烈建议）新增 tombstone 表：`provider_model_tombstones`
  - 字段：`workspace_id, provider_id, platform_model_id, deleted_at`
  - 用于避免“用户删除的平台模型在下次同步又出现”

**涉及目录**
- Alembic：`app/alembic/versions/*`
- SQLModel：
  - `app/app/modules/modelhub/domain/models.py`（拆分/新增 platform/provider/provider_model）
  - `app/app/infra/db/*`（如有统一基类/时间戳）

**验收标准**
- 能在 DB 中创建三张新表（或 provider_models 新表）并正常启动迁移
- 旧接口 `/models` 不崩（可先维持兼容，逐步迁移到新 API）

---

### P0-2 平台模型库同步任务（external → platform_models）
**目标**：平台侧可定期把各 provider 的官方模型列表写入 platform_models。

- [ ] 建立 Provider Adapter 接口（平台任务用）
  - `list_models(provider_kind) -> List[ModelDTO]`
- [ ] 先实现最小覆盖（建议至少 3 家）：OpenAI / Anthropic / Gemini
- [ ] Upsert platform_models，并记录 diff（added/removed/changed）
- [ ] 将“抓不到的模型”标记为 `is_active=false`（不删除）

**涉及目录**
- 建议落点：
  - `app/app/modules/modelhub/infra/adapters/*`（或 `app/app/adapters/*`）
  - `app/app/modules/modelhub/application/jobs/*`（若已有 worker 体系）
  - `app/app/modules/modelhub/application/service.py`（补同步入口）

**验收标准**
- 手动触发一次同步后，platform_models 有数据
- 再次同步能产生合理 diff（新增/变更/下线）

---

### P0-3 租户同步（platform_models → provider_models）
**目标**：workspace 下每个 provider 可以“从平台库同步模型到该 provider 的 provider_models”。

- [ ] 新增 API：`POST /api/v1/modelhub/providers/{id}/sync-from-platform`
  - 入参（可选）：`include_model_ids[]`（用于选择性同步）
  - 出参：`job_id`（或同步结果）
- [ ] 同步规则实现：
  - 新增：平台有、租户无 → 插入 `source=platform` 记录
  - 更新：若字段未在 `user_overrides` 中 → 用平台值更新；否则保持并标记 `diverged`
  - 下线：平台 `is_active=false` → 租户标记 `platform_removed`（不删除）
  - 删除：若租户删除平台模型 → 写 tombstone，默认不重建

- [ ] 新增 `sync_jobs`（建议 provider 维度）
  - 字段：`id/workspace_id/provider_id/status/diff_json/error/started_at/ended_at`

**涉及目录**
- API：
  - `app/app/api/v1/modelhub/router.py`（新增 providers 与 sync endpoints）
  - `app/app/api/v1/modelhub/handlers.py`（新增 handler）
- Service：
  - `app/app/modules/modelhub/application/service.py`
  - `app/app/modules/modelhub/infra/repository/*`（如已有仓储层）
- DB：
  - `app/app/infra/db/pagination.py`（列表分页复用）

**验收标准**
- Provider sync 后，provider_models 中出现平台模型
- 用户修改某字段后，再次同步不会覆盖该字段，并将 `sync_status=diverged`
- 用户删除同步模型后，再次同步默认不复活（tombstone 生效）

---

### P0-4 Providers API（工作区多 provider 管理）
**目标**：前端不再从 `/models` 推导 providers，而是有真实 providers CRUD。

- [ ] `GET /api/v1/modelhub/providers`
- [ ] `POST /api/v1/modelhub/providers`
- [ ] `PATCH /api/v1/modelhub/providers/{id}`
- [ ] `DELETE /api/v1/modelhub/providers/{id}`
- [ ] `POST /api/v1/modelhub/providers/{id}/healthcheck`
  - 校验 credential_ref、base_url 连通性（最小：能调用 list_models 或简单 ping）
  - 更新 providers.status 与 last_healthcheck_error

**验收标准**
- 前端能创建/编辑/删除 provider
- provider healthcheck 能给出明确错误（权限/网络/base_url 等）

---

### P0-5 前端 pages/model 落地（去 mock + 支持 provider 管理 + 同步）
**目标**：在 `pages/model` 下完成可用闭环。

- [ ] `web/src/services/provider-service.ts`
  - 替换：
    - `listProviders()`：从 `/modelhub/providers` 获取
    - `createProvider/updateProvider/deleteProvider()`：接通 API（移除抛错）
  - 新增：
    - `syncFromPlatform(providerId)`
    - `healthCheck(providerId)`
    - `listSyncJobs(providerId)`
    - `listPlatformModels(providerKind)`（如需要 platform tab）

- [ ] `web/src/pages/model/setting/ui/provider-list.tsx`
  - 去掉“unavailable toast”
  - 增加按钮：健康检查 / 立即同步 / 查看同步日志
  - Provider 编辑：name/kind/base_url/credential_ref/status

- [ ] `web/src/pages/model/setting/ui/model-list.tsx`
  - 表格增加列：`source`, `sync_status`, `enabled`
  - 平台模型编辑提示：
    - 编辑后写 user_overrides，sync_status 变 diverged
  - 删除平台模型：提示“不会自动恢复”（若 tombstone 默认开启）

- [ ] `web/src/pages/model/box.tsx`
  - 移除硬编码 providers 列表，改为真实 provider 列表与统计

**验收标准**
- 新建 provider → 一键同步 → 看到模型列表
- 模型可启用/禁用、可编辑（平台模型编辑后 diverged）
- 同步日志可查看（至少显示 added/updated/removed/skipped）

---

## 4. P1（强烈建议）——让同步可运营、可排障、可验证

### P1-1 同步策略与定时任务
- [ ] provider `sync_policy_json`：
  - `auto_sync: bool`
  - `interval_minutes: int`
  - `recreate_deleted: bool`（默认 false）
  - `default_enabled: bool`
- [ ] 定时同步：
  - 平台库：external → platform_models（默认每 6h）
  - 租户：platform_models → provider_models（按 provider policy）
- [ ] 同步失败告警：
  - 连续失败 N 次 → provider.status=error，前端提示检查 credential/base_url

### P1-2 同步日志 UI（增强）
- [ ] `sync_jobs` diff 展示组件
  - added/updated/removed/skipped_due_to_override
  - 展示错误堆栈（后端摘要 + request_id）

### P1-3 Model Test（后端补齐 + 前端接通）
> 你已存在 UI：`web/src/pages/model/setting/ui/model-test.tsx`，但 service 目前抛错。

- [ ] 后端新增：
  - `POST /api/v1/modelhub/test/chat`
  - `POST /api/v1/modelhub/test/embeddings`
  - 返回：响应片段、耗时、tokens、request_id、错误详情
- [ ] 前端接通 `ProviderService.testModelConnection()`
- [ ] 增加“保存为推荐配置/快速启用”操作（可选）

---

## 5. P2（可后置）——增强能力与面向商业化

- [ ] workspace 级 allow/deny：限制哪些 provider_models 可用于 bot/workflow/chat
- [ ] 默认模型别名（alias）：`default.chat / default.embedding`
  - 让 bot/workflow build 引用 alias，而不是写死 model_id
- [ ] 价格/成本元数据：在 provider_models 存 pricing（或从平台库带入）
  - 与 Run/Cost 体系结合（后续可观测）
- [ ] openai_compat 自定义 provider：base_url + headers 模板化
- [ ] 平台库人工纠偏：lifecycle/display_name/tags 管理后台（仅管理员）

---

## 6. 建议的开发顺序（可直接在 VSCode/Codex 拆分）

1) **DB：platform_models + providers + provider_models(演进) + sync_jobs + tombstones**
2) **后端：providers CRUD + healthcheck**
3) **后端：平台库同步任务（先 OpenAI/Anthropic/Gemini）**
4) **后端：provider sync-from-platform（含 user_overrides 与 tombstone 规则）**
5) **前端：pages/model provider-list 接真 API + 同步按钮 + jobs 展示**
6) **前端：model-list 增加 source/sync_status/enable 与分叉提示**
7) **P1：Model Test 接通 + 定时同步**

---

## 7. 代码触点速查（便于 Codex 定位）

### 前端
- `web/src/pages/model/index.tsx`
- `web/src/pages/model/box.tsx`
- `web/src/pages/model/setting/index.tsx`
- `web/src/pages/model/setting/models.tsx`
- `web/src/pages/model/setting/ui/provider-list.tsx`
- `web/src/pages/model/setting/ui/model-list.tsx`
- `web/src/pages/model/setting/ui/model-form.tsx`
- `web/src/pages/model/setting/ui/model-test.tsx`
- `web/src/services/provider-service.ts`

### 后端
- `app/app/api/v1/modelhub/router.py`
- `app/app/api/v1/modelhub/handlers.py`
- `app/app/api/v1/modelhub/dependencies.py`
- `app/app/modules/modelhub/domain/models.py`
- `app/app/modules/modelhub/application/service.py`
- `app/alembic/versions/*`

---

## 8. 最小验收用例（P0）
- [ ] 创建 provider（workspace A）
- [ ] 点击“健康检查”通过
- [ ] 点击“从平台同步模型”成功（sync_jobs=success）
- [ ] 在 model-list 中看到同步模型（source=platform, sync_status=in_sync）
- [ ] 修改 display_name → sync_status=diverged
- [ ] 再次同步 → display_name 不被覆盖，jobs diff 中显示 skipped_due_to_override
- [ ] 删除该平台模型 → tombstone 生效；再次同步不复活
