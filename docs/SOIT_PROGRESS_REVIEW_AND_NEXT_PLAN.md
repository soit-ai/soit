# SOIT 代码进度复盘 & 下一阶段待完善功能计划（面向可交付版本）

> 基于你提供的 `soit-pro.zip`（后端 `app/` + 前端 `web/`），对照 `app/docs/engineering/PLAN_GUIDE.md` 逐项检查后的结论与下一步计划。  
> 目标版本：**v0.9 可交付（MVP + 可运营）**（与 Roadmap 的 M0/M1/M3/M4/M5 MVP loop 对齐）

---

## 0. 总结结论：是否按计划继续推进？

**可以继续按计划推进，并且当前实现与 Roadmap 的方向一致。**  
但为了“可交付”，建议把下一阶段的主线聚焦在：

1) **M0 DoD 补齐（权限一致性/事件化观测/运行历史与成本/Secrets 注入落地验证）**  
2) **M5 Workflow 做成产品闭环（发布/设置页 + 版本/权限/运行控制）**  
3) 并行补齐 **M1 Chat 的完整会话体验** 与 **M3 Dataset 的后台化 ingestion 闭环**  

---

## 1. Roadmap 对照：当前实现进度（按 Milestone）

> 说明：下面的“完成度”是按 **交付标准（可演示可用）** 评估，不是“是否已有文件/接口”。

### M0 Kernel Foundation（完成度：≈ 85%）
已具备（对照计划）：
- **RequestContext 多租户作用域**（`tenant_id/workspace_id/user_id`）✅
- **RBAC + 资源级授权（ResourceGrant）** ✅
- **Run/Step/Artifact/Cost 核心模型 + Run API** ✅
- **EventBus + TraceWriter emit events** ✅
- **SSE 支持事件驱动（并保留 DB fallback）** ✅
- **Tools PolicyGateway：egress/rate-limit/audit/timeout/retry + secret injection** ✅
- **Runs/Cost 聚合接口** ✅

主要缺口（M0 DoD 级别）：
- **授权“异步漂移”已基本解决，但仍存在 sync wrapper 依赖线程执行的路径**（需要明确约束：仅在 sync guard 使用，且不可在高并发热点路径滥用）
- **EventBus 仍是 InMemory（进程内）**：单机可交付；若你计划短期支持多实例，需要规划 Redis/NATS（可留 v1.0，但要在文档里明确限制）

---

### M1 Chat（完成度：≈ 70%）
已具备：
- Conversation + Message 持久化模型（含 `run_id`）✅
- Chat 模块 service/repository/API 框架齐全 ✅

待补齐到可交付：
- **对话列表/归档/删除/分页** 的前后端一致体验
- **Streaming 断连恢复/finish_reason/token usage/cost 对齐**（跑通 demo）
- **RAG 引用 Dataset 的 citations 展示闭环**（能“看见引用来源”）

---

### M3 Dataset（完成度：≈ 75%）
已具备：
- Dataset/Document/Chunk/Index 基础模型 ✅
- **DatasetIngestTask（queued/running/succeeded/failed/canceled）+ retry 字段** ✅
- runtime ingest_worker（可后台跑）✅

待补齐到可交付：
- **worker 的常驻运行方式**（命令/compose service/开关配置）
- ingestion 的 **可查询/可重试/可取消** API 与 UI 完整闭环
- 删除一致性（对象存储 + 向量索引 + 元数据）明确策略（立即删 or 回收站）

---

### M4 Tools & Connectors（完成度：≈ 70%）
已具备：
- ToolPolicyGateway（timeout/retry/rate/egress/audit）✅
- **secret injection（`secret_ref` → resolved + redacted）** ✅

待补齐到可交付：
- **Secrets 管理 UI/API（最小：CRUD + 引用测试）**
- Tool schema 校验与错误回显（让非研发也能配置工具）

---

### M5 Workflow（完成度：≈ 70% 后端 / ≈ 60% 前端）
已具备：
- Workflow + WorkflowVersion（current_version 指针）✅
- publish_version / list_versions / run / retry / replay 等 API ✅
- Workflow detail 页：`build.tsx`、`log.tsx`、`monitor.tsx` 已实现 ✅

明显缺口：
- 前端 **publish.tsx / setting.tsx 仍为空文件（0 行）** —— 这是“不可交付”的关键短板  
- settings 所对应的后端能力（运行限制/权限/参数）需要补齐（最小实现）

---

## 2. 当前版本的“可交付风险点”（优先级 P0）

### P0-1：Workflow 发布闭环缺失（最影响演示）
- publish 页空 → 用户无法把 build 的内容“发布成可执行版本”
- 建议把 publish 做成 **最小三件套**：
  1) 版本列表（时间/创建人/摘要）
  2) 发布（写入 workflow.current_version_id）
  3) 一键执行（基于当前版本）

### P0-2：Workflow 设置闭环缺失（权限/运行限制）
- setting 页空 → 无法体现“企业级可控”
- 最小 setting：
  - 权限：Owner/Admin/Dev/Viewer + ResourceGrant（共享给某人）
  - 运行限制：timeout、max_steps、max_tool_calls、budget（先落表或 JSON meta）

### P0-3：Dataset Worker 的运行方式需要“交付级说明”
- 已有 ingest_worker，但需要明确：
  - 作为独立进程跑（compose service）还是 Celery/队列
  - 失败重试与并发配置
  - 任务 claim 的租户/工作区边界

---

## 3. 下一阶段待完善功能计划（面向 v0.9 可交付）

> 下面按 P0/P1/P2 排序，带验收标准（DoD），可直接转 Jira/Linear。

### 3.1 P0（必须完成，保证可交付）

#### P0-A：Workflow 发布 & 设置（前端 + 后端闭环）
- **Publish（前端）**
  - [ ] 版本列表：`GET /workflow/{id}/versions`
  - [ ] 发布按钮：`POST /workflow/{id}/publish`（或已存在 publish_version 作为发布）
  - [ ] 当前版本标识：`GET /workflow/{id}/version/current`
  - [ ] 发布后跳转可执行（run）入口
- **Setting（前端）**
  - [ ] 权限管理：展示 workspace role + resource grants（共享给 user）
  - [ ] 运行限制：timeout/max_steps/max_tool_calls/budget（最小可落在 workflow metadata_json 或独立表）
- **验收**
  - 能从 build → publish → run → monitor/log 一条链跑通（demo 必过）

#### P0-B：Runs/Cost UI 与排障闭环（确认“可运营”）
- [ ] Runs 列表过滤（mode/status/time/workflow_id）
- [ ] Run 详情：steps + errors + artifacts
- [ ] Cost Summary：by day/by model/by provider（至少 1 张图或表）
- **验收**
  - 任意一次 workflow/chat 执行都能在 Runs 页面定位到失败原因与成本来源

#### P0-C：Secrets 管理最小闭环
- [ ] Secrets CRUD（仅 workspace scope）
- [ ] `secret_ref` 引用测试（调用一个 HTTP tool 或 health check）
- [ ] 全链路脱敏验证（日志/trace/artifact 不出现明文）
- **验收**
  - 场景：带 token 的 HTTP tool 成功调用，trace/audit 仅记录 redacted

#### P0-D：Dataset Ingest Worker 交付化
- [ ] worker 启动方式确定（compose service / command）
- [ ] ingest task 列表、详情、重试 API + UI（最小）
- [ ] 失败原因展示（error_code/error_message）
- **验收**
  - 上传文档 → 任务排队 → worker 处理 → 可检索；失败可重试

---

### 3.2 P1（提升可用性，形成“可试用产品”）

#### P1-A：Chat 产品体验补齐（会话管理 + RAG 引用）
- [ ] 会话列表/搜索/归档/删除（软删）
- [ ] message 分页 + 回放
- [ ] RAG citations 展示（来源 doc/chunk）
- [ ] streaming 断连处理（至少不会挂死/卡住）
- **验收**
  - demo：选择 dataset → chat 提问 → 返回引用 → Runs 可查 cost

#### P1-B：Workflow 变量系统与节点最小集验收
- [ ] 变量引用：`{{inputs}}/{{context}}/{{steps.node.output}}` 全覆盖
- [ ] 节点：LLM/Tool/If/SetVar/HTTP 全部可跑通（含错误回显）
- [ ] retry/replay：追加 step，不覆盖历史
- **验收**
  - 一个 5 节点样例 workflow（含 if 分支）稳定跑通

#### P1-C：PluginMarket（最小租户级启停）
- [ ] tool 插件列表（已安装/可用）
- [ ] enable/disable（租户级）
- [ ] runtime reload（已有接口则补 UI）
- **验收**
  - 禁用工具后 workflow/tool 调用被拒绝且可解释

---

### 3.3 P2（为 v1.0 做准备，可延后）

- [ ] InMemory EventBus → 可插拔（Redis/NATS）并可跨实例推送
- [ ] API Key 管理（创建/轮换/吊销）+ rate limit/quota 配置落库
- [ ] Marketplace 签名/兼容矩阵/灰度发布
- [ ] Agent（plan-execute-verify）最小 runtime
- [ ] AppCenter（App definition + install + permissions）

---

## 4. 建议的推进顺序（最少返工）
1) **Workflow publish/setting（P0-A）** → 立刻提升“可交付感”  
2) **Secrets + Tools 引用闭环（P0-C）** → 企业/客户最在意  
3) **Dataset worker 交付化（P0-D）** → RAG 价值体现  
4) **Runs/Cost UI（P0-B）** → 可运营、可排障  
5) 再做 Chat/RAG/PluginMarket（P1）提升产品体验  

---

## 5. 可交付 Demo 清单（发布前必须全部通过）
- [ ] **Demo-1：Workflow** build → publish → run → monitor/log → retry  
- [ ] **Demo-2：Dataset** upload → ingest task → worker 完成 → 检索测试通过  
- [ ] **Demo-3：Chat+RAG** 选择 dataset → chat → 引用可见 → Runs 成本可查  
- [ ] **Demo-4：Secrets** secret_ref 注入 → HTTP tool 成功 → 全链路无明文泄露

---
