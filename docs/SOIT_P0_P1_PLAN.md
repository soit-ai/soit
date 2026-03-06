# SOIT P0 / P1 迭代计划（Workflow 闭环优先）

> 目标：先把 **Workflow** 从 UI 到后端跑通闭环（P0），再进入“可交付/可运维”的平台化强化（P1）。  
> 说明：本文以当前仓库结构（后端 `app/` + 前端 `web/`）为基准，任务描述尽量落到文件级，并给出验收方式（Smoke）。

---

## 总览

### P0（阻断级修复）— 目标：Workflow 端到端可用
**交付定义（DoD）：**
- ✅ Web 上 `Workflow 列表 → 详情 → 版本 → 发布 → 执行 → SSE 流式执行` 全链路跑通
- ✅ `/workflows/**` 与 `/sse/execution` 的请求/响应契约与前端一致，不出现 400/422
- ✅ Response Envelope（`{code,data,request_id,run_id}`）在前端被一致解包（或全局解包）

### P1（可交付/可运维强化）— 目标：平台稳定地基 + 可观测性闭环
**交付定义（DoD）：**
- ✅ Run / Step / Artifact / Cost 全链路可追踪可查询
- ✅ Secrets / Tool 调用审计与脱敏落地
- ✅ 多租户隔离与 RBAC 最小闭环
- ✅ 形成稳定的回归测试与发布验收流程（CI / Smoke / 关键接口一致性）

---

## P0 任务清单（Workflow 闭环）

> 建议提交顺序：P0-02 → P0-04 → P0-01 → P0-03 → P0-05

### P0-01 前端：workflow service 统一 envelope 解包（阻断 UI 正常渲染）

**问题：**  
后端启用了 Response Envelope（`ResponseEnvelopeMiddleware`），多数 API 返回为 `{"code":0,"data":...}`。  
前端 workflow service 部分方法未 `.then(r => r.data)` 解包，导致 UI 把 envelope 当业务数据使用。

**改动范围：**
- 文件：`web/src/services/workflow/index.ts`
- 将 workflow service 内所有 API 调用统一改为：
  - `return get(...).then(r => r.data)`
  - `return post(...).then(r => r.data)` 等
- 与现有 dataset-service 风格保持一致（当前 `updateWorkflow` 已做解包，其他方法补齐）。

**验收：**
- 打开 Web 的 Workflow 列表/详情页：列表可正常显示，版本列表不报错
- Network 面板确认前端拿到的是业务 payload，而不是 envelope

---

### P0-02 后端：publish 请求体契约修正（避免 422）

**问题：**  
`POST /workflows/{app_id}/publish` 当前写法 `version_id: str = Body(...)` 导致请求体必须为 **裸字符串**。  
前端发送 `{ "version_id": "xxx" }` 导致 422（Unprocessable Entity）。

**改动范围：**
- 文件：
  - `app/app/modules/workflow/application/schemas.py`
  - `app/app/api/v1/workflow/router.py`
- 在 `schemas.py` 增加：
  - `WorkflowPublishRequest(version_id: str, preflight: bool = False)`
- 在 `router.py` 将 publish 接口签名改为：
  - `payload: WorkflowPublishRequest`
  - 调用 handler 使用 `payload.version_id`、`payload.preflight`

**验收（curl 逻辑）：**
1) create workflow → create version → publish  
2) publish 请求不再返回 422，返回 code=0 且 current_version_id 更新

---

### P0-03 后端：WorkflowVersionResponse 字段对齐（workflow_id vs app_id）

**问题：**  
后端返回 `WorkflowVersionResponse.app_id`，但前端类型/逻辑期望 `workflow_id`，导致页面字段 undefined。

**改动范围：**
- 文件：
  - `app/app/modules/workflow/application/schemas.py`
  - `app/app/api/v1/workflow/handlers.py`
- 方案（推荐）：对外 API 维持 workflow 语义
  - 将 `WorkflowVersionResponse` 的 `app_id` 改为 `workflow_id`
  - handler 映射：`workflow_id = version.app_id`

**验收：**
- `GET /workflows/{id}/versions` 返回 items 中包含 `workflow_id`
- Web 版本列表/详情页不再出现 undefined 相关错误

---

### P0-04 后端：SSE /sse/execution body 字段对齐（workflow_id vs app_id）

**问题：**  
前端 `streamWorkflowExecution()` 发送 `{ workflow_id, inputs }`。  
后端 `/sse/execution` 目前参数名为 `app_id`，FastAPI 会按字段名取 body，导致字段不一致 → SSE 无法启动。

**改动范围：**
- 文件：`app/app/api/v1/sse/router.py`
- 将参数名从 `app_id` 改为 `workflow_id`（内部仍当 app_id 使用即可）：
  - `workflow_id: str = Body(...)`
  - 调用 handler 时传 `workflow_id`

**验收：**
- Web 触发流式执行：SSE 连接正常建立并持续输出事件
- 后端无 422/400，客户端无 JSON key mismatch

---

### P0-05 新增：最小 Smoke（固化验收，防回归）

**目的：**  
避免后续改动导致 Workflow 闭环回归，形成“可执行的验收步骤”。

**建议新增：**
- 文件：`app/scripts/smoke_workflow.sh`（或 python 版本）
- 内容包含：
  - 登录拿 token
  - create workflow
  - create version
  - publish
  - execute（非 SSE）
  - （可选）SSE 建议走 Web 验收，或提供 curl/脚本示例

**验收：**
- smoke 脚本执行所有步骤 HTTP 200/201
- 每步返回 envelope `code=0`
- publish 后 current_version_id 正确更新
- execute 返回 run_id（或至少包含可追踪执行结果）

---

### P0 配套：建议统一前端 request 全局解包（可选）

> 这是替代 P0-01“逐 service 解包”的方案，若后续要更统一，建议纳入 P1 做一次全局一致化。

- 文件：`web/src/utils/request.ts`
- 在统一响应拦截处解包：
  - 成功：直接返回 `envelope.data`
  - 保留 `request_id/run_id` 可通过 headers 或另一个 wrapper 暴露（按你们需要）

---

## P0 验收清单（Checklist）

- [ ] Workflow 列表加载正常（无 envelope 结构泄漏到 UI）
- [ ] Workflow 详情页可打开并显示版本列表
- [ ] 创建版本成功
- [ ] 发布版本成功（不出现 422）
- [ ] 执行成功（非 SSE）
- [ ] SSE 执行能建立连接并持续返回事件（字段名一致）

---

## P1 任务清单（可交付/可运维强化）

### P1-01 Run / Step / Artifact / Cost 全链路打通（平台稳定地基）

**目标：**
- 每次 workflow / chat / tool 调用都能生成可追踪的 run_id
- 节点级别的 step 记录完整（开始/结束/状态/错误/耗时）
- artifacts（输入输出、日志片段、文件引用等）可查询
- cost（LLM/tool）可聚合统计，支持 workspace / app / run 维度

**实现要点：**
- workflow 执行引擎：节点执行必须写 step（成功/失败都写）
- LLM 与 tool gateway：统一写 cost 记录
- API：run 查询、step 查询、artifact 列表、cost 汇总接口补齐
- Web：监控/日志页面与后端接口逐项对齐（字段与筛选条件一致）

**验收：**
- 任意一次 workflow execute 之后：
  - 能按 run_id 查询到 run、steps、artifacts、cost
  - 失败场景（节点报错）也能完整落库并可视化

---

### P1-02 Secrets / Tool 调用闭环验收（可审计、可脱敏）

**目标：**
- secret_ref 注入链路完善：tool/connector 读取 secret 时不泄漏明文
- tool 调用审计：按 run_id 可查询调用记录（参数脱敏、响应摘要可控）
- 基础安全：日志/trace 不打印 Authorization、密钥、敏感 headers/body

**实现要点：**
- secret 注入：统一在 gateway 层解引用（不要在业务层散落）
- 脱敏策略：中间件 / logger 层做 redaction（headers/body key allowlist/denylist）
- 审计表结构：至少包含 tool_name、provider、latency、status、error、request_ref、response_ref

**验收：**
- 使用含 secret 的 tool 执行一次
- 日志与 DB 审计记录中不出现明文 secret
- 仍能复盘调用（有必要的上下文字段、trace/run_id 完整）

---

### P1-03 多租户隔离与 RBAC 最小闭环

**目标：**
- 所有资源按 workspace 隔离（含 apps/workflows/datasets/runs/artifacts 等）
- RBAC 最小可用：读写权限区分 + 拒绝路径明确

**实现要点：**
- workspace header（如 `X-Workspace-Id`）贯穿：
  - middleware 解析
  - repo 查询强制加 workspace_id 条件
- RBAC：
  - role：owner/admin/member/viewer（或你们现有）
  - 权限点：create/update/delete vs read
  - 审计：关键操作记录 actor_id、workspace_id、resource_id

**验收：**
- 同一账号在两个 workspace 下创建资源互不可见
- viewer 角色无法进行写操作（返回 403）

---

### P1-04 回归测试与发布验收流程固化

**目标：**
- PR 合并前能自动跑基础测试（至少覆盖 P0 smoke 的关键接口）
- 发布前能一键跑 smoke（docker compose 环境）

**实现要点：**
- tests：
  - 单元测试：schema/handler/gateway 的关键逻辑
  - 集成测试：workflow publish/execute、dataset ingest/query、chat basic
- scripts：
  - `scripts/smoke_*.sh` 标准化输出（成功/失败码）
- CI：
  - lint + unit + (可选) integration（或 nightly）

**验收：**
- CI 通过后才能合并
- 任意发布候选版本可一键跑 smoke 并得出可交付结论

---

## P1 验收清单（Checklist）

- [ ] workflow execute 后：run/steps/artifacts/cost 可完整查询
- [ ] tool 调用可审计且日志脱敏
- [ ] workspace 隔离用例通过
- [ ] RBAC 最小权限用例通过（403 正确）
- [ ] CI/Smoke 固化，发布可重复

---

## 建议排期（参考）

- **P0：1 个短迭代（1~3 天）**  
  以“workflow 闭环能演示”为唯一目标，先不扩展新功能。
- **P1：1~2 个迭代（2~4 周）**  
  以“可交付/可运维”为目标，优先落地可观测性地基（Run/Step/Artifact/Cost）与安全审计。

---

## 附：P0 Smoke 执行步骤（示例）

> 以下为示意步骤，具体命令可在仓库落脚到 `app/scripts/smoke_workflow.sh`

1. docker compose 启动依赖（Postgres/Redis/Milvus/MinIO/Vault/api/web）
2. migrate + bootstrap admin
3. create workflow
4. create workflow version
5. publish version
6. execute（非 SSE）
7. Web 触发 SSE 执行并观察流式事件输出
