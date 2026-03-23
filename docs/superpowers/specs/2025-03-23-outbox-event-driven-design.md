# SOIT 最小 Outbox 事件驱动改造 — 设计规格（定稿）

**日期**: 2025-03-23  
**状态**: 已定稿（brainstorming 一至四节合并；已按评审补充 Dispatcher 步骤、publisher 定位、Wave B/C 边界与 handler 事务说明）  
**依据**: `docs/SOIT_Minimal_Outbox_EventDriven_Design_Checklist.md`（Minimal / Converged Edition）

---

## 1. 目标与范围

### 1.1 设计目标

- **控制面**保持同步（Agent / Workflow / KB / 配置等 CRUD 与查询）。
- **执行面**渐进事件驱动：Run/Task、工作流节点调度、审批恢复、Trace/Audit/Cost 等。
- **Phase 1 使用 Outbox**，不引入 MQ；读模型保持精简，优先扩展核心表而非大量 summary 表。

### 1.2 分波顺序（已定稿）

采用 **A → B → C**：

| 阶段 | 名称 | 摘要 |
|------|------|------|
| **Wave A** | 基础设施与可靠投递 | `event_outbox`、`event_consumer_checkpoint`、可选 DLQ；Dispatcher、Registry、幂等与 checkpoint |
| **Wave B** | 执行面事实事件化 | Run/Task、Workflow、Approval 同事务写业务表 + outbox；缩短同步编排链 |
| **Wave C** | 可观测性订阅化 | Trace / Audit / Usage / Cost 迁出主路径，订阅 B 已稳定发出的事件 |

### 1.3 Phase 1 不包含

与清单 **§12** 一致：MQ、重型多 Agent 编排、完整 ingest/MCP 事件管线、大规模 projection/summary 体系。

---

## 2. 组件边界与数据流

### 2.1 分层职责

- **`api/`**：鉴权、校验、DTO、调用应用服务；**不**编排长执行链、**不**直接写 Outbox。
- **`app/kernel/events/`**（Wave A）：Envelope / DomainEvent、Outbox 模型与 repository、dispatcher、registry、幂等 + checkpoint 辅助。`kernel` **不依赖** `modules/`。
- **域应用服务 / runtime / workflow / approvals**：在**同一 DB 事务**内更新权威业务表并 **INSERT `event_outbox`**。
- **Dispatcher**：流程与清单 **§10** 对齐：
  1. 拉取 `pending` 且 `available_at <= now` 的事件；
  2. Claim 为 `processing`；
  3. 按 `event_type` 解析 handlers；
  4. **对每个 handler 执行前** 查 `event_consumer_checkpoint`；若该 `(consumer_name, event_id)` 已存在则 **skip**；
  5. 执行 handler；成功则 **write checkpoint**；
  6. 若**全部** handlers 成功（或均已 skip），将 outbox 行标为 `done`；
  7. 若失败：`attempt_count`、退避、`last_error`；超阈值则可选进 DLQ。
- **`publisher`（清单 §4）**：Phase 1 可由 **repository 的 enqueue API** 承担「同事务插入 outbox」职责；若实现中单独抽出 `publisher.py`，其职责仅为对 repository 的薄封装，**非额外抽象层**。
- **Handlers**：按清单建议分包（如 `kernel/runtime/handlers/`、`modules/workflow/handlers/` 等），**必须幂等**。

### 2.2 主数据流

```
Client → API → Application Service
              → BEGIN TX
              → 更新业务表
              → INSERT event_outbox
              → COMMIT
Dispatcher → handlers → 副作用 / 下一批事实事件
```

**事务说明**：上游「业务请求」事务与 **各 handler invocation** 分离（handler 在提交后运行）。**单个 handler 内部**若需更新权威业务状态并（可选）再插入新的 outbox 行，这些写入须在 **同一 handler 事务** 内原子完成；不得将同一 handler 内强一致依赖的写拆成多个无协调事务。

- **correlation_id**：默认以 `run_id` 串执行链（清单 **§5**）。
- **causation_id**：指向直接上游 `event_id`（清单 **§5**）。

### 2.3 与现有 EventBus / RedisEventBus 的边界

| 用途 | 策略 |
|------|------|
| 执行面事实、状态推进、审批恢复 | **仅** Outbox + Dispatcher |
| 可选实时 UI / 非关键通知 | 可保留 Redis/Memory Bus，**不得**作为唯一推进源；丢失可接受须文档化 |
| 迁移 | 凡需可靠投递的路径从 Bus 迁出；避免同一逻辑双语义 |

### 2.4 错误处理（概要）

- 业务事务失败：整单回滚，无 outbox 行。
- Handler 失败：依赖 outbox 重试 + checkpoint；永久失败进 DLQ。

### 2.5 测试挂钩

- Handler 对同一 `event_id` 重复调用 + checkpoint 行为可测。
- Wave A 起：outbox + dispatcher 集成测试；Wave B 起：关键链路透传；Wave C：可观测 consumer 幂等与重复投递断言。

---

## 3. 分波交付清单（映射清单 §13）

### 3.1 Wave A — 基础设施（§13.1）

| ID | 交付项 |
|----|--------|
| A1 | DomainEvent / envelope 基型与序列化（清单 **§5** 字段） |
| A2 | `event_outbox` 表、迁移、索引（**§7.1**） |
| A3 | `event_consumer_checkpoint`，唯一键 `(consumer_name, event_id)`（**§7.2**） |
| A4 | （推荐）`dead_letter_events`（**§7.3**） |
| A5 | Outbox repository |
| A6 | Handler registry |
| A7 | Dispatcher worker（**§10** 流程） |
| A8 | 幂等辅助 |
| A9 | （可选）`publisher` 薄封装，或与 A5 合并为同一 enqueue 表面 |
| A10 | 烟囱验收：同事务写入 → 异步消费 → 幂等重放 |

### 3.2 Wave B — 执行面（§13.2–13.4、§13.6 相关）

| ID | 交付项 |
|----|--------|
| B1 | Runtime：`run.*` / `task.*` 等事实事件（**§6.1**，按需启用） |
| B2 | 推进由 consumer 驱动；API 仅触发变更 + outbox（**§3、§14**） |
| B3 | Workflow 节点事件 + 调度 consumer（**§11.2**） |
| B4 | `workflow_runs` 计数等（**§8.2**） |
| B5 | Approval 事件与等待/恢复（**§11.3**） |
| B6 | 扩展 `runs`、按需 `workflow_runs`；核对 `approvals`（**§8**） |
| B7 | 验收：Run/Task、Workflow、Approval 三条链端到端；控制面仍同步（**§2.1、§12**） |

*说明：在 **Wave C 完成前**，主路径可**暂时**内联 Trace/Audit/Usage/Cost；**Wave C 仍属 Phase 1**，与清单 **§12、§13.5**（Trace / Audit / Cost subscribers）一致，目标是在 C 中**全部**迁出内联逻辑，而非推迟到 Phase 2。*

### 3.3 Wave C — 可观测性（§13.5、§11.4）

| ID | 交付项 |
|----|--------|
| C1 | trace / observability handlers 订阅执行/工作流/审批事件 |
| C2 | 主链移除深嵌 trace/audit/usage/cost |
| C3 | 新 consumer 幂等与 checkpoint 一致 |
| C4 | 验收：重复投递下无重复计费/审计/脏 trace（按现有语义定义） |

---

## 4. 风险、回滚与运维

### 4.1 风险与缓解

- **重复消费**：checkpoint + 幂等 handler。
- **乱序**：单条多 handler 顺序固定；跨事件用状态机守卫。
- **积压**：pending 深度、延迟、按类型分桶；扩展前明确 claim/租约策略。
- **双语义**：事实推进仅 Outbox；Bus 仅限明确 best-effort。
- **大 payload**：事件精简，大对象用引用（**§5**）。
- **Schema 演进**：`event_version` 与兼容策略。

### 4.2 回滚（概要）

- **A**：停 dispatcher；评估是否冻结 outbox 写入；已 `done` 行一般不删。
- **B**：特性开关或版本回滚 + 未消费 outbox playbook。
- **C**：恢复内联可观测，停用 handlers；B 链保持可用。

### 4.3 运维建议

- 指标：`outbox_pending_count`、processing 滞留、失败率、DLQ、按 `event_type` 分桶。
- 日志：`event_id`、`correlation_id`、`consumer_name`、`last_error`。
- 多实例：依赖原子 claim，避免双投。

---

## 5. 约束（清单 §14 摘录）

- API 不编排长执行链。
- 跨模块副作用优先事件订阅。
- 所有 consumers 幂等。
- Phase 1 用 Outbox，不上 MQ。
- 避免过早大量 summary 表；避免事件爆炸；事件描述**事实**而非命令。

---

## 6. 参考

- `docs/SOIT_Minimal_Outbox_EventDriven_Design_Checklist.md` — 全量清单与推荐目录结构（**§4**）。
