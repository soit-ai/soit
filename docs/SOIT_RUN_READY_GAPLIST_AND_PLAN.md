# SOIT 可正常运行版本（v0.9 Run-ready）需补齐功能清单与计划

> 目标：把当前代码从“开发态可跑”提升到“交付态可正常运行（开箱即用）”。  
> 核心要求：**一键启动（Compose）→ 自动迁移/初始化 → Dataset worker 消费任务 → Web 可访问 → Demo 场景可复现**。

---

## 1) 交付态“可正常运行”定义（Run-ready DoD）

### 平台级 DoD
- [ ] `docker compose up -d` 后：API / DB / Redis / MinIO / Milvus / Vault 全部健康（healthcheck 通过）
- [ ] **无需手工操作**即可完成：
  - [ ] 数据库迁移（alembic upgrade head）
  - [ ] 初始化默认 tenant/workspace/admin（或提供一次性 bootstrap job）
- [ ] Dataset ingestion **任务可被 worker 消费**（任务状态能从 queued→running→succeeded/failed）
- [ ] Web（前端）有明确交付方式（compose 内置 or 独立部署），默认配置可打开
- [ ] 关键链路 demo 可复现且可排障：
  - [ ] Workflow：build→publish→run→monitor/log→retry
  - [ ] Dataset：upload→ingest→search
  - [ ] Chat+RAG：引用 Dataset→回答含 citations
  - [ ] Secrets：secret_ref 注入工具调用，无明文泄露

---

## 2) P0 必须补齐功能清单（阻断“正常运行”的缺口）

> P0 的原则：不做“新能力扩展”，只补齐“开箱即用”的必需链路。

### P0-01 数据库迁移自动化（Migration Job）
**问题**：首次启动若不手动执行 alembic upgrade，API 容易因为表不存在而不可用。  
**需要补齐**
- [ ] 新增 `migrate` compose service（一次性 job）：
  - 运行 `alembic upgrade head`
  - 依赖 postgres 健康后再执行
- [ ] API service `depends_on` `migrate`（或使用启动脚本确保顺序）
- [ ] README 增加迁移说明与故障排查

**验收（DoD）**
- `docker compose up -d` 后，数据库表自动就绪；无需人工进入容器执行迁移。

---

### P0-02 初始化默认租户/工作区/管理员（Bootstrap Job）
**问题**：没有默认账号/工作区就无法立刻登录使用；现在有脚本但没接入启动流程。  
**需要补齐**
- [ ] 新增 `bootstrap` compose service（一次性 job）：
  - 运行 `scripts/bootstrap_admin.py`（或你仓库已有初始化脚本）
  - 幂等：重复执行不会创建重复数据
- [ ] 支持通过环境变量配置默认 admin（email/password/tenant/workspace）
- [ ] 在 API 启动前执行（或允许 API 启动后立即可用）

**验收（DoD）**
- 启动后可以使用默认账号直接登录进入系统；再次启动不会重复创建。

---

### P0-03 Dataset Ingestion Worker 服务化（Worker in Compose）
**问题**：已有 ingest worker 脚本，但 compose 未启动 worker 服务，任务不会被消费。  
**需要补齐**
- [ ] 新增 `dataset-worker` compose service（常驻进程）：
  - 运行 `scripts/dataset_ingest_worker.py` / `scripts/ingest_worker.py`（以仓库实际为准）
  - 依赖 redis/postgres/minio/milvus/vault 健康后启动
- [ ] Worker 并发与轮询间隔配置（env）
- [ ] IngestTask 状态写回与错误字段（error_code/message）确保 UI 可显示

**验收（DoD）**
- 上传文档后任务会从 queued 进入 running，并最终 succeeded/failed；
- failed 可通过 API 触发 retry（如果已具备 retry 字段则补齐接口/UI）。

---

### P0-04 Web 交付方式固化（Compose 内置 or 独立部署）
**问题**：compose 中 web 注释掉；交付时无法“一键访问”。  
**需要补齐（两选一，建议 A）**
- **方案 A（建议）**：compose 内置 web 镜像  
  - [ ] 添加 `web` service：build 前端 → Nginx 静态托管
  - [ ] 通过 env 注入 API base URL（如 `/api` 反代）
- 方案 B：web 独立部署  
  - [ ] 提供 `web/dist` 构建产物方式 + Nginx 配置样例
  - [ ] 明确 `VITE_API_BASE_URL`、CORS、反代规则

**验收（DoD）**
- 启动后访问 `http://localhost:<port>` 能打开前端，并能正常调用 API。

---

### P0-05 健康检查与启动顺序（Healthcheck & Depends）
**问题**：服务多且依赖复杂（milvus/etcd/minio/vault），无健康检查会导致“偶发启动失败”。  
**需要补齐**
- [ ] 为 postgres/redis/minio/vault/milvus 添加 healthcheck（尽量使用 curl/wget 或内置命令）
- [ ] API/worker/web 的 `depends_on: condition: service_healthy`
- [ ] README 增加“常见启动失败原因与排查清单”（milvus/etcd/vault）

**验收（DoD）**
- 冷启动成功率显著提高（连续 3 次冷启动都能成功跑通 Demo-1/2）。

---

### P0-06 Demo 场景脚本化（Release Smoke Tests）
**问题**：没有自动化 Demo 验证，发版容易“看起来能跑但关键路径坏了”。  
**需要补齐**
- [ ] 增加 `scripts/smoke/*.py`（或 `make smoke`）：
  - Demo-1：创建 workflow→publish→run→等待完成
  - Demo-2：上传 doc→等待 ingest 完成→检索
  - Demo-3：chat with rag→验证 citations
  - Demo-4：secret_ref tool call→验证无明文泄露（至少检查响应与日志关键字）
- [ ] CI（可选）跑 smoke（最小本地可跑即可）

**验收（DoD）**
- 一条命令即可在新环境验证关键链路；失败时输出明确错误定位信息。

---

## 3) P1 强化项（不阻断运行，但影响“交付体验”）

### P1-01 运行历史与成本（Runs/Cost）UI 验收补齐
- [ ] Runs 列表过滤（mode/status/time/workflow）
- [ ] Run 详情：steps/错误/成本聚合
- [ ] Cost Summary：按 model/provider 聚合

### P1-02 Secrets 管理 UI（最小可用）
- [ ] secrets CRUD（workspace scope）
- [ ] 引用测试按钮（执行一个 HTTP tool）

### P1-03 Dataset UI：任务状态与重试入口
- [ ] 文档列表显示 ingest 状态
- [ ] 失败原因展示
- [ ] retry/cancel 按钮（如后端支持）

---

## 4) 执行计划（推荐 2~3 个迭代）

> 你可以按团队人力调整；这里给一个“最少返工”的推进顺序。

### Iteration 1（P0 基础交付链路，3~5 人日）
- P0-01 Migration Job
- P0-02 Bootstrap Job
- P0-03 Dataset Worker Compose 服务
- P0-05 Healthcheck & Depends（先做核心依赖）

**交付物**
- 更新后的 `docker-compose.yml`（新增 migrate/bootstrap/worker）
- `README_RUN.md`（一键启动说明 + 默认账号）

### Iteration 2（P0 Web 交付 + Smoke Demo，4~6 人日）
- P0-04 Web 交付固化（建议方案 A）
- P0-06 Smoke Tests 脚本化
- 完善 P0-05（补齐所有 healthcheck）

**交付物**
- 可直接访问的 web（Nginx 静态托管）
- `make smoke` / `python scripts/smoke/run_all.py` 一键验证

### Iteration 3（P1 体验强化，4~8 人日）
- P1-01 Runs/Cost UI
- P1-02 Secrets UI
- P1-03 Dataset UI（状态/重试）

**交付物**
- 运营/排障可视化闭环（运行历史、成本、错误）

---

## 5) 任务拆分（可直接转 Jira/Linear）

| ID | 优先级 | 任务 | 产出文件/模块 | 验收要点 |
|---|---|---|---|---|
| P0-01 | P0 | compose migrate job | `docker-compose.yml` `scripts/migrate.sh` | up 后自动迁移 |
| P0-02 | P0 | compose bootstrap job | `docker-compose.yml` `scripts/bootstrap_admin.py` | 默认账号可登录、幂等 |
| P0-03 | P0 | dataset-worker service | `docker-compose.yml` `scripts/*worker*.py` | ingest task 能消费 |
| P0-04A | P0 | web service（Nginx） | `web/Dockerfile` `nginx.conf` `docker-compose.yml` | 启动即可访问前端 |
| P0-05 | P0 | healthcheck & depends | `docker-compose.yml` | 冷启动稳定 |
| P0-06 | P0 | smoke tests | `scripts/smoke/*` | 一键验证 Demo 1~4 |

---

## 6) 发布前检查（Release Checklist）
- [ ] `docker compose up -d` 后无需手工操作即可登录
- [ ] Dataset ingest 能完成一次成功任务
- [ ] Workflow build→publish→run→monitor/log→retry 全链通过
- [ ] Runs 页面可定位一次失败原因与成本
- [ ] Secrets 注入调用成功且无明文泄露
- [ ] smoke tests 全绿

---
