# SOIT P0 缺口补齐开发清单（跳过 Agent）
> 范围：**Chat / Dataset / Workflow**  
> 目标：补齐“后端已实现但前端未覆盖 / 产品闭环不完整”的 P0 能力，让三个模块达到可稳定交付的可用版本。

---

## 0. 约定与产出

### 0.1 目录与命名
- 前端 service：`web/src/services/{module}-service.ts`（如已存在则在原文件扩展）
- 前端页面：`web/src/pages/{module}/...`
- 请求工具：沿用项目现有的 `get/post/patch/delete` 封装（不要重复造轮子）

### 0.2 P0 验收口径（统一）
- ✅ 接口调通（含 200/4xx/5xx 分支）
- ✅ UI 状态一致（loading/disabled/toast/错误提示）
- ✅ 刷新页面后状态可恢复（本地状态与后端一致）
- ✅ 关键边界：取消/重试/断线/快速重复点击不会导致异常状态或数据串扰

---

## 1) CHAT P0 开发清单

### CHAT-P0-1 补齐 history：`GET /chat/history` + `DELETE /chat/history/{conversation_id}`
**目的**：侧边栏会话来源稳定，提供历史清理能力。

#### A. 后端接口
- `GET /api/v1/chat/history`
- `DELETE /api/v1/chat/history/{conversation_id}`

#### B. 前端改动
1) `web/src/services/chat-service.ts`
- 新增：
  - `listHistory(params?)`
  - `deleteHistory(conversation_id)`

2) `web/src/pages/chat/ui/box-sidebar.tsx`
- 将会话列表数据源切换为 `history`（P0 直接替换即可，避免同时维护两套）
- 增加操作入口：
  - 删除历史（单条）
  - 可选：清空历史（如果后端有批量接口；没有就先不做）

#### C. 自测用例
- [ ] 列表能刷新
- [ ] 删除一条历史后，选中项切换合理（删除当前会话时自动切到下一条/空态）
- [ ] 删除历史不影响 conversation 的基本 CRUD（边界处理清晰）

---

### CHAT-P0-2 会话/消息一致性修复（串会话、刷新丢消息、重命名/删除同步）
**目的**：把“创建会话→对话→刷新→回看”闭环做扎实。

#### A. 对齐点（已有接口，校对调用时机）
- `POST /chat/conversations`
- `GET /chat/conversations`
- `GET /chat/conversations/{id}`
- `GET /chat/conversations/{id}/messages`
- `PATCH /chat/conversations/{id}`
- `DELETE /chat/conversations/{id}`

#### B. 前端改动（建议）
- `web/src/pages/chat/index.tsx`
  - 页面初始化：从 route 参数或 sidebar 选中项加载 conversation
  - 加载消息：始终从 `listMessages(conversation_id)` 拉取（必要时与本地 optimistic 合并/覆盖）
  - stream 完成后 reconcile（建议：拉一次 messages，确保与后端一致）
- `web/src/pages/chat/ui/box-sidebar.tsx`
  - 重命名：成功后刷新列表/更新本地缓存
  - 删除：成功后移除列表项；若删的是当前会话，回到空态或切换到下一条

#### C. 自测用例
- [ ] 新建会话并对话后刷新，仍能看到完整消息
- [ ] 重命名立即生效且刷新后仍正确
- [ ] 删除当前会话不崩溃，且 UI 状态合理

---

## 2) DATASET P0 开发清单

### DATASET-P0-1 补齐 Index 详情 `GET /datasets/{dataset_id}/indexes/{index_id}`
**目的**：Index 设置页可进入单个 index 的详情/编辑（加载完整配置）。

#### A. 后端接口
- `GET /api/v1/datasets/{dataset_id}/indexes/{index_id}`

#### B. 前端改动
1) `web/src/services/dataset-service.ts`
- 新增：
  - `getIndex(dataset_id, index_id)`

2) `web/src/pages/dataset/detail/setting.tsx`（或 index 管理所在页面）
- Index 列表新增「查看/编辑」入口：
  - 点击时调用 `getIndex` 拉详情
  - 展示配置（embedding 模型、chunk 参数、状态、创建时间等）
  - 编辑保存继续使用你们已有的 `updateIndex(PATCH)` 方法

#### C. 自测用例
- [ ] 点击任意 index 能看到完整详情
- [ ] 修改参数并保存后，列表与详情刷新一致

---

### DATASET-P0-2 Ingest Tasks：列表/详情/失败原因/重试取消“可运营闭环”
**目的**：让数据导入任务“可看、可诊断、可恢复”。

#### A. 已有接口（确认 UI 覆盖质量）
- `GET /datasets/{dataset_id}/ingest-tasks`
- `GET /datasets/{dataset_id}/ingest-tasks/{task_id}`
- `POST /datasets/{dataset_id}/ingest-tasks/{task_id}/retry`
- `POST /datasets/{dataset_id}/ingest-tasks/{task_id}/cancel`
- `POST /datasets/{dataset_id}/documents/{document_id}/retry-ingest`（如同时存在）

#### B. 前端改动
1) `web/src/pages/dataset/detail/document.tsx`
- Ingest 任务列表至少展示：
  - 状态（queued/running/succeeded/failed/canceled）
  - 进度（% 或阶段）
  - 文档关联（document_id / doc_key / 文件名）
  - 创建时间、耗时
  - 错误摘要（failed 时）
- 操作：
  - `Retry`（仅 failed/canceled 可用）
  - `Cancel`（仅 queued/running 可用）
  - 二次确认（P0 必须）
- 刷新策略：
  - running 状态可轮询（例如 3~5s，一旦离开页面停止轮询）

2) 任务详情组件（任选其一）
- 方案 A：新增 `web/src/pages/dataset/detail/ingest-task-detail.tsx`
- 方案 B：用 drawer/modal 在原页面展示详情
- 详情至少包括：
  - 错误堆栈/失败阶段/重试次数
  - 处理到哪个步骤（parse/chunk/embed/index 等，如后端提供）
  - 相关文档跳转入口

#### C. 自测用例
- [ ] running 任务能看到进度变化（轮询有效）
- [ ] failed 任务能看到错误原因（不少于摘要）
- [ ] retry 后状态回到 queued/running 并最终成功（如环境允许）
- [ ] cancel 后任务停止继续执行（状态可见）

---

### DATASET-P0-3 Index rebuild：防误操作 + 状态反馈
**目的**：rebuild 属高风险操作，P0 要做到“确认 + 可见反馈 + 状态刷新”。

#### A. 后端接口
- `POST /api/v1/datasets/{dataset_id}/indexes/{index_id}/rebuild`

#### B. 前端改动
- `web/src/pages/dataset/detail/setting.tsx`
  - rebuild 按钮：二次确认（写明影响：索引重建期间查询可能受影响）
  - 点击后：loading + toast
  - rebuild 完成前：允许手动刷新/自动轮询 index 状态（P0 建议手动刷新即可，简单可靠）
- `web/src/services/dataset-service.ts`
  - 若已有 `rebuildIndex`，确认错误处理与返回值透出

#### C. 自测用例
- [ ] rebuild 必须确认
- [ ] rebuild 后状态可见（至少能看到请求成功提示，并刷新后看到状态变化）

---

## 3) WORKFLOW P0 开发清单

### WF-P0-1 service 补齐 run 控制接口（4 个）
**目的**：补齐后端已有但前端缺失的 run 控制能力。

#### A. 后端接口（前端缺）
- `POST /api/v1/workflows/{app_id}/runs/{run_id}/pause`
- `POST /api/v1/workflows/{app_id}/runs/{run_id}/resume`
- `POST /api/v1/workflows/{app_id}/runs/{run_id}/retry`
- `POST /api/v1/workflows/{app_id}/runs/{run_id}/replay`

#### B. 前端改动
- `web/src/services/workflow/index.ts`
  - 新增方法：
    - `pauseRun(app_id, run_id)`
    - `resumeRun(app_id, run_id)`
    - `retryRun(app_id, run_id)`
    - `replayRun(app_id, run_id)`
  - 统一错误处理：
    - 409/422：状态不允许（例如已结束的 run 不允许 pause）
    - 404：run 不存在
    - 401/403：权限问题

#### C. 自测用例
- [ ] 四个接口都能打通并返回可用响应
- [ ] 非法状态能给出明确提示

---

### WF-P0-2 在运行记录/日志页接入 pause/resume/retry/replay
**目的**：UI 可操作 run，并且按钮随状态变化。

#### A. 页面定位
- 优先在 workflow 的 run/log 页面增加操作区（你们项目里通常是类似）：
  - `web/src/pages/workflow/detail/log.tsx`
  - 或 run 详情页（若存在）

#### B. UI 交互（最小集）
- 状态 → 可用按钮：
  - `running` → Pause
  - `paused` → Resume
  - `failed` → Retry / Replay
  - `succeeded` → Replay
- 点击动作：
  - 二次确认（Retry/Replay 建议确认，Pause/Resume 可不确认）
  - 操作后 toast 提示
  - 刷新 run 状态（重新拉 run 或刷新 runs 列表）

#### C. 自测用例
- [ ] running → pause 后状态变 paused
- [ ] paused → resume 后状态回 running
- [ ] failed → retry 后生成新 run 或在原 run 下重试（按后端语义）
- [ ] succeeded → replay 可触发新 run

---

### WF-P0-3 最小可观测联动（定位失败节点/错误信息）
**目的**：P0 不追求全量观测，但必须能“看懂失败原因”。

#### A. 必须展示
- run 基本信息：status、start/end、duration
- error 信息：message / code / stack（能展示多少展示多少）
- 最小定位：最后失败 step / 节点名（若后端提供 step 列表接口）

#### B. 前端改动建议
- 在 run 详情中增加：
  - 错误摘要卡片
  - 跳转到 step 列表/展开 step（如果你们已有 runs/steps 页面，做 link 即可）

#### C. 自测用例
- [ ] 人为制造失败（比如 HTTP 节点指向无效地址）后，UI 能显示明确错误信息
- [ ] 能定位到失败节点（至少显示节点名/step id）

---

## 4) P0 合并与回归清单（必须做）

### 4.1 回归测试项
- Chat：
  - [ ] stream 正常、停止正常、切换会话不串
  - [ ] history 列表/删除稳定
- Dataset：
  - [ ] index detail 拉取正常
  - [ ] ingest tasks 可看、可取消、可重试
  - [ ] rebuild 有确认与反馈
- Workflow：
  - [ ] pause/resume/retry/replay 操作可用且状态约束正确
  - [ ] 失败 run 可定位错误原因

### 4.2 代码质量要求（P0）
- 前端：service 方法统一返回结构与异常处理，不要在页面层散落重复逻辑
- 前端：按钮点击防抖（至少禁用重复点击）
- 前端：轮询必须可取消（离开页面/切换 dataset 时停止）
- 后端：无需改动（本次 P0 假设后端接口已稳定可用）

---

## 5) 建议拆分 Issue（可直接复制）
1. **CHAT-P0-1**：接入 `/chat/stream`（含停止生成、断线处理）
2. **CHAT-P0-2**：接入 `/chat/history`（sidebar 切换数据源 + 删除历史）
3. **CHAT-P0-3**：会话/消息一致性修复（刷新、切换、重命名、删除）
4. **DATASET-P0-1**：补齐 `getIndex` + setting 页接入
5. **DATASET-P0-2**：Ingest tasks 运营闭环（列表/详情/重试/取消/轮询）
6. **DATASET-P0-3**：Index rebuild 防误操作 + 状态反馈
7. **WF-P0-1**：workflow run 控制接口 service 补齐（4 个）
8. **WF-P0-2**：run/log 页接入按钮（状态约束）
9. **WF-P0-3**：最小可观测联动（错误信息/失败节点定位）

---
