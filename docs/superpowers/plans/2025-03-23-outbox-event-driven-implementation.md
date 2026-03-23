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
| `server/app/kernel/events/outbox_repo.py` | enqueue、fetch pending、claim、mark done/failed、DLQ |
| `server/app/kernel/events/checkpoint.py` | 查询/写入 checkpoint 辅助 |
| `server/app/kernel/events/registry.py` | `event_type` → 有序 handler 列表 |
| `server/app/kernel/events/dispatcher.py` | 规格 §10 七步循环（异步） |
| `server/app/kernel/events/__init__.py` | 导出公共 API（与现有 `bus` 并存） |
| `server/alembic/versions/<new>_event_outbox_tables.py` | 新表与索引 |
| `server/app/settings/settings.py`（或等价） | `outbox_dispatcher_enabled`、poll 间隔、batch size、max_attempts |
| `server/app/main.py` | lifespan 内可选 `asyncio.create_task(dispatcher.run_loop(...))` |
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

- [ ] **Step 1: 写失败测试** — 断言 dataclass/Pydantic 模型序列化往返后关键字段一致（`event_id`, `event_type`, `event_version`, `tenant_id`, `correlation_id`, `payload`）。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd server
uv run pytest tests/unit/test_outbox_envelope.py -v
```

Expected: FAIL（模块不存在或未实现）

- [ ] **Step 3: 最小实现** — 使用与项目一致的模型风格（可与现有 `app/kernel` 中 schema 风格对齐）；**代码注释使用英文**（工作区规则）。

- [ ] **Step 4: 测试通过**

```bash
uv run pytest tests/unit/test_outbox_envelope.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/kernel/events/envelope.py server/tests/unit/test_outbox_envelope.py
git commit -m "feat(outbox): 增加领域事件 envelope 与单测"
```

---

### Task A2: Alembic 迁移 — event_outbox、event_consumer_checkpoint、dead_letter（推荐）

**Files:**
- Create: `server/alembic/versions/<timestamp>_event_outbox_tables.py`
- Modify: 无（若需注册模型进 `env.py`/`create_tables` 按现有惯例）

- [ ] **Step 1:** 运行 `cd server && uv run alembic heads` 确认当前 head revision id。

- [ ] **Step 2:** 新建 migration，`down_revision` 指向当前 head；按规格 **§7.1–7.3** 创建表与索引（`status+available_at`、`correlation_id`、`subject_type+subject_id`、`run_id`、`workflow_run_id`）。

- [ ] **Step 3:** `uv run alembic upgrade head` 在本地开发库验证（或 `alembic upgrade head --sql` 检视）。

- [ ] **Step 4: Commit**

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

- [ ] **Step 1: 失败测试** — 使用项目现有 DB fixture（若存在）或 `sqlite` 内存引擎：在同一 session 内 `enqueue` 后 `flush`，再 `fetch_pending` 能取到 `pending` 行；`claim` 后状态为 `processing`。

- [ ] **Step 3: 实现** — `enqueue(...)` 仅 `session.add`，**不**在 repo 内 `commit`（由调用方控制事务）。提供原子 `claim`（`UPDATE ... WHERE id=? AND status='pending'` 或等价）。

- [ ] **Step 4:** `uv run pytest tests/unit/test_outbox_repository.py -v` → PASS

- [ ] **Step 5: Commit** — `feat(outbox): Outbox 模型与 repository`

---

### Task A4: Checkpoint 辅助

**Files:**
- Create: `server/app/kernel/events/checkpoint.py`
- Test: `server/tests/unit/test_outbox_checkpoint.py`

- [ ] 测试：`has_processed(consumer_name, event_id)` 在插入一行后为 True；唯一约束冲突时行为明确（插入失败则视为已存在，由调用方 skip）。

- [ ] 实现：封装 `try_insert_checkpoint` / `is_processed`。

- [ ] `uv run pytest tests/unit/test_outbox_checkpoint.py -v` → PASS

- [ ] Commit: `feat(outbox): consumer checkpoint 辅助`

---

### Task A5: Handler Registry

**Files:**
- Create: `server/app/kernel/events/registry.py`
- Test: `server/tests/unit/test_outbox_registry.py`

- [ ] 注册多个 handler 同一 `event_type`，`get_handlers` 返回顺序稳定（注册顺序）。

- [ ] Commit: `feat(outbox): handler 注册表`

---

### Task A6: Dispatcher（规格 §10）

**Files:**
- Create: `server/app/kernel/events/dispatcher.py`
- Test: `server/tests/unit/test_outbox_dispatcher.py`

- [ ] 实现异步 `process_batch()`：对每条 outbox 行，对每个 handler：**先 checkpoint 查询 → skip 或执行 → 成功则写 checkpoint**；全部 handler 成功后 `mark_done`；任一步异常则 `mark_retry`/`last_error`/`attempt_count`，超阈值 `dead_letter`（若表存在）。

- [ ] 单元测试使用 **fake session** 或 mock repo，覆盖：双 handler、第二个失败时第一个 checkpoint 已写入且不丢、重入时 skip。

- [ ] `uv run pytest tests/unit/test_outbox_dispatcher.py -v` → PASS

- [ ] Commit: `feat(outbox): dispatcher 与单测`

---

### Task A7: 配置与 lifespan 挂载

**Files:**
- Modify: `server/app/settings/settings.py`（或实际配置模块）
- Modify: `server/app/main.py`

- [ ] 增加 `outbox_dispatcher_enabled: bool = False`、`outbox_dispatcher_poll_interval: float`、`outbox_dispatcher_batch_size: int` 等。

- [ ] 在 `lifespan` 中若 enabled，则 `asyncio.create_task(OutboxDispatcher(...).run_loop(...))`，shutdown 时 cancel（**照抄** knowledge worker 的 cancel 模式，见 `main.py` 约 80–104 行）。

- [ ] 手动验证：启动 API + 启用 flag，日志无异常循环。

- [ ] Commit: `feat(outbox): 可配置启动 dispatcher 后台任务`

---

### Task A8: 集成烟囱测试

**Files:**
- Create: `server/tests/integration/test_outbox_dispatch.py`

- [ ] 在同一测试中：开启测试 DB、插入一行业务占位（可选）、**同事务** enqueue 一条真实 `event_outbox`、commit；运行 dispatcher 一轮；断言测试 handler 副作用（如测试表计数）且 outbox 为 `done`。

- [ ] `uv run pytest tests/integration/test_outbox_dispatch.py -v` → PASS

- [ ] Commit: `test(outbox): dispatcher 端到端烟囱测试`

---

## Wave B — 执行面事件化（按链渐进，多条 PR 可拆分）

### Task B1: 事件类型常量与 Runtime 首条链（示例：run.created）

**Files:**
- Create: `server/app/kernel/runtime/events.py`（`RunEventType` 等字符串常量）
- Modify: 实际创建 `runs` 的服务（需在代码库中 `rg "runs"` / `create_run` 定位，例如 modules 下 run 服务）
- Modify: 上述服务所用 session：**提交前** `outbox_repo.enqueue` 同事务

- [ ] 定义最小集合：先 **仅** `run.created`（或规格 §6.1 中与当前主链重合的 1–2 个）。

- [ ] 注册 handler：例如 `server/app/kernel/runtime/handlers/on_run_created.py`，由 wiring 注册到 registry（避免 kernel import modules：handler 可放在 kernel/runtime/handlers，内部仅调 ports/已有服务）。

- [ ] 集成测试：创建 run 的 API 或 service 调用后，dispatcher 处理完毕的观测断言（可轮询 DB）。

- [ ] Commit: `feat(runtime): run.created 写入 outbox 并由 handler 消费`

---

### Task B2: Task 生命周期事件与状态机推进

**Files:**
- Modify: task 状态迁移集中点（`RuntimeCoreService` 或 task 执行器）
- Create/Modify: `server/app/kernel/runtime/handlers/` 下对应 handlers

- [ ] 按规格 §6.1 逐步加入 `task.*`，**YAGNI**：仅对接当前代码路径会触发的状态。

- [ ] 每加一个事件：`uv run pytest server/tests/unit/test_runtime_* server/tests/integration/...` 回归。

- [ ] Commit（可多个）：`feat(runtime): task 生命周期 outbox 事件`

---

### Task B3: Workflow 节点调度

**Files:**
- Modify: `server/app/modules/workflow/` 下节点完成/失败路径
- Create: `server/app/modules/workflow/handlers/scheduler.py`（名称自定）

- [ ] 发 `workflow.node.completed` / `workflow.node.failed`；consumer 调度下一节点（规格 §11.2）。

- [ ] 更新 `workflow_runs` 计数字段（规格 §8.2），**同事务或单 handler 事务**内完成。

- [ ] `uv run pytest tests/unit/test_workflow_executor.py tests/entrypoints/test_workflow_api.py -v`（按需）

- [ ] Commit: `feat(workflow): 节点事件与调度 consumer`

---

### Task B4: Approval 请求与恢复

**Files:**
- Modify: `server/app/modules/` 下 approvals 服务（路径以仓库为准）
- Create: `server/app/modules/approvals/handlers/resume.py`

- [ ] `approval.requested` / `approval.approved` / `approval.rejected`（§6.3）；consumer 恢复等待中的 run/node（§11.3）。

- [ ] Commit: `feat(approvals): 审批事件与恢复路径`

---

### Task B5: 表字段扩展 runs / workflow_runs

**Files:**
- New migration under `server/alembic/versions/`
- Modify: `server/app/kernel/runtime/models.py` 或 `runs` 所在模型文件、workflow_run 模型

- [ ] 按规格 **§8.1–8.2** 添加字段；回填策略（nullable + 应用层写入）在 migration 注释中说明。

- [ ] Commit: `feat(db): 扩展 runs/workflow_runs 查询字段`

---

## Wave C — 可观测性订阅

### Task C1: Trace/Audit/Usage/Cost handlers

**Files:**
- Create: `server/app/kernel/trace/handlers/`、`server/app/kernel/observability/handlers/`
- Modify: 当前内联写入点（从 `test_trace_emission.py`、`trace/writer.py` 等顺藤摸瓜）

- [ ] 为每类 side effect 注册 **稳定 consumer_name**；逻辑保持幂等（重复 `event_id` 不重复写审计行，或依赖业务唯一键）。

- [ ] `uv run pytest tests/test_trace_emission.py tests/unit/test_audit_log.py -v`（按实际测试文件调整）

- [ ] Commit: `refactor(observability): trace/audit/cost 改为 outbox 订阅`

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
