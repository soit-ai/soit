# SOIT 平台可交付版本功能计划（Deliverable Plan）

> 版本定位：**SOIT v0.9 可交付（MVP+可运营）**  
> 目标：在现有代码骨架基础上，把 **Kernel（Run/Step/Artifact/Cost）+ 多租户隔离 + 权限一致性 + Chat/Dataset/Workflow/Tools 最小闭环 + 可观测前端** 做到“可演示、可试用、可复用、可定位问题、可统计成本”的交付标准。  
> 适用形态：企业内测 / 私有化部署 / SaaS 早期试用。

---

## 1. 交付标准（Definition of Done）

### 1.1 平台级 DoD
- **稳定性**：核心链路（登录→创建资源→执行→观测）无崩溃；SSE/WS 断连可恢复或可降级。
- **安全性**：权限检查一致、无异步漂移；Secrets 不以明文进入日志/Trace/Artifact。
- **多租户**：所有资源均带 `tenant_id/workspace_id`，查询与写入强隔离（接口级 + DB 级）。
- **可观测**：任意一次执行均生成 Run/Step，成本（Cost）可聚合查询；前端可查看运行历史与错误定位。
- **可运维**：提供最小部署文档、配置说明、健康检查、基础监控指标、数据库迁移可复现。

### 1.2 业务级 DoD
- **Chat**：会话/消息可持久化、分页查询；支持流式输出；能引用 Dataset 检索结果。
- **Dataset**：上传→解析→切分→向量化→检索闭环；长任务后台化；状态可查、失败可重试。
- **Workflow**：至少 5 类节点可运行（LLM/Tool/If/SetVar/HTTP）；变量引用可用；日志与监控页面可用；失败可定位与重试。
- **Tools**：HTTP 工具可调用；支持 secret injection；调用过程写入 Step + Cost + Audit。
- **Plugin Marketplace（最小版）**：租户级启用/禁用工具插件；支持版本信息展示（可先不实现“升级兼容矩阵”）。

---

## 2. 版本范围（Scope）

### 2.1 必做（In Scope）
- Kernel 稳定地基：Run/Step/Artifact/Cost 全链路、事件化观测、统一策略网关（PolicyGateway）
- Identity：登录、角色、资源授权（ACL/Grant）、API Key（可选）
- Chat + Dataset + Workflow + Tools：形成可交付闭环
- Observability UI：Runs 页面、Workflow Log/Monitor 页面
- 安全：Secrets 注入与脱敏、基础 egress 控制（最小）
- 部署与运维：Docker Compose、迁移、启动脚本、最小文档

### 2.2 暂不做（Out of Scope）
- 高级协作：多人实时协作、评论、审批流
- 高级 Agent：多轮计划、工具自反思、长时任务调度（可留到 v1.0）
- 复杂 Marketplace：签名校验、灰度发布、兼容矩阵、回滚自动化（可留到 v1.0）
- SaaS 计费结算：支付、订阅、发票（先做成本统计与配额预埋）
- 大规模多集群调度：K8S Operator、横向扩展策略（先做单机/小集群）

---

## 3. 里程碑与迭代建议（Milestones）

> 建议 3 个迭代（每迭代 1~2 周），按 **P0→P1→P2**，保证先稳地基再扩展功能。

- **Milestone A（P0）平台地基可用**：权限一致性 + 事件化观测 + Runs/Cost 查询聚合 + Secrets 注入
- **Milestone B（P1）三大业务闭环**：Chat 会话闭环 + Dataset 后台化 + Workflow 节点/变量/重试
- **Milestone C（P1 UI）可交付体验**：Runs 页面 + Workflow log/monitor/publish/setting 页面 + 基础文档

---

## 4. 功能计划（详细清单）

### 4.1 P0 平台地基（必须先完成）

#### 4.1.1 权限一致性与资源级授权（ACL/Grant）
- **目标**：权限判定路径可预测、可 await、无后台漂移；支持对具体资源授予动作权限（read/write/execute）。
- 功能点
  1. 统一鉴权入口：API Dependency/Guard 全部走 `await require_*`
  2. 移除/禁用同步 fallback（`create_task` 等）路径
  3. 新增资源授权表（ResourceGrant）
     - subject：user_id（可扩展 api_key_id）
     - resource：type + id
     - actions：read/write/execute/delete/publish
  4. 权限决策优先级：Owner/Admin/Dev/Viewer（role） + Grant（资源授权提升）
  5. 审计：授权变更写 Audit（who/when/what）
- 验收标准
  - 关键资源（dataset/workflow/chat/session/run）权限校验覆盖完整
  - 无异步漂移；拒绝路径稳定 403；单测覆盖

#### 4.1.2 事件化观测：TraceWriter → EventBus → SSE/WS
- **目标**：替代 DB 轮询，提升实时性与可扩展性。
- 功能点
  1. TraceWriter 写入 run/step/status/cost 时 emit event
  2. Event schema：run.created/run.updated/step.created/step.updated/cost.recorded
  3. SSE Handler 订阅 EventBus 推送；断连即取消订阅
  4. fallback：客户端提供 last_event_id 时可补拉（通过 run/step 查询）
- 验收标准
  - Workflow 执行时，monitor 页面实时看到 step 状态变化
  - DB 轮询退场或作为降级路径（默认事件驱动）

#### 4.1.3 Runs & Cost 查询面（运营可用）
- **目标**：运行历史、成本统计可查，支撑排障与配额。
- 功能点
  1. Run 列表：分页、过滤（mode/status/time/workflow_id/user_id）
  2. Run 详情：steps、artifacts、errors
  3. Cost 聚合：按 provider/model/mode/workspace 时间窗聚合
  4. 导出（可选）：CSV（先留接口）
- 验收标准
  - 前端 Runs 页面可用（见 4.3）
  - 成本统计与 run 关联一致

#### 4.1.4 Tools Secret Injection 与脱敏
- **目标**：工具调用可注入密钥并安全脱敏。
- 功能点
  1. 定义最小“Secret 引用协议”
     - headers/query/body 支持 `secret_ref`
     - 可选：签名策略 `signing_policy_ref`
  2. ToolPolicyGateway 执行注入与脱敏
  3. Audit 记录引用（ref）而非明文
- 验收标准
  - 任意日志/trace 中不出现明文 secrets
  - 单测覆盖注入成功与脱敏规则

---

### 4.2 P1 业务闭环（可交付功能核心）

#### 4.2.1 Chat：会话与消息完整闭环
- 功能点
  1. Session CRUD：创建/重命名/归档/删除（软删）
  2. Message：追加、分页、按 session 查询、引用 run_id
  3. Streaming：
     - SSE/WS 流式输出（断连处理）
     - finish_reason、token_usage、cost 对齐
  4. RAG（可选）：支持从 Dataset 检索并注入引用
- 验收标准
  - 前端 Chat 可用：刷新不丢历史；分页可查；流式输出稳定
  - 每次对话生成 Run/Steps，成本可查询

#### 4.2.2 Dataset：上传→解析→切分→向量→检索闭环（后台化）
- 功能点
  1. Dataset CRUD：创建/重命名/删除（软删）/权限
  2. Document 上传：
     - 对象存储落地（MinIO）
     - 生成 Artifact 记录
  3. Ingestion Job（后台化）：
     - 状态机：queued/running/succeeded/failed/canceled
     - 重试：手动重试（最小）/自动重试（可选）
  4. 解析与切分：
     - 至少支持：txt/markdown/pdf（pdf 可先纯文本）
     - chunk 规则可配置（chunk_size/overlap）
  5. 向量化与索引：
     - embeddings 批处理
     - upsert 至 Milvus（或当前 adapter）
  6. 检索：
     - topK + score
     - snippet + citation（doc_id/chunk_id）
  7. 删除一致性：
     - 删除 doc 同步移除索引 + 对象存储（或进入回收站策略）
- 验收标准
  - 上传大文件不阻塞；任务状态可查；失败可重试
  - 检索可返回引用信息并在 Chat/Workflow 使用

#### 4.2.3 Workflow：节点最小集合 + 变量系统 + 重试/重放
- 功能点
  1. Workflow CRUD：创建/编辑/复制/删除/权限
  2. Node 最小集合：
     - LLM Node
     - Tool Invoke Node（HTTP）
     - If/Condition Node
     - SetVar Node
     - HTTP Request Node（可合并到 ToolInvoke，仍建议独立便于 UI）
  3. 变量系统：
     - `{{inputs.xxx}}`
     - `{{context.xxx}}`
     - `{{steps.node_id.output.xxx}}`
  4. 执行：
     - 每节点写 RunStep（node_id/step_type/status/start/end/error）
     - 失败错误结构化（error_code/message/stack/extra）
  5. 控制：
     - retry：对失败 node 重试（追加新 step，不覆盖旧 step）
     - replay：从历史 run 复制 inputs 生成新 run
  6. 导入/导出（最小）：
     - JSON（YAML 可延后）
- 验收标准
  - 一个包含 5 节点的示例 workflow 可跑通
  - 监控页实时展示 steps；log 可过滤与查看错误详情
  - retry/replay 行为一致且可观测

---

### 4.3 P1 前端可交付体验（必须补齐的页面）

#### 4.3.1 Runs 页面（运行历史/成本）
- 页面与功能
  1. Runs 列表：过滤（mode/status/time），分页
  2. Run 详情：step 时间线/表格、artifact 列表、错误详情
  3. Cost 统计：按 provider/model 聚合视图（图表可简）
- 验收标准
  - 运营/开发可通过 UI 定位失败节点与成本来源

#### 4.3.2 Workflow 详情页补齐（当前空文件需实现）
- 需要实现的页面
  - `workflow/detail/monitor`：实时 step 流（SSE/WS）
  - `workflow/detail/log`：历史 run steps 与错误详情
  - `workflow/detail/publish`：最小发布（版本号/草稿/已发布）
  - `workflow/detail/setting`：权限、运行限制（timeout、max_steps 等）
- 验收标准
  - 运行中可看 monitor；运行后可查 log；可发布并生成可执行入口

#### 4.3.3 Dataset 页面体验补齐（建议）
- 功能点
  - 文档列表与 ingestion 状态
  - 文档详情：chunks 数量、最后更新时间
  - 检索测试：输入 query 返回 results + citations
- 验收标准
  - 非研发人员能通过 UI 自助完成“上传-索引-检索验证”

---

### 4.4 P1 运维与发布（可部署、可升级）

#### 4.4.1 Docker Compose 与配置文档
- 功能点
  - compose：api + web + postgres + redis + milvus + minio（按你现有栈）
  - `.env.example`：关键配置说明（LLM provider、vault、storage、vector、auth）
  - 一键启动脚本与健康检查
- 验收标准
  - 新环境按文档 30 分钟内可启动并跑通 demo

#### 4.4.2 迁移与初始化
- 功能点
  - Alembic 迁移可重复执行
  - 初始化脚本：创建默认 tenant/workspace/admin
- 验收标准
  - 清库重建后可一键恢复到可登录可用状态

---

## 5. 交付版本 Demo 场景（必须跑通）

### 场景 A：Chat + Dataset RAG
1. 创建 Dataset → 上传文档 → 等待 ingestion 完成  
2. 在 Chat 中开启“引用该 Dataset” → 提问 → 返回答案 + citations  
3. 在 Runs 页面查看 run/steps/cost

### 场景 B：Workflow 编排与观测
1. 创建 workflow（LLM → If → ToolInvoke → SetVar → LLM）  
2. 执行 workflow（生成 run）  
3. 监控页实时看到步骤变化；失败能在 log 中看到 error_details  
4. 重试失败节点；Run 页面可对比前后差异与成本变化

### 场景 C：Secrets 注入工具调用
1. 配置 Vault/Secrets（写入一个 token）  
2. 工具调用引用 secret_ref 注入 header  
3. Audit/Trace 不出现明文 secrets；调用成功并有 step/cost 记录

---

## 6. 质量保障计划（QA / 测试）

### 6.1 单元测试（最低覆盖）
- identity：role + grant 权限判定
- tools：secret injection + 脱敏
- dataset：chunker + ingestion 状态机
- workflow：变量解析 + executor（至少 5 节点）
- trace：event emit 被触发

### 6.2 集成测试（建议）
- workflow 跑通 + SSE 推送（可用测试 client）
- dataset ingestion 后可检索
- chat 流式输出 + run/cost 一致

### 6.3 回归清单（发布前）
- 登录/权限：不同角色访问同资源的 allow/deny
- 运行历史：run 列表、run 详情、cost 聚合
- SSE：断连重连
- Secrets：无明文泄露（日志扫描）

---

## 7. 发布检查清单（Release Checklist）
- [ ] DB migrations 已生成并通过全量回放
- [ ] `.env.example` 更新且文档一致
- [ ] docker-compose 可启动 demo 并通过场景 A/B/C
- [ ] 关键 API 有 OpenAPI 文档说明（或 README）
- [ ] 前端关键页面（Runs、Workflow log/monitor、Dataset）可用
- [ ] 安全扫描：日志/trace 中无明文 secrets
- [ ] 版本标记与变更日志（CHANGELOG）更新

---

## 8. 任务拆分建议（给团队分配时可用）

### 后端线 A（安全/权限/Secrets）
- 权限 async 化与 ResourceGrant
- ToolPolicyGateway secret injection 与脱敏
- 授权审计与基础安全策略（timeout/budget）

### 后端线 B（可观测/事件/SSE/Runs）
- TraceWriter emit event
- SSE 事件驱动订阅与 fallback
- Runs/Cost 聚合查询与过滤

### 业务线（Chat/Dataset/Workflow）
- Chat session/message 闭环 + streaming
- Dataset ingestion job 状态机 + 后台化
- Workflow 节点与变量系统 + retry/replay

### 前端线（可交付 UI）
- Runs 页面
- Workflow detail：monitor/log/publish/setting
- Dataset 文档与检索测试页面

---

## 9. 下一步建议（最省返工顺序）
1. **先把 P0 做完**（权限一致性、事件化 SSE、Runs/Cost、Secrets 注入）  
2. 再把 **Workflow + UI** 做成可交付（monitor/log）  
3. 并行补齐 **Chat 会话闭环** 与 **Dataset 后台化**  
4. 最后再扩展 Bot/Agent/App/Marketplace（建立在稳定底座之上）

---
