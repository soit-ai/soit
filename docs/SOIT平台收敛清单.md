# SOIT 收敛式精简清理清单

## 文档目的

本清单用于指导 SOIT 平台进行一轮**收敛式精简重构**。目标不是做温和兼容，而是基于当前已确定的长期蓝图，**主动删除历史包袱、统一核心语义、压缩冗余模型、清理兼容代码、收紧数据库结构**，让后续 Agent / Runtime / Workflow / Skill / Knowledge / Plugin / MCP 的演进建立在统一、干净、稳定的内核之上。

本次清理的总原则为：

1. **只保留新蓝图主语义**
2. **删除历史兼容层，不继续双轨并存**
3. **数据库只保留未来仍会继续演进的结构**
4. **允许破坏式重构，不为旧设计长期背负成本**

---

## 一、目标蓝图基线

本轮清理完成后，平台主语义统一收敛到以下对象：

* Agent
* Thread / Chat
* Task
* Run / RunStep / Artifact / Cost
* Response / ResponseEvent
* Workflow
* Skill
* Knowledge
* Plugin
* MCP
* Trace / Observability
* Tenant / Workspace / Membership

以下旧语义或过渡语义，原则上不再继续保留：

* App / Application
* Dataset
* 旧版独立 Chat 产品模型
* 临时 Binding 扩展语义
* 兼容旧 API 的 schema / DTO / facade
* 兼容旧路由的 redirect / adapter
* 只为迁移存在的 mapping / bridge / temp 表

---

## 二、清理原则

### 1. 语义唯一化

同一业务能力只能存在一套正式命名和一套正式模型，不允许出现以下情况长期并存：

* agent 与 app 同时表示“智能体主体”
* knowledge 与 dataset 同时表示“知识库主体”
* response event 与 message event 各自维护一套事件流
* run artifact 与其他临时 output 表重复表达执行产物
* plugin / tool / skill / mcp 在绑定关系中混乱重叠但无统一抽象

### 2. 不保留历史兼容层

本轮重构默认采用**破坏式收敛**策略：

* 不继续兼容旧 API 路径
* 不继续兼容旧表结构
* 不继续兼容旧字段
* 不继续兼容旧前端入口
* 不继续兼容旧命名对象
* 不继续保留过渡 mapper / adapter / facade

### 3. 先统一模型，再补能力

本轮重点不是继续扩业务，而是先做这几件事：

* 清语义
* 删旧代码
* 收表结构
* 统一绑定关系
* 收敛状态模型
* 清理前端信息架构

### 4. 面向未来演进保留结构

凡是未来仍可能支撑平台演进的核心结构应保留并强化，例如：

* Agent 主体与版本体系
* Thread / Task / Run / Response 统一执行账本
* Knowledge 完整文档与切片链路
* Workflow 编排定义与执行对接
* Skill 可复用能力抽象
* Plugin / MCP 扩展接入模型
* Trace / Artifact / Cost / Observability

---

## 三、总体清理范围

本次建议覆盖以下四个层面：

### A. 后端代码层

清理目标包括但不限于：

* legacy router
* redirect route
* compatibility facade
* old schema / dto
* mapper / adapter
* temp compatibility service
* old app/application service
* dataset compatibility service
* duplicated binding service
* deprecated response assembly logic

### B. 前端代码层

清理目标包括但不限于：

* 旧路由别名
* 旧门户菜单
* 独立 App 概念残留入口
* Dataset 相关菜单与页面命名
* 仅用于兼容旧接口的 hook / store / query
* 旧页面跳转页
* 已废弃但仍保留的 form/model 类型

### C. 数据库层

清理目标包括但不限于：

* 已被 Agent 替代的旧主体表
* 已被 Knowledge 替代的旧 Dataset 表
* 历史兼容字段
* 同义冗余字段
* 迁移过渡表
* 只服务于旧查询的索引
* 已失去业务意义的唯一约束、外键和状态枚举

### D. 文档与测试层

清理目标包括但不限于：

* README 中旧概念描述
* OpenAPI 中兼容旧命名的说明
* 测试目录中 legacy case
* seed/demo 数据中的旧对象
* migration 命名和注释中的旧语义
* 工程文档中的双轨概念

---

## 四、P0：必须优先执行的清理项

P0 的原则是：**先把主语义清干净，禁止旧世界继续渗透。**

### P0-1 统一主体命名：App / Application 全面收敛到 Agent

#### 清理目标

在全仓范围内排查并删除或改名以下对象：

* app
* apps
* application
* applications
* app_version
* application_version
* app_binding
* app_publish
* app_component
* app_runtime
* app_chat
* app_session

#### 执行动作

1. 所有仍表达“智能体主体”的 app/application 命名统一改为 agent
2. 所有文案、DTO、service、repo、路由、前端 store、hook 中的旧命名统一替换
3. 删除仅用于兼容旧 app 语义的 facade / redirect / alias
4. 迁移脚本中如果仍存在旧表兼容保留策略，直接转为 drop 或 rename 完成态

#### 验收标准

* 新代码中不再允许出现表示主体语义的 app/application 命名
* 外部接口仅暴露 agent 语义
* 前端仅保留 Agent 入口与概念

---

### P0-2 统一知识命名：Dataset 全面收敛到 Knowledge

#### 清理目标

在全仓范围内排查并删除或改名以下对象：

* dataset
* datasets
* dataset_document
* dataset_chunk
* dataset_index
* dataset_embedding
* dataset_retrieval
* dataset_search
* dataset_binding

#### 执行动作

1. 所有知识库主语义统一改为 knowledge
2. 历史 dataset -> knowledge 的兼容转换逻辑全部删除
3. 删除旧 API / DTO / service / repo / UI 页面中的 dataset 残留
4. 数据库层面不再保留 dataset 兼容表或兼容字段
5. 检查 seed、fixture、测试数据是否仍生成 dataset 相关对象并清理

#### 验收标准

* 平台对外只有 knowledge 概念
* 代码中 dataset 仅允许出现在历史迁移注释，不允许继续出现在运行时代码中
* 前端菜单、页面、文案、接口路径全部统一为 knowledge

---

### P0-3 删掉历史兼容路由与 API 别名

#### 清理目标

删除以下类型接口：

* `/apps/*` 兼容路由
* `/applications/*` 兼容路由
* `/datasets/*` 兼容路由
* 旧 chat API 兼容路径
* 旧 response 结构兼容接口
* 旧 workflow 版本入口别名
* 旧 plugin/tool 暂时双入口

#### 执行动作

1. 审核所有 router，识别仅用于兼容旧前端或旧命名的路径
2. 直接删除旧路径，不保留 redirect
3. 更新前端请求统一指向新路径
4. OpenAPI 中删除兼容接口定义

#### 验收标准

* API 文档只保留新蓝图下的标准路径
* 后端不再维护旧接口
* 前端不再请求旧路径

---

### P0-4 删除 compatibility / legacy / adapter / facade 代码

#### 清理目标

重点排查目录和对象名称：

* `legacy`
* `compat`
* `compatibility`
* `adapter`
* `bridge`
* `facade`
* `deprecated`
* `migration_helper`
* `alias_service`
* `shim`

#### 执行动作

1. 全仓检索上述关键词
2. 将代码分为三类：

   * 确认仅为兼容旧系统存在：直接删除
   * 实际承担正式业务：并入正式 service
   * 只做字段映射：让调用方改造后删除
3. 所有新蓝图中无必要的兼容层全部删除

#### 验收标准

* 核心业务代码不再绕过 facade / adapter 才能工作
* 服务调用链路直接、清晰
* 旧语义 mapper 不再存在

---

### P0-5 清除旧前端入口与历史门户

#### 清理目标

前端信息架构统一到新蓝图，不再保留历史门户残影，重点清理：

* App 页面入口
* Dataset 页面入口
* 历史独立 Chat 产品入口
* 过时的 redirect 页面
* 旧 layout 菜单项
* 临时兼容的页面 alias

#### 执行动作

1. 侧边栏统一为新蓝图入口集合
2. 删除不再保留的旧产品入口
3. Chat 收敛为 Agent 默认交互，不再作为平行产品域长期保留旧概念
4. 页面路径、breadcrumb、文案全部统一

#### 验收标准

* 前端导航不再出现旧产品概念
* 页面入口与后端资源语义完全一致
* 用户看不到平台内部的历史过渡设计

---

## 五、P1：建议本轮同步完成的结构收敛项

P1 的原则是：**把关键运行时和扩展模型彻底统一，避免后面继续返工。**

### P1-1 统一 Agent Binding 体系

#### 当前问题

Agent 虽然已经是主体，但 binding 常常只覆盖：

* model
* tool
* knowledge
* workflow
* skill
* tool

而 Skill / Workflow / Tool 未完全进入统一绑定体系。

#### 目标结构

建议将 Agent Binding 统一收敛为正式能力绑定模型，支持以下类型：

* model
* knowledge
* workflow
* skill
* tool


#### 执行动作

1. 统一 binding 表或 binding schema
2. 去掉临时字段、临时扩展、临时枚举
3. 每种绑定关系都要有明确 target_type / target_id / version 规则
4. 删除重复表达同类绑定关系的中间表

#### 验收标准

* Agent 真正成为统一编排入口
* 不再存在“某能力只能通过特殊字段挂载”的情况
* Skill / Workflow / MCP 能正式成为 Agent 可调度能力

---

### P1-2 收敛运行时结果模型

#### 当前问题

平台在执行产物层面容易出现多种“结果对象”并行，例如：

* response output
* message payload
* run artifact
* temporary step output
* workflow node output snapshot

#### 目标结构

统一把执行结果收敛到以下核心链路：

* Run
* RunStep
* RunArtifact
* Response
* ResponseEvent
* Trace

#### 执行动作

1. 明确什么属于 Artifact，什么属于 ResponseEvent
2. 删除临时 snapshot 表或重复 output 表
3. run step 输出统一通过标准 schema 表达
4. 不再让 message 表承担复杂执行结果存储语义

#### 验收标准

* 任何执行产物都能在统一账本中找到归属
* 没有平行的结果表体系
* Trace、Artifact、ResponseEvent 的边界清晰

---

### P1-3 统一状态字段和枚举

#### 清理目标

排查以下对象上的状态字段：

* agent status
* task status
* run status
* step status
* response status
* event status
* workflow publish status
* skill publish status
* approval status

#### 执行动作

1. 统一命名风格，如 `status`、`lifecycle_status`、`publish_status`
2. 去掉同义状态：

   * active / enabled / available 混用
   * archived / deleted / removed 混用
   * pending / queued / created 表义不清
3. 明确运行态和发布态分层
4. 清除只为旧流程保留的状态值

#### 验收标准

* 状态体系统一、可解释
* 不存在历史流程遗留状态
* 前后端枚举口径一致

---

### P1-4 MCP 从“注册对象”收敛到“运行时能力对象”

#### 当前问题

MCP 往往先有 server 管理，但缺少深度进入 runtime 的能力模型。

#### 执行动作

1. 明确 MCP 在平台中的正式位置：

   * 扩展接入层
   * Agent 可绑定能力来源
   * Runtime 可调用外部能力通道
2. 清除仅做 catalog 展示的临时字段和过渡接口
3. 将 MCP 的能力发现、能力缓存、权限控制、审计挂入正式链路
4. 删除临时试验用的 MCP metadata 字段

#### 验收标准

* MCP 不是纯后台配置对象
* MCP 能作为 Agent/Runtime 的正式能力来源
* 审批、审计、权限与运行态挂通

---

### P1-5 Skill 从“资源对象”收敛到“复用能力层”

#### 当前问题

Skill 容易被实现成单纯的 CRUD 资源，而不是正式复用层。

#### 执行动作

1. 清理 Skill 中仅为展示或试验保留的字段
2. 统一 Skill Version / Publish / Invocation 模型
3. 去掉与 Plugin、Workflow、Tool 重复表达的字段
4. 让 Skill 能明确作为：

   * Agent 可绑定能力
   * Workflow 可引用节点能力
   * 业务域可复用执行单元

#### 验收标准

* Skill 不再只是“一个资源页”
* Skill 有明确运行时地位
* Skill 与 Plugin / MCP / Workflow 的边界清晰

---

## 六、P2：后续可继续补充的清理项

P2 的原则是：**补齐工程整洁度，防止旧语义再回流。**

### P2-1 清理迁移命名和历史注释

清理对象包括：

* Alembic migration 名称中的 app / dataset 旧命名
* 注释中“暂时兼容旧版本”的描述
* README 中旧架构介绍
* 工程文档中的双轨表达

原则：

* 可读性优先
* 避免新成员被历史命名误导
* 不强求重写全部历史迁移，但新迁移不得继续使用旧语义

---

### P2-2 清理测试中的 legacy case

清理对象包括：

* 旧 API 的集成测试
* dataset 兼容测试
* app/application 命名测试
* redirect 路由测试
* 兼容旧 response schema 的断言

原则：

* 只保留新蓝图的正式行为测试
* 不再为已废弃能力维护测试成本

---

### P2-3 清理 seed / fixture / demo data

清理对象包括：

* 旧 app demo
* dataset demo
* 兼容旧字段的 fixture
* 临时 workflow / plugin / skill 样例
* 文案和 metadata 中旧概念残留

原则：

* 演示数据必须体现新蓝图
* 不能再生成历史对象误导开发

---

### P2-4 清理前端文案与 UI 命名残留

清理对象包括：

* App / Application 文案
* Dataset 文案
* 独立 Chat 产品旧文案
* 旧菜单标题
* 模态框、表单、按钮名称中的历史词汇

原则：

* UI 文案必须和领域模型一致
* 不允许“数据库叫 Agent，前端还叫 App”

---

## 七、数据库专项清理清单

以下为数据库层的重点收敛要求。

### 7.1 应删除的表类型

#### A. 旧主体表

凡是以下语义仍残留，应评估直接删除或迁移完成后删除：

* app / apps
* application / applications
* app_versions
* application_versions
* app_bindings
* app_components
* app_runtime_sessions
* app_publishes

#### B. 旧知识表

* dataset
* datasets
* dataset_documents
* dataset_chunks
* dataset_indexes
* dataset_embeddings
* dataset_bindings
* dataset_search_logs

#### C. 过渡 mapping / bridge 表

* app_to_agent_mapping
* dataset_to_knowledge_mapping
* compatibility_bindings
* legacy_resource_refs
* transitional_summary_tables
* migration_bridge_tables

#### D. 冗余结果表 / 临时快照表

* temporary_step_outputs
* duplicated_run_outputs
* workflow_node_snapshot_tables
* legacy_chat_response_tables
* 临时 projection 表（若已无消费者）

---

### 7.2 应删除的字段类型

#### A. 兼容旧命名字段

例如：

* `app_id`（语义上已应改为 `agent_id`）
* `dataset_id`（语义上已应改为 `knowledge_id`）
* `application_type`
* `legacy_app_ref`
* `old_dataset_ref`

#### B. 同义冗余字段

例如同一对象中同时存在：

* `status` 与 `is_enabled`
* `published` 与 `publish_status`
* `deleted_at` 与 `is_deleted`
* `metadata` 与 `extra_metadata` 与 `config_payload`
* `name` 与 `title` 表义重复却未定义边界

#### C. 仅历史展示用字段

* 不再写入但仍保留的旧统计字段
* 不再参与运行态的 legacy summary 字段
* 历史 UI 兼容字段
* 为旧导出接口保留的扁平字段

#### D. 试验性字段

* 仅服务某次临时方案的 config
* 未正式进入运行态的实验列
* 已无现行代码读取的 JSON 扩展字段

---

### 7.3 应收紧的约束

#### A. 非空约束

对于已成为正式主链路的字段，应补齐 `NOT NULL`：

* agent 主体关联字段
* thread / task / run 主链路外键
* binding target_type / target_id
* response / response_event 关键关联字段
* publish 状态关键字段

#### B. 唯一约束

需要根据正式业务语义重建唯一约束，例如：

* 同一 workspace 下唯一 slug
* 同一 agent version 唯一版本号
* 同一 publish channel 唯一生效版本
* 同一 binding 唯一 target 组合
* 同一知识文档唯一业务键

#### C. 外键约束

删除历史兼容弱关联，保留正式强关联：

* 旧 app -> agent 的软关联删除
* dataset -> knowledge 的过渡弱关联删除
* 运行账本全链路外键明确化
* Artifact / Trace / Cost 与 Run 主链挂紧

#### D. 索引清理

删除以下类型索引：

* 只为旧路由查询服务的索引
* 已废弃表上的索引
* 重复索引
* 宽泛 JSON 检索试验索引
* 已不符合当前查询路径的过时联合索引

---

## 八、前后端命名统一清单

### 8.1 必须统一到新蓝图的名词

| 旧名词               | 新名词                 |
| ----------------- | ------------------- |
| App / Application | Agent               |
| Dataset           | Knowledge           |
| App Publish       | Agent Publish       |
| App Version       | Agent Version       |
| App Binding       | Agent Binding       |
| Dataset Document  | Knowledge Document  |
| Dataset Chunk     | Knowledge Chunk     |
| App Chat          | Agent Chat / Thread |
| App Session       | Thread / Task / Run |

### 8.2 前端菜单建议统一为

* Agents
* Chat
* Workflows
* Skills
* Knowledge
* Plugins
* MCP
* Tasks
* Runs / Observability
* Models
* Settings

### 8.3 禁止继续新增的历史命名

以下命名从本轮开始禁止在新代码中继续出现：

* app*
* application*
* dataset*
* legacy*
* compatibility*
* adapter*
* bridge*
* deprecated*
* old_*
* temp_*（正式业务代码中）

---

## 九、建议执行顺序

### Phase 1：冻结目标模型

输出唯一正式模型边界：

* Agent
* Thread / Task / Run / Response / Artifact / Trace
* Workflow
* Skill
* Knowledge
* Plugin
* MCP

要求：

* 以后代码不允许新增旧概念
* 所有新开发都必须遵守该语义基线

---

### Phase 2：全仓盘点

输出四份盘点清单：

1. 旧表清单
2. 旧字段清单
3. 兼容接口清单
4. 兼容代码目录清单

要求：

* 每项标注“删除 / 合并 / 改名 / 保留”
* 不允许含糊写“先留着”

---

### Phase 3：先删代码，再删数据库

建议顺序：

1. 删除前端旧入口、旧请求
2. 删除后端旧 router / service / schema / facade
3. 删除兼容测试
4. 执行数据库迁移，drop / rename / merge
5. 补新测试和文档

原则：

* 不要先删库再让代码临时适配
* 优先让代码世界完成收敛，再做结构落地

---

### Phase 4：统一迁移与约束收紧

迁移动作建议一次性完成：

* rename 的 rename
* merge 的 merge
* drop 的 drop
* not null 的补 not null
* unique / foreign key / index 的统一收紧

原则：

* 不做长期过渡列
* 不做双写双读
* 不再保留 shadow schema

---

### Phase 5：补测试、文档、示例

最终只保留新蓝图内容：

* 测试仅覆盖正式能力
* README 仅解释当前架构
* OpenAPI 仅暴露正式接口
* demo/seed 仅生成当前模型

---

## 十、执行约束

本轮清理必须遵守以下约束：

1. **不新增新的兼容层**
2. **不保留“以后可能还会用”的旧字段**
3. **不允许前后端语义不一致**
4. **不允许数据库结构继续容纳双模型**
5. **不允许测试继续维护已废弃能力**
6. **不允许用 adapter/facade 掩盖模型设计问题**
7. **不允许为短期迁移便利牺牲长期语义纯度**

---

## 十一、最终目标状态

清理完成后，SOIT 应达到以下状态：

### 1. 领域语义纯净

平台主语义只剩：

* Agent
* Workflow
* Skill
* Knowledge
* Plugin
* MCP
* Thread / Task / Run / Response / Artifact / Trace

### 2. 代码调用链清晰

* 没有历史 facade
* 没有兼容 adapter
* 没有双轨 service
* 没有旧路由 alias

### 3. 数据库结构收敛

* 没有 app / dataset 旧主体表
* 没有历史兼容字段
* 没有过渡 mapping 表
* 没有重复状态和重复结果表

### 4. 前端信息架构统一

* 菜单与领域模型一致
* Chat 是 Agent 默认交互模式
* 不再存在旧产品门户概念

### 5. 为下一阶段演进铺平道路

在完成本轮收敛后，平台才适合继续深做以下方向：

* Agent 统一调度 Workflow / Skill / Plugin / MCP
* Runtime 正式事件驱动化
* Skill 成为复用能力层
* MCP 深度进入运行时
* Observability / Artifact / Trace 进一步强化
* 多 Agent 协作和 A2A 能力接入

---

## 十二、结论

SOIT 当前最需要的，不是继续叠加新功能，而是做一轮**去历史兼容、去旧业务、去过渡结构、去双轨语义**的收敛式精简重构。

本轮工作的核心不是“优化”，而是：

* 删旧
* 并语义
* 收模型
* 紧约束
* 断兼容

只有完成这轮清理，SOIT 才能真正从“架构方向已对”进入“平台底座可持续演进”的状态。
