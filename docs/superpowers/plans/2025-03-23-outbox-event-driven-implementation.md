# Outbox 事件驱动（Phase 1，A→B→C）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 SOIT-Pro 后端落地事务型 Outbox、Dispatcher 与幂等消费，再逐步将执行面改为事实事件驱动，最后把 Trace/Audit/Usage/Cost 迁出主链为订阅者。

**Architecture:** 业务用例在 **同一 SQLAlchemy Session 事务** 内写权威表 + `event_outbox`；独立 **OutboxDispatcher** 循环（模式对齐 `app/main.py` 中 `GlobalKnowledgeIngestWorker`）拉取、claim、按注册表调 handler，**逐 handler 前查 `event_consumer_checkpoint`**。模块事件类型常量放在各域，kernel 仅提供管道与类型无关的存储。现有 `InMemoryEventBus`/`RedisEventBus` 保留给 **best-effort** 场景，执行面事实推进以 Outbox 为准（见规格 §2.3）。

**Tech Stack:** Python 3.x、FastAPI、SQLModel/SQLAlchemy、Alembic、`uv`（工作目录 **`server/`**）、pytest。

**规格依据:** `docs/superpowers/specs/2025-03-23-outbox-event-driven-design.md`、`docs/SOIT_Minimal_Outbox_EventDriven_Design_Checklist.md`

**必读工程文档:** `server/docs/architecture/PROJECT_STRUCTURE.md`（边界：kernel 不依赖 modules）

---

## 文件结构总览（创建 / 修改）

| 路径 | 职责 |
|------|------|
| `server/app/kernel/events/envelope.py` | Domain 事件 envelope 与序列化（规格 §5 字段） |
| `server/app/kernel/events/outbox_models.py` | SQLModel：`EventOutboxRow`、`EventConsumerCheckpoint`、可选 `DeadLetterEvent` |
| `server/app/kernel/events/outbox_repo.py` | enqueue、fetch pending、claim、mark done/failed、DLQ（**规格 A9**：`publisher.py` 不单独建文件，enqueue 由本模块承担） |
| `server/app/kernel/events/checkpoint.py` | 查询/写入 checkpoint 辅助 |
| `server/app/kernel/events/registry.py` | `event_type` → 有序 handler 列表 |
| `server/app/kernel/events/dispatcher.py` | 规格 §10 七步循环（异步） |
| `server/app/kernel/events/__init__.py` | 导出公共 API（与现有 `bus` 并存） |
| `server/alembic/versions/<new>_event_outbox_tables.py` | 新表与索引 |
| `server/app/settings/settings.py`（或等价） | `outbox_dispatcher_enabled`、poll 间隔、batch size、max_attempts |
| `server/app/main.py` | lifespan 内可选 `asyncio.create_task(dispatcher.run_loop(...))` |
| `server/app/wiring/outbox_handlers.py`（或 `kernel/events/bootstrap.py`，路径实现时二选一） | **组合根**：启动时注册全部 outbox handlers（含 Wave A 烟囱测试用 handler） |
| `server/app/kernel/runtime/handlers/` | Wave B：runtime 相关 outbox handlers（按需拆分文件） |
| `server/app/modules/workflow/handlers/` | Wave B：workflow 调度 handler |
| `server/app/modules/approvals/handlers/` | Wave B：approval resume handler |
| `server/app/kernel/trace/handlers/`、`server/app/kernel/observability/handlers/` | Wave C：订阅消费 |
| `server/tests/unit/test_outbox_*.py` | repository、registry、dispatcher 行为 |
| `server/tests/integration/test_outbox_dispatch.py`（或同级） | 烟囱：同事务写入 + 消费 |

**修改热点（Wave B/C，按实际代码调整路径）：**

- `server/app/kernel/runtime/core/service.py`、`repository.py` — 事务内 enqueue
- `server/app/modules/workflow/` 下执行/调度入口 — 发工作流节点事实事件
- `server/app/modules/` 下审批相关服务 — 发审批事件
- `server/app/kernel/trace/`、`server/tests/test_trace_emission.py` — Wave C 迁出内联写入

---

## Wave A — 基础设施

### Task A1: Envelope 与 event_type 常量骨架

**Files:**
- Create: `server/app/kernel/events/envelope.py`
- Test: `server/tests/unit/test_outbox_envelope.py`

- [x] **Step 1: 写失败测试** — 断言 dataclass/Pydantic 模型序列化往返后关键字段一致（`event_id`, `event_type`, `event_version`, `tenant_id`, `correlation_id`, `payload`）。

- [x] **Step 2: 运行测试确认失败**

```bash
cd server
uv run pytest tests/unit/test_outbox_envelope.py -v
```

Expected: FAIL（模块不存在或未实现）

- [x] **Step 3: 最小实现** — 使用与项目一致的模型风格（可与现有 `app/kernel` 中 schema 风格对齐）；**代码注释使用英文**（工作区规则）。

- [x] **Step 4: 测试通过**

```bash
uv run pytest tests/unit/test_outbox_envelope.py -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add server/app/kernel/events/envelope.py server/tests/unit/test_outbox_envelope.py
git commit -m "feat(outbox): 增加领域事件 envelope 与单测"
```

---

### Task A2: Alembic 迁移 — event_outbox、event_consumer_checkpoint、dead_letter（推荐）

**Files:**
- Create: `server/alembic/versions/<timestamp>_event_outbox_tables.py`
- Modify: 无（若需注册模型进 `env.py`/`create_tables` 按现有惯例）

- [x] **Step 1:** 运行 `cd server && uv run alembic heads` 确认当前 head revision id。

- [x] **Step 2:** 新建 migration，`down_revision` 指向当前 head；按规格 **§7.1–7.3** 创建表与索引（`status+available_at`、`correlation_id`、`subject_type+subject_id`、`run_id`、`workflow_run_id`）。

- [x] **Step 3:** `uv run alembic upgrade head` 在本地开发库验证（或 `alembic upgrade head --sql` 检视）。

- [x] **Step 4: Commit**

```bash
git add server/alembic/versions/
git commit -m "feat(db): 新增 event_outbox 与 consumer checkpoint 表"
```

---

### Task A3: SQLModel 与 OutboxRepository

**Files:**
- Create: `server/app/kernel/events/outbox_models.py`
- Create: `server/app/kernel/events/outbox_repo.py`
- Test: `server/tests/unit/test_outbox_repository.py`

- [x] **Step 1: 失败测试** — 使用项目现有 DB fixture（若存在）或 `sqlite` 内存引擎：在同一 session 内 `enqueue` 后 `flush`，再 `fetch_pending` 能取到 `pending` 行；`claim` 后状态为 `processing`。

- [x] **Step 2: 运行测试确认失败** — `uv run pytest tests/unit/test_outbox_repository.py -v` → FAIL

- [x] **Step 3: 实现** — `enqueue(...)` 仅 `session.add`，**不**在 repo 内 `commit`（由调用方控制事务）。提供原子 `claim`（`UPDATE ... WHERE id=? AND status='pending'` 或等价）。

- [x] **Step 4: 运行测试确认通过** — `uv run pytest tests/unit/test_outbox_repository.py -v` → PASS

- [x] **Step 5: Commit** — `feat(outbox): Outbox 模型与 repository`

---

### Task A4: Checkpoint 辅助

**Files:**
- Create: `server/app/kernel/events/checkpoint.py`
- Test: `server/tests/unit/test_outbox_checkpoint.py`

- [x] 测试：`has_processed(consumer_name, event_id)` 在插入一行后为 True；唯一约束冲突时行为明确（插入失败则视为已存在，由调用方 skip）。

- [x] 实现：封装 `try_insert_checkpoint` / `is_processed`。

- [x] `uv run pytest tests/unit/test_outbox_checkpoint.py -v` → PASS

- [x] Commit: `feat(outbox): consumer checkpoint 辅助`

---

### Task A5: Handler Registry

**Files:**
- Create: `server/app/kernel/events/registry.py`
- Test: `server/tests/unit/test_outbox_registry.py`

- [x] 注册多个 handler 同一 `event_type`，`get_handlers` 返回顺序稳定（注册顺序）。

- [x] Commit: `feat(outbox): handler 注册表`

---

### Task A6: Dispatcher（规格 §10）

**Files:**
- Create: `server/app/kernel/events/dispatcher.py`
- Test: `server/tests/unit/test_outbox_dispatcher.py`

- [x] 实现异步 `process_batch()`：对每条 outbox 行，对每个 handler：**先 checkpoint 查询 → skip 或执行 → 成功则写 checkpoint**；全部 handler 成功后 `mark_done`；任一步异常则 `mark_retry`/`last_error`/`attempt_count`，超阈值 `dead_letter`（若表存在）。

- [x] 单元测试使用 **fake session** 或 mock repo，覆盖：双 handler、第二个失败时第一个 checkpoint 已写入且不丢、重入时 skip。

- [x] `uv run pytest tests/unit/test_outbox_dispatcher.py -v` → PASS

- [x] Commit: `feat(outbox): dispatcher 与单测`

---

### Task A7: 配置、handler 引导（composition root）与 lifespan 挂载

**Files:**
- Modify: `server/app/settings/settings.py`（或实际配置模块）
- Modify: `server/app/main.py`
- Create: `server/app/wiring/outbox_handlers.py`（或 `server/app/kernel/events/bootstrap.py`）

- [x] 增加 `outbox_dispatcher_enabled: bool = False`、`outbox_dispatcher_poll_interval: float`、`outbox_dispatcher_batch_size: int` 等。

- [x] **实现 `register_outbox_handlers()`**（名称自定）：至少注册 **A8 烟囱测试** 所需 `event_type` 与占位 handler；Wave B/C 完成后在同一入口追加注册，避免「dispatcher 空转」。

- [x] 在 `lifespan` 启动时 **先调用** `register_outbox_handlers()`，再若 enabled 则 `asyncio.create_task(OutboxDispatcher(...).run_loop(...))`，shutdown 时 cancel（**照抄** knowledge worker 的 cancel 模式，见 `main.py` 约 80–104 行）。

- [x] 手动验证：启动 API + 启用 flag，日志无异常循环。

- [x] Commit: `feat(outbox): 可配置启动 dispatcher 与 handler 注册`

---

### Task A8: 集成烟囱测试

**Files:**
- Create: `server/tests/integration/test_outbox_dispatch.py`

- [x] 在同一测试中：开启测试 DB、插入一行业务占位（可选）、**同事务** enqueue 一条真实 `event_outbox`、commit；运行 dispatcher 一轮；断言测试 handler 副作用（如测试表计数）且 outbox 为 `done`。

- [x] `uv run pytest tests/integration/test_outbox_dispatch.py -v` → PASS

- [x] Commit: `test(outbox): dispatcher 端到端烟囱测试`

> **A9**：`publisher.py` 薄封装已落地（与 A3/A5 衔接）。  
> **A10**：幂等重放与 `OutboxDispatcherService` 已覆盖于 `tests/integration/test_outbox_dispatch.py`。

---

## Wave B — 执行面事件化（按链渐进，多条 PR 可拆分）

### Task B1: 事件类型常量与 Runtime 首条链（示例：run.created）

**Files:**
- Create: `server/app/kernel/runtime/events.py`（`RunEventType` 等字符串常量）
- Modify: 实际创建 `runs` 的服务（需在代码库中 `rg "runs"` / `create_run` 定位，例如 modules 下 run 服务）
- Modify: 上述服务所用 session：**提交前** `outbox_repo.enqueue` 同事务

- [x] 定义最小集合：先 **仅** `run.created`（或规格 §6.1 中与当前主链重合的 1–2 个）。

- [x] 注册 handler：例如 `server/app/kernel/runtime/handlers/on_run_created.py`，在 **`register_outbox_handlers()`**（见 Task A7）中注册到 registry（避免 kernel import modules：handler 可放在 kernel/runtime/handlers，内部仅调 ports/已有服务）。

- [x] 集成测试：创建 run 的 API 或 service 调用后，dispatcher 处理完毕的观测断言（可轮询 DB）。

- [x] Commit: `feat(runtime): run.created 写入 outbox 并由 handler 消费`

---

### Task B2: Task 生命周期事件与状态机推进

**Files:**
- Modify: task 状态迁移集中点（`RuntimeCoreService` 或 task 执行器）
- Create/Modify: `server/app/kernel/runtime/handlers/` 下对应 handlers

- [x] 按规格 §6.1 逐步加入 `task.*`，**YAGNI**：仅对接当前代码路径会触发的状态。

- [x] 每加一个事件：`uv run pytest server/tests/unit/test_runtime_* server/tests/integration/...` 回归。

- [x] Commit（可多个）：`feat(runtime): task 生命周期 outbox 事件`

---

### Task B3: Workflow 节点调度

**Files:**
- Modify: `server/app/modules/workflow/` 下节点完成/失败路径
- Create: `server/app/modules/workflow/handlers/scheduler.py`（名称自定）

- [ ] 发 `workflow.node.completed` / `workflow.node.failed`；consumer 调度下一节点（规格 §11.2）。

- [ ] 更新 `workflow_runs` 计数字段（规格 §8.2），**同事务或单 handler 事务**内完成。

- [ ] 回归：在 `server/tests` 下用 `rg workflow` / 现有 CI 已跑的文件列出命令，例如 `uv run pytest tests/unit/test_workflow_executor.py -v`（**若文件不存在则换为实际路径**）

- [ ] Commit: `feat(workflow): 节点事件与调度 consumer`

---

### Task B4: Approval 请求与恢复

**Files:**
- Modify: `server/app/modules/observability/infra/repository.py`、`application/service.py`
- Create: `server/app/modules/observability/domain/approval_events.py`、`infra/approval_outbox_emit.py`、`handlers/on_approval_outbox.py`；`server/app/wiring/outbox_handlers.py` 注册

- [x] `approval.requested` / `approval.approved` / `approval.rejected`（§6.3）；consumer 对 `waiting_approval` 任务：`approved` → `resume_task`，`rejected` → `transition_task` FAILED（§11.3 任务路径；workflow 节点后续在 B3/B6）。

- [x] 回归：`tests/integration/test_approval_outbox_resume.py`

- [ ] Commit: `feat(approvals): 审批事件与恢复路径`

---

### Task B5: 表字段扩展 runs / workflow_runs

**Files:**
- New migration: `server/alembic/versions/20260323120000_runs_workflow_runs_b5.py`
- Modify: `server/app/kernel/trace/models.py`（`Run`）、`server/app/modules/workflow/domain/models.py`（`WorkflowRun`）、`server/app/kernel/runtime/core/service.py`（`transition_task` 同事务更新 headline）

- [x] 按规格 **§8.1–8.2**：`runs.current_task_id`、`runs.last_error`；新建 `workflow_runs` 及计数列；nullable，由应用层写入（见 migration 顶部说明）。

- [ ] Commit: `feat(db): 扩展 runs/workflow_runs 查询字段`

---

### Task B6: 规格 B7 端到端验收（Run/Task + Workflow + Approval）

- [x] 集成测试 `tests/integration/test_outbox_phase1_execution_chains.py`：`run.created` → dispatch `done`；`task.created`/`started`/`completed` 全部 `done`；`workflow.node.completed` consumer 递增 `workflow_runs` 计数并在 payload 含 `next_node_id` 时入箱下一节点事件（第二条消费后计数与 outbox 一致）；`approval.approved` 后 `waiting_approval` 任务恢复为 `running`。执行器内自动发节点事件仍属 **B3**，本链路由测试入箱模拟上游事实。

- [x] 命令：

```bash
cd server
uv run pytest tests/integration/test_outbox_phase1_execution_chains.py -v
```

- [x] Commit: `test(outbox): B6 Phase1 执行链集成测试与 workflow.node.completed 消费端`

---

## Wave C — 可观测性订阅

### Task C1: Trace/Audit/Usage/Cost handlers

**Files:**
- Create: `server/app/kernel/trace/handlers/`、`server/app/kernel/observability/handlers/`
- Modify: 当前内联写入点（从 `test_trace_emission.py`、`trace/writer.py` 等顺藤摸瓜）

- [ ] 为每类 side effect 注册 **稳定 consumer_name**；逻辑保持幂等（重复 `event_id` 不重复写审计行，或依赖业务唯一键）。

- [ ] 回归：用 `rg trace|audit` 在 `server/tests` 定位后运行对应 `pytest`（**勿硬编码不存在的路径**）

- [ ] Commit: `refactor(observability): trace/audit/cost 改为 outbox 订阅`

---

### Task C1b: 重复投递 / 幂等集成测试（规格 C3、C4、§2.5）

**Files:**
- Create: `server/tests/integration/test_outbox_observability_idempotency.py`（名称自定）

- [ ] **同一 `event_id` + 同一 `consumer_name`**：手动插入 checkpoint 或跑两轮 dispatcher，断言审计/usage/trace **无重复行**（或符合业务唯一约束）。

- [ ] `uv run pytest tests/integration/test_outbox_observability_idempotency.py -v` → PASS

- [ ] Commit: `test(outbox): 可观测 consumer 重复投递幂等`

---

### Task C2: 清理主路径内联与文档注释

- [ ] 删除或降级为「仅 debug」的内联调用；在关键入口文件顶部 **英文注释** 说明：执行事实以 Outbox 为准。

- [ ] Commit: `chore(outbox): 移除主链可观测内联写入`

---

## 全量回归

- [ ] `cd server && uv run pytest` — 全绿后再合并 Wave。

---

## 计划审阅与执行方式

本计划写完后应由独立审阅者对照 `docs/superpowers/specs/2025-03-23-outbox-event-driven-design.md` 检查：事务边界、§10 顺序、Phase 1 范围、与现有 `EventBus` 边界。

---

**Plan complete and saved to `docs/superpowers/plans/2025-03-23-outbox-event-driven-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — 每个 Task 派生子代理执行，任务间人工或自动 review，迭代快。

**2. Inline Execution** — 本会话用 executing-plans 按检查点批量执行。

**Which approach?**
