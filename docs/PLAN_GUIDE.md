# SOIT 开发计划（Roadmap & Backlog）
> 版本：v1.0  
> 日期：2026-01-04  
> 原则：**内核长期稳定**（Kernel），其余能力尽量以 **Plugin / App** 外挂扩展；统一通过 **Gateway + Registry** 解耦实现可替换、可演进。

---

## 1. 目标与范围

### 1.1 产品形态递进
- **Chat → Bot → Workflow → Agent → App/Workspace**
- 各形态基于统一的：身份权限、多租户、网关抽象、插件注册、执行引擎、可观测性。

### 1.2 开源内核与增值能力边界（建议）
- **开源内核（优先）**：Kernel + Gateway + Registry + Execution + Observability + Chat/Bot/Workflow 基础能力 + Dataset 基础能力
- **企业/增值（后续）**：SSO/SAML、审计与合规、护栏策略中心、私有市场、计费与配额、企业安全边界、团队协作增强

---

## 2. 里程碑计划（Milestones）

> 优先级：P0(必须) / P1(高) / P2(中) / P3(低)

| 里程碑 | 目标产出 | 核心功能包 | 优先级 | 关键依赖 |
|---|---|---|---|---|
| M0 内核底座 | 可长期稳定的 Kernel + Gateway + Registry + Execution | Identity/RBAC、多租户基表、迁移、统一错误码、事件总线、网关接口、插件注册与生命周期、SSE/流式协议、基础日志&TraceId | P0 | DB/配置体系、接口定稿 |
| M1 Chat | 可用对话 API（含流式） | 会话/消息模型、provider:model 路由、流式输出、消息存储&分页、对话参数（system/temperature等）、基础成本统计 | P1 | LLM Gateway、SSE |
| M2 Bot | 角色机器人可配置可发布 | Bot 定义（Prompt/工具权限/模型/参数）、版本管理、发布与分享、运行历史 | P1 | Registry、Tools |
| M3 Dataset | Dataset ingestion + RAG 检索闭环 | Dataset 管理、上传/解析/切分、Embedding、向量索引、检索策略、引用片段返回、删除/重建策略 | P1 | Vector/Storage |
| M4 Tools & Connectors | 工具插件体系跑通 | 工具协议（HTTP 优先）、schema/权限/成本、secret 注入、审计、最小工具集（HTTP/时间/随机等） | P1 | Secrets、Registry |
| M5 Workflow | 可执行编排（节点全插件化） | Workflow 定义/版本、节点插件集（LLM/Tool/条件/变量/HTTP）、变量流转、运行/重试/回放、运行历史与日志、导入导出（YAML/JSON） | P1 | Execution 引擎、Node Plugin |
| M6 Agent | 计划-执行-校验的 Agent 框架 | Planner/Executor/Verifier 组件化、记忆接口、预算与限流、失败恢复 | P2 | Tools/Workflow、Memory |
| M7 Workspace & App | 应用形态交付 | Workspace（项目/成员/资源）、App 定义（UI+后端绑定）、发布/安装、应用级权限 | P2 | Identity、Registry(App类型) |
| M8 Enterprise Boundary | 企业安全边界与合规（企业版） | SSO(OIDC)/SAML、组织架构、审计日志、护栏策略中心、KMS/Vault、数据隔离策略 | P2 | Identity/Audit/Secrets |
| M9 SaaS Ops & Billing | SaaS 化运营能力 | 套餐/配额/用量、成本中心、限流、运维后台、告警 | P3 | Metering、Observability |
| M10 Marketplace | 插件/节点/应用生态分发 | 市场列表、评分/审核、签名校验、灰度/兼容策略、私有市场 | P3 | Registry、安全签名 |

---

## 3. MVP（首发最小闭环）建议范围

**必选闭环：**
1. **M0**：Identity + Gateway + Registry + Execution（含 SSE）+ Observability
2. **M1**：Chat（多模型路由 + 流式 + 存储）
3. **M3**：Dataset（上传→切分→向量→检索→引用）
4. **M4**：Tools（HTTP 工具 + Secret 注入）
5. **M5**：Workflow（基础节点插件 + 运行历史）

---

## 4. Backlog 功能表（可直接拆任务）

### 4.1 多租户与权限
| 模块 | 功能点 | 优先级 | 验收要点 |
|---|---|---|---|
| Tenant | 租户/项目/空间模型 | P0 | 表结构+API；资源隔离生效 |
| RBAC | 角色（Owner/Admin/Dev/Viewer）与资源授权 | P0/P1 | API 鉴权；权限拒绝路径正确 |
| API Key | API Key 管理、轮换、禁用 | P0 | Key 生效/失效可测 |

### 4.2 插件系统（Registry）
| 模块 | 功能点 | 优先级 | 验收要点 |
|---|---|---|---|
| Plugin Types | ModelProvider / Tool / WorkflowNode / App | P0 | 类型可扩展；统一元数据 |
| Lifecycle | 安装/卸载/启停/升级 | P0/P1 | 升级兼容校验；回滚策略（可选） |
| Versioning | 版本与依赖、兼容矩阵 | P1 | 依赖冲突给出可读错误 |

### 4.3 模型网关（LLM Gateway）
| 功能点 | 优先级 | 验收要点 |
|---|---|---|
| provider:model 路由与能力声明 | P0 | 能选择 provider+model 并正确调用 |
| 统一请求/响应结构 | P0 | 适配器更换不影响上层 |
| SSE 流式输出 | P0/P1 | 前端/调用方可稳定消费 |
| 超时/重试/熔断（最小实现） | P1 | 配置可控；失败可追踪 |
| Token/成本统计 | P1 | 每次调用有可记录数据 |

### 4.4 工具网关（Tools Gateway）
| 功能点 | 优先级 | 验收要点 |
|---|---|---|
| 工具 schema（JSON schema）与参数校验 | P1 | 非法参数被拒绝 |
| Secret 注入（headers/signature 等） | P1 | Secret 不落日志；引用正确 |
| 工具调用审计 | P1 | 调用记录可查询 |
| 最小工具集（HTTP/时间/文本处理） | P1 | 能跑通 Workflow/Agent |

### 4.5 向量与存储（Vector/Storage）
| 功能点 | 优先级 | 验收要点 |
|---|---|---|
| Milvus 适配（Vector Gateway） | P1 | upsert/search/delete 可用 |
| MinIO/S3 适配（Storage Gateway） | P1 | 上传/下载/签名 URL 可用 |
| 文档元数据与清理策略 | P1 | 删除一致性（对象+索引） |

### 4.6 Workflow（Execution + Nodes）
| 功能点 | 优先级 | 验收要点 |
|---|---|---|
| Workflow 定义/版本/发布 | P1 | 版本可回溯 |
| 变量系统（输入/输出/上下文） | P1 | 变量映射准确；作用域正确 |
| 执行控制（运行/暂停/重试/回放） | P1 | 失败可定位；可重试 |
| 节点插件化（见 6 节） | P1 | 节点可按租户安装 |
| 导入导出（YAML/JSON） | P2 | 模板可分享复用 |

### 4.7 可观测性（Observability）
| 功能点 | 优先级 | 验收要点 |
|---|---|---|
| TraceId 全链路 | P0 | 每次请求/执行有 TraceId |
| 运行日志（Workflow/Tool/LLM） | P0/P1 | 可按 trace/时间过滤 |
| 成本统计与报表（基础） | P1 | Token/费用聚合可查 |
| 指标与告警（后续） | P2/P3 | Prometheus/OTel 可选 |

### 4.8 记忆（Memory）
| 功能点 | 优先级 | 验收要点 |
|---|---|---|
| 短期记忆（会话窗口策略） | P2 | 可配置窗口/裁剪 |
| 长期记忆接口（向量+摘要） | P2 | 可插拔存储与检索策略 |
| 记忆注入策略 | P2 | 相关性可控；可观测 |

### 4.9 企业安全边界（Enterprise）
| 功能点 | 优先级 | 验收要点 |
|---|---|---|
| SSO（OIDC 优先） | P2 | 可对接企业 IdP |
| 审计日志（不可篡改方向） | P2 | 关键操作留痕 |
| 护栏（规则/脱敏/黑白名单） | P2 | 可配置策略；生效可验证 |
| Vault/KMS 适配 | P2 | Secret 生命周期可控 |

---

## 5. 每个里程碑的验收清单（Definition of Done）

### M0（P0）验收
- [ ] 多租户数据隔离（至少 tenant_id 全链路贯穿）
- [ ] Identity/RBAC 生效（含 API Key/JWT 任一）
- [ ] LLM/Tools/Vector/Storage Gateway 接口定稿并有最小实现
- [ ] Registry 支持插件注册与启停（最小生命周期）
- [ ] SSE 流式协议跑通（含错误/中断处理）
- [ ] 日志含 TraceId，可按 TraceId 查询

### M1（Chat）验收
- [ ] 创建会话、发送消息、分页查询消息
- [ ] 流式输出稳定（客户端断开处理正确）
- [ ] provider:model 路由可用
- [ ] 基础 token/成本可记录

### M3（Dataset）验收
- [ ] 上传→解析/切分→Embedding→向量入库
- [ ] 检索返回引用片段与来源
- [ ] 删除文档可同步清理索引与对象

### M5（Workflow）验收
- [ ] 最少 5 个节点插件可用（LLM/Tool/If/SetVar/HTTP）
- [ ] 运行历史可查，失败原因可定位
- [ ] 变量映射与上下文流转正确

---

## 6. Workflow 节点插件清单（建议首批）

> 节点按插件交付，可安装/卸载/升级；节点输入输出统一 schema。

### 6.1 基础控制类
- Start / End
- Set Variable（写入上下文）
- If / Switch（条件分支）
- Merge（分支汇聚）
- ForEach（遍历）
- Delay / Wait（延时）

### 6.2 LLM 类
- LLM Chat（文本）
- LLM JSON（结构化输出校验）
- LLM Tool-Calling（工具调用模式）

### 6.3 工具与集成类
- HTTP Request（支持签名/secret注入）
- Webhook Trigger（触发器）
- Tool Invoke（调用工具网关中已安装工具）

### 6.4 Dataset 类
- Dataset Retrieve（向量检索）
- Rerank（可选）
- Compose Answer（拼装引用）

### 6.5 数据处理类（后续）
- Text Transform（清洗/截断/模板）
- JSON Transform（映射/选择/合并）
- Code Runner（Python/JS，后续）

---

## 7. 技术实现约束（简要）

- **内核稳定**：Kernel 仅保留抽象、协议、执行与观测；具体实现放 adapters/plugins。
- **协议优先**：Gateway/Plugin 的输入输出尽量 schema 化，避免隐式耦合。
- **运行历史可追溯**：Workflow/Agent/Tool/LLM 全部落可查询记录（最小字段：trace_id、tenant_id、start/end、status、error、cost）。
- **安全默认开启**：secret 不入日志；工具调用权限与配额可控。

---

## 8. 附：建议的仓库文件名
- `DEVELOPMENT_PLAN.md`（本文）
- `ARCHITECTURE.md`（架构与核心原则）
- `PLUGIN_SPEC.md`（插件协议与 manifest/schema）
- `WORKFLOW_DSL.md`（工作流 DSL 与变量规范）
