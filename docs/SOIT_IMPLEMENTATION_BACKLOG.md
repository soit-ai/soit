# SOIT 实现清单（Backlog / 任务表）

> 适用范围：`soit-pro` 仓库（后端 `app/` + 前端 `web/`）
>
> 字段说明：
> - **PR 切分建议**：同一任务如需要拆多个 PR，用 `PR1/PR2` 表示
> - **依赖**：写任务编号，表示需要先完成的任务
> - **建议工期**：按“实现 + 单测 + 联调 + 基本文档”粗粒度估算（人日）

---

## P0 必须闭环（M0 底座：可观测 + 多租户隔离 + 权限一致性 + 稳定 SSE）

| ID | 优先级 | Epic | 模块 | 主要路径/文件 | 任务说明 | 验收标准（DoD） | 依赖 | 负责人 | 建议工期(人日) | PR 切分建议 |
|---|---|---|---|---|---|---|---|---|---:|---|
| P0-01 | P0 | 安全与权限 | Identity | `app/app/kernel/identity/permissions.py` `app/app/kernel/identity/guard.py` `app/app/kernel/identity/rbac.py` | 移除“同步权限校验里 create_task/fallback”异步漂移；收敛为明确 async 判定路径（API 依赖必须 await） | 任意资源校验不产生后台漂移任务；拒绝路径稳定返回 403；单测覆盖 role allow/deny |  |  | 2.0 | PR1：新增 async guard；PR2：替换 API dependencies 为 await；PR3：删除旧同步漂移逻辑 |
| P0-02 | P0 | 安全与权限 | Identity | `app/app/modules/identity/domain/models.py` `app/app/modules/identity/infra/repository.py` `app/app/modules/identity/application/service.py` `app/alembic/versions/*` | 新增资源级授权（ResourceGrant/ACL），支持 user→resource→actions 的授权提升 | 表结构与 migration 完成；service 可创建/撤销 grant；权限判定接入 grant；最少覆盖 dataset/workflow 两类资源 | P0-01 |  | 3.0 | PR1：模型+迁移；PR2：repo+service；PR3：接入权限判定+单测 |
| P0-03 | P0 | 基础稳定性 | Secrets | `app/app/adapters/secrets/vault.py` | 修复 Vault adapter 缺失 `Any` 导入导致运行错误 | 启动不报错；至少 1 个单测或 import 校验 |  |  | 0.2 | 单 PR |
| P0-04 | P0 | 可观测基座 | Trace | `app/app/kernel/trace/writer.py` `app/app/wiring/container.py` | TraceWriter 注入 EventBus：写入 Run/Step/Cost 时同时 emit 事件（不影响落库） | 事件包含 tenant/workspace/run/step/cost 关键字段；DB 写入行为不变；单测覆盖 emit 被调用 |  |  | 1.5 | PR1：EventBus 接入；PR2：事件 schema + 单测 |
| P0-05 | P0 | 可观测基座 | SSE | `app/app/api/v1/sse/handlers.py` | SSE 从 DB 轮询升级为事件驱动订阅（允许 fallback 补拉） | SSE 实时推送 step/status；断连立即取消订阅；事件丢失可按 run_id 补拉 steps；压测下 DB 查询显著下降 | P0-04 |  | 2.5 | PR1：事件订阅通道；PR2：fallback 补拉；PR3：压测与文档 |
| P0-06 | P0 | 工具安全 | Tools | `app/app/kernel/ports/tools/policy.py` `app/app/adapters/http_tools.py` | ToolPolicyGateway 实现 secret injection（最小协议），并保证不在日志/trace 中泄露明文 | 支持 header/body/query 的 secret_ref 替换；trace/audit 不含明文；单测覆盖注入与脱敏 | P0-03 |  | 2.0 | PR1：协议+注入实现；PR2：脱敏+单测；PR3：接入示例 |
| P0-07 | P0 | 运行历史与成本 | Runs | `app/app/api/v1/runs/*` `app/app/modules/run/*`（如存在） | 补齐 Runs/Cost 查询接口的聚合视图（按 provider/model/mode 聚合）与必要过滤（time/status/mode） | 列表分页+过滤；run detail 含 steps+cost summary；接口稳定可供前端调用；覆盖关键用例单测 | P0-04 |  | 2.0 | PR1：聚合 API；PR2：过滤+分页；PR3：单测与示例 |

---


---


---

## P1 核心可用（MVP 闭环：Chat + Dataset + Workflow + 前端可见性）

| ID | 优先级 | Epic | 模块 | 主要路径/文件 | 任务说明 | 验收标准（DoD） | 依赖 | 负责人 | 建议工期(人日) | PR 切分建议 |
|---|---|---|---|---|---|---|---|---|---:|---|
| P1-01 | P1 | 前端可观测 | Web-Runs | `web/src/services/run-service.ts` `web/src/pages/run/*`（新增） | 新增 Runs 页面：列表 + 详情（steps、cost summary） | 可查看 Run 列表并筛选；进入详情能看到 steps 时间线 + cost 聚合；与后端接口对齐 | P0-07 |  | 2.0 | PR1：路由+列表；PR2：详情页；PR3：筛选/分页 |
| P1-02 | P1 | Workflow 可见性 | Web-Workflow | `web/src/pages/workflow/detail/log.tsx` `web/src/pages/workflow/detail/monitor.tsx` | 补齐 workflow log/monitor 页面：对接 SSE + run detail | monitor 实时显示 step/status；log 支持过滤 step_type/status；错误详情可展开 | P0-05,P0-07 |  | 2.0 | PR1：monitor SSE；PR2：log 查询+过滤；PR3：UI 细节 |
| P1-03 | P1 | Chat 闭环 | Chat | `app/app/api/v1/chat/*` `app/app/modules/chat/*` `web/src/pages/chat/*` | 会话/消息持久化闭环；流式断连处理；usage/cost 与 run 对齐展示 | session CRUD；message 分页；streaming 断连不破坏会话；cost 归集到 run 并可查询 | P0-07 |  | 3.5 | PR1：后端 session/message；PR2：前端适配；PR3：streaming 细化 |
| P1-04 | P1 | Dataset 后台化 | Dataset | `app/app/modules/dataset/*` `app/app/api/v1/dataset/*` | ingestion 任务化（queued/running/succeeded/failed）；支持重试/取消（最小版可先重试） | 上传不阻塞；任务状态可查；失败可重试；检索不受影响 |  |  | 4.0 | PR1：任务表+迁移；PR2：worker/执行器；PR3：API+前端状态 |
| P1-05 | P1 | Workflow 节点最小集 | Workflow | `app/app/modules/workflow/runtime/*` `app/app/api/v1/workflow/*` | 节点最小集跑通：SetVar/If/LLM/ToolInvoke/HTTP；每节点写 RunStep | 5 节点均可运行；每次节点执行都有 step 记录；失败有 error_details；monitor 可实时看到变化 | P0-05,P0-06 |  | 4.0 | PR1：节点执行器；PR2：变量解析；PR3：集成测试 |
| P1-06 | P1 | Workflow 变量系统 | Workflow | `app/app/modules/workflow/runtime/*` `app/app/api/v1/schemas/workflow.py` | 支持 `{{inputs}}/{{context}}/{{steps.node.output}}` 引用；分支合并策略明确 | 引用表达式覆盖常用场景；错误提示清晰；至少 10 个表达式单测 | P1-05 |  | 2.5 | PR1：表达式解析器；PR2：执行期注入；PR3：单测 |

---

## P2 增强（Agent / Marketplace / 企业能力预埋）

| ID | 优先级 | Epic | 模块 | 主要路径/文件 | 任务说明 | 验收标准（DoD） | 依赖 | 负责人 | 建议工期(人日) | PR 切分建议 |
|---|---|---|---|---|---|---|---|---|---:|---|
| P2-01 | P2 | Agent MVP | Agent | `app/app/modules/agent/*` `app/app/api/v1/agent/*` | 最小 Agent runtime：plan→execute→verify；可调用 tools + dataset retrieval | 提供一个 demo agent；可观测链路完整（run/steps/cost）；失败可定位 | P1-04,P1-05 |  | 4.0 | PR1：agent contracts；PR2：planner/executor；PR3：demo+文档 |
| P2-02 | P2 | 插件市场隔离 | PluginMarket | `app/app/modules/pluginmarket/*` `app/app/kernel/ports/plugin_runtime/*` | 租户级安装/启用/禁用/升级隔离规则固化（含兼容策略） | 同插件在不同 tenant 状态互不影响；升级不破坏已发布 workflow；冲突可阻止升级 | P0-02 |  | 4.0 | PR1：状态模型；PR2：安装/启用 API；PR3：升级策略+测试 |
| P2-03 | P2 | 企业合规预埋 | Security | `app/app/api/v1/security/*` `app/app/kernel/*policy*` | 配额/速率限制/出站审计（egress）基础规则 | 可按 tenant/workspace 限制；审计记录可查；默认规则不影响开发模式 | P0-06,P0-07 |  | 3.0 | PR1：policy；PR2：审计与查询；PR3：文档 |

---

## 并行开发建议（最少冲突的分工方式）

### 后端 A 线（安全/权限/Secrets）
- 负责：P0-01、P0-02、P0-03、P0-06
- 并行原则：P0-03 可独立；P0-01→P0-02 串行；P0-06 依赖 P0-03

### 后端 B 线（Trace/SSE/Runs）
- 负责：P0-04、P0-05、P0-07
- 并行原则：P0-04 先；P0-07 可与 P0-05 并行，但最终一起联调

### 前端线（可见性 UI）
- 负责：P1-01、P1-02（优先）
- 并行原则：等 P0-05、P0-07 接口稳定后联调；页面骨架可先搭

### Workflow 线（runtime/节点/变量）
- 负责：P1-05、P1-06
- 并行原则：先节点执行器（P1-05），变量解析（P1-06）可部分并行，但最终要联调

---

## 迭代建议（可直接作为 Sprint 目标）

### Sprint 1（先稳底座）
- P0-03（Vault 修复）
- P0-01（权限判定收敛）
- P0-02（资源级授权）
- P0-04（Trace 事件发布）

### Sprint 2（可观测跑起来 + 工具安全）
- P0-05（SSE 事件驱动）
- P0-06（Tool secret injection + 脱敏）
- P0-07（Runs/Cost 聚合查询）

### Sprint 3（前端可见性 + Workflow MVP）
- P1-01（Runs 页面）
- P1-02（workflow log/monitor）
- P1-05（Workflow 节点最小集）
- P1-06（Workflow 变量系统）

