# SOIT：Workflow 集成 AppCenter（最优建议）后端改造开发清单（详细）

> 目标：按“最优建议”落地统一模型  
> - **canonical 真相**：`app_versions.spec_json`（workflow 版本完整 DAG）  
> - **通用组件图投影**：`app_components` + `app_component_edges`（用于查询/执行加速/未来扩展）  
> - **外部引用**：`app_version_refs`（只存 tool/dataset/model/plugin/secret/app 等外部资源引用，不存节点）  
> - **省略**：`workflow_node_index` / `workflow_edge_index`（不再需要）  
> - **前端不改**：保留现有 `/workflow/*` API，内部改走 AppCenter + 投影生成

---

## 0. 总体架构与职责拆分（定死，不走弯路）

### 数据真相与投影
- **AppVersion.spec_json**：唯一真相（发布/回滚/导入导出都依赖它）
- **AppComponents/AppComponentEdges**：发布后生成的投影（可重建）
- **AppVersionRefs**：发布后生成的外部依赖索引（可重建）

### 生成时机
- draft：只写 `spec_json`（轻量保存）
- publish：`validate -> checksum -> set current -> build refs -> build components/edges`（同步完成，保证发布版本可查询/可执行）

---

## 1. 数据模型改造（P0）

### P0-01 新增表：app_components（节点实例投影）
**位置建议**：`app/app/modules/appcenter/domain/models.py` 或 `modules/app/domain/models.py`

- [ ] 表 `app_components`
  - `id`（PK，UUID/ULID）
  - `tenant_id`, `workspace_id`
  - `app_id`, `app_version_id`
  - `component_id`（string，等同 workflow node_id，业务内唯一）
  - `component_type`（string，如 `llm.chat`, `tool.http`, `control.if`）
  - `name`（可选）
  - `spec_json`（JSONB：节点参数配置）
  - `ui_json`（JSONB：坐标/分组/颜色等）
  - `spec_checksum`（string：与 app_versions.checksum 对齐）
  - `created_at`, `updated_at`
- [ ] 约束/索引
  - `UNIQUE(app_version_id, component_id)`
  - index：`(tenant_id, workspace_id, app_id)`, `(app_version_id)`, `(component_type)`, `(spec_checksum)`

**DoD**
- 能按 app_version_id 拉取全量 components；单个 component_id 唯一。

---

### P0-02 新增表：app_component_edges（连线投影）
- [ ] 表 `app_component_edges`
  - `id`（PK）
  - `tenant_id`, `workspace_id`
  - `app_id`, `app_version_id`
  - `edge_id`（string）
  - `from_component_id`, `to_component_id`
  - `edge_spec_json`（JSONB：端口映射、条件表达式等）
  - `spec_checksum`
  - `created_at`, `updated_at`
- [ ] 约束/索引
  - `UNIQUE(app_version_id, edge_id)`（或 `(app_version_id, from, to, ports)`）
  - index：`(app_version_id)`, `(from_component_id)`, `(to_component_id)`, `(spec_checksum)`

**DoD**
- 能按 app_version_id 拉取全量 edges；边可定位到 from/to 节点。

---

### P0-03 新增表：app_version_refs（外部引用索引）
> 只存外部依赖，不存 workflow node/edge

- [ ] 表 `app_version_refs`
  - `id`（PK）
  - `tenant_id`, `workspace_id`
  - `app_id`, `app_version_id`
  - `ref_type`：`tool | dataset | model | plugin | secret | app`
  - `ref_id`（UUID，适用于 tool/dataset/plugin/secret/app）
  - `ref_key`（string，适用于 model：如 `openai:gpt-5`）
  - `spec_path`（string：引用在 spec_json 的 JSONPath，如 `$.graph.nodes[3].params.tool_ref`）
  - `spec_checksum`
  - `created_at`
- [ ] 约束/索引
  - `UNIQUE(app_version_id, ref_type, COALESCE(ref_id, ''), COALESCE(ref_key, ''), COALESCE(spec_path, ''))`
  - index：`(ref_type, ref_id)`, `(ref_type, ref_key)`, `(app_version_id)`, `(spec_checksum)`

**DoD**
- 能快速回答：“某 tool/dataset/model 被哪些 app_version 引用？”

---

### P0-04 app_versions 增强：checksum + published 不可变约束
- [ ] `app_versions` 增加 `checksum`（SHA256(spec_json canonicalized)）
- [ ] publish 后禁止修改 published 版本 spec_json（DB 层可用 status check + 应用层强制）
- [ ] 增加 `created_from_version_id`（可选，用于复制/回滚溯源）

**DoD**
- published 版本不可被覆盖；修改必须创建新版本。

---

### P0-05 Alembic migration
- [ ] 新增 migration：创建上述 3 张表 + app_versions 新字段
- [ ] 若你使用“清库重建 baseline”：把这些表加入 baseline

**DoD**
- migrate 后表结构完整，索引/约束生效。

---

## 2. Spec 与 Catalog（P0/P1）

### P0-06 workflow.v1 spec 明确化（canonical）
- [ ] 确认 `workflow.v1` spec 结构至少包含：
  - `graph.nodes[]`：`id,type,name,params,ui`
  - `graph.edges[]`：`id,from,to,from_port,to_port,condition?`
  - `inputs_schema` / `outputs_schema`
  - `limits`：timeout/max_steps/budget/max_tool_calls
  - `runtime`：`workflow_engine_v1`
- [ ] 提供 JSON Schema：`kernel/specs/apps/v1/workflow.v1.schema.json`

**DoD**
- validator 能校验 workflow.v1；错误信息含 path。

---

### P1-01 Node Catalog（节点类型定义）统一入口
> 不存实例，只存类型定义；未来插件节点接入这里

- [ ] 定义 `NodeDef` 结构（内存 registry 或表均可，推荐 registry + 插件装载）：
  - `node_type`、`params_schema`、`io_schema`、`executor`、`source(builtin/plugin)`、`plugin_id?`
- [ ] 新增 API：`GET /api/v1/workflow/node-catalog`（给前端画布用，如果前端已调用则对齐）

**DoD**
- 能返回可用节点类型、schema、默认值提示。

---

## 3. Publish Pipeline（核心）（P0）

### P0-07 实现发布管线：publish -> validate -> checksum -> projections
**新增服务**：`AppPublishService`（建议放 `modules/appcenter/application/publish_service.py`）

- [ ] `publish(app_id, version_id)` 步骤：
  1. 读取 App + Version（必须是 draft）
  2. `SpecValidator.validate(version.spec_schema, version.spec_json)`
  3. 计算 `checksum = sha256(canonical_json(spec_json))`，写回 version
  4. 将旧 published 标记为 deprecated（可选）
  5. 将当前 version 标记为 published
  6. 更新 `apps.current_version_id = version_id`
  7. `ProjectionBuilder.build_refs(...)` 生成 `app_version_refs`
  8. `ProjectionBuilder.build_components(...)` 生成 `app_components/app_component_edges`
  9. 事务提交

- [ ] 幂等策略：
  - 若 version 已 published 且 checksum 未变：直接返回成功
  - 生成投影时使用 `spec_checksum`：先 delete where app_version_id & checksum!=current，再批量 upsert current

**DoD**
- 发布一次后：refs/components/edges 都生成；重复发布不会重复插入脏数据。

---

### P0-08 ProjectionBuilder：从 workflow spec 生成 components/edges/refs
**新增模块**：`kernel/projections/workflow_projection.py`

- [ ] `build_workflow_components(spec_json) -> components[]`
  - 映射：node.id -> component_id，node.type -> component_type，params/ui 拆分为 JSON
- [ ] `build_workflow_edges(spec_json) -> edges[]`
  - from/to/ports/condition -> edge_spec_json
- [ ] `build_workflow_refs(spec_json) -> refs[]`
  - 从 node.params 中提取：
    - tool_ref/dataset_ref/model_ref/plugin_ref/secret_ref 等（按你 spec 约定）
  - 输出 ref_type/ref_id/ref_key/spec_path

**DoD**
- 给定任意 workflow spec，能稳定生成投影与引用列表。

---

## 4. 执行模型改造（P0/P1）

### P0-09 WorkflowExecutor：读取 canonical spec（不依赖投影）
> 最优建议下，执行以 spec_json 为准；components/edges 用于查询和可选加速

- [ ] 现有 `WorkflowExecutorV1` 改为读取 `app_versions.spec_json`
- [ ] 生成 run/step：node_id 对应 step.external_id（建议用 node_id）
- [ ] tool/dataset/model 的实际引用，从 spec_json 解析（或从 refs 表读取做预检查）

**DoD**
- 执行完全不依赖 components/edges 表；即使投影没生成，也可执行（但 publish 已保证会生成）。

---

### P1-02 执行前预检（可选但强烈建议）
- [ ] `PreflightChecker`：
  - 检查 app_version_refs 中的外部依赖是否存在/可用/权限允许
  - model 是否在 ModelHub 允许列表内
  - tool 是否已安装启用（插件状态）

**DoD**
- 缺依赖时提前失败，返回明确 error_code，而不是运行到一半才炸。

---

## 5. Workflow API Facade 改造（前端不改）（P0）

### P0-10 workflow endpoints 内部接入 publish pipeline
- [ ] `POST /workflow/{id}/publish`：
  - 调用 `AppPublishService.publish(app_id, version_id)`
- [ ] `GET /workflow/{id}/versions`：
  - 来自 app_versions；字段适配前端旧协议
- [ ] `GET /workflow/{id}/detail`：
  - 从 current_version/spec_json 拼装旧字段（id/name/version/graph/etc）
- [ ] `POST /workflow/{id}/run`：
  - 默认使用 `apps.current_version_id`（published）
- [ ] `POST /workflow/{id}/run?use_draft=true`（可选）：
  - 显式指定某 draft version

**DoD**
- 前端 workflow 全链路无改动可用。

---

## 6. 查询能力（用 components/edges/refs 替代 workflow_*_index）（P1）

### P1-03 查询 API（运营/排障/分析）
- [ ] `GET /api/v1/apps/{id}/versions/{vid}/components`
- [ ] `GET /api/v1/apps/{id}/versions/{vid}/edges`
- [ ] `GET /api/v1/apps/{id}/versions/{vid}/refs`
- [ ] `GET /api/v1/refs/impact?ref_type=tool&ref_id=...`（影响分析）

**DoD**
- 能回答：某 tool/dataset/model 的影响范围；某 workflow 版本包含哪些节点。

---

## 7. 数据一致性与维护（P1/P2）

### P1-04 投影重建命令（必须有）
- [ ] `scripts/rebuild_projections.py --app_id ... --version_id ...`
- [ ] 支持全量重建（用于应急、升级 schema 后修复）

**DoD**
- 任何时刻可从 spec_json 重建 refs/components/edges。

---

### P2-01 清理策略与生命周期
- [ ] app_version deprecated/archived 是否保留投影（建议保留）
- [ ] 删除 app：cascade 删除 app_versions + projections + refs（或软删）

**DoD**
- 删除/归档行为一致，不产生孤儿数据。

---

## 8. 测试与验收（P0/P1）

### P0-11 单元测试：投影生成器
- [ ] 固定 workflow spec fixture：
  - 校验 components 数量、edge 数量、refs 提取结果
  - checksum 不变时幂等

### P0-12 集成测试：publish pipeline
- [ ] create app + create draft version + publish
- [ ] 断言：status 更新、current_version_id 更新、refs/components/edges 生成成功

### P1-05 集成测试：workflow 执行链路
- [ ] publish 后执行 workflow
- [ ] 断言：runs/steps/cost 正常写入，step.external_id=node_id

**DoD**
- CI/本地 smoke 能跑通 publish + execute。

---

## 9. 实施顺序（建议）

1) **P0-01~P0-05**：表结构与 migration（components/edges/refs + checksum）  
2) **P0-06**：workflow.v1 spec schema 明确 + validator  
3) **P0-07~P0-08**：publish pipeline + projection builder  
4) **P0-09~P0-10**：workflow executor + workflow API facade 接入 publish pipeline  
5) **P0-11~P0-12**：核心测试补齐  
6) **P1-03/P1-04**：查询 API + 投影重建脚本  
7) **P1-02**：预检（可选）  
8) **P2**：生命周期/清理策略完善

---

## 10. 最终验收清单（Release Checklist）
- [ ] publish 会生成：`checksum + refs + components + edges`
- [ ] 不存在 workflow_node_index/workflow_edge_index（已省略）
- [ ] execute 只依赖 spec_json（投影缺失也不会阻断执行）
- [ ] 能做影响分析：tool/dataset/model -> 查询引用到的 app_versions
- [ ] 前端 workflow 全链路无改动可用

---
