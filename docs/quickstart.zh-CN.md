# SOIT 快速开始

本文档是 Phase 1 本地自托管环境的 Quickstart 路径，覆盖 Docker 启动、demo seed、smoke / regression 验证，以及 1.0 Quickstart 门槛需要保留的证据。

![SOIT 工作区截图](assets/hero.png)

## 启动本地环境

在仓库根目录执行：

```bash
cp .env.example .env
docker compose --env-file .env -f docker/docker-compose.yml up -d postgres redis minio etcd milvus vault migrate bootstrap api web knowledge-ingest-worker outbox-dispatcher
```

打开：

- Web UI：`http://localhost:5000`
- API base / API docs：`http://localhost:9200`

使用 `.env` 中的 `BOOTSTRAP_ADMIN_EMAIL` 和 `BOOTSTRAP_ADMIN_PASSWORD` 登录。

## 初始化 Demo 工作区

数据库迁移完成后，写入确定性的 Phase 1 demo 数据：

```bash
cd server
uv run python scripts/bootstrap_enterprise_mvp.py
```

该 seed 脚本是 idempotent 的，会创建或更新：

- sample Provider 和测试模型
- sample Knowledge，包含 `refund-policy.md`
- sample Agent，绑定模型、知识库和工具
- sample Workflow，用于 support ticket triage

如需更完整的 Observe、Task、Run、审批和失败状态 demo：

```bash
uv run python scripts/seed_enterprise_mvp_scenarios.py --reset
```

## 验证 Demo 链路

运行 Agent / Knowledge / Workflow 的后端 smoke 测试：

```bash
uv run pytest tests/integration/test_enterprise_agent_mvp.py -q
```

运行 support-ticket regression evaluator：

```bash
uv run python scripts/evaluate_support_ticket_regression.py --json-output ../artifacts/support-ticket-regression/report-current.json
```

报告应包含 citation evidence、tool-call evidence、child workflow run evidence、audit evidence 和 cost evidence。

## 手工 UI 检查

上方截图引用 `docs/assets/hero.png`，作为首屏视觉参考。随后检查：

1. ModelHub 展示 seed 的测试 Provider 和模型。
2. Knowledge 包含 seed 的 refund policy 文档。
3. Agent 能基于退款政策问题返回带引用的回答。
4. Workflow 能执行 support-ticket triage 链路。
5. Runs 与 Observe 展示 response events、run steps、tool calls、child workflow runs、costs、citations 和 audits。

## Docker Smoke 证据

在路线图中勾选 Docker / Quickstart 条目前，需要保留以下命令的新输出：

```bash
curl http://localhost:9200/health/ready
curl http://localhost:5000/
docker compose -f docker/docker-compose.yml ps knowledge-ingest-worker
docker compose -f docker/docker-compose.yml ps outbox-dispatcher
```

期望结果：API ready、Web 可访问，并且 `knowledge-ingest-worker` 与 `outbox-dispatcher` 均处于 healthy 或 running 状态。

复制 `docs/deployment/quickstart-deployment-evidence.example.json` 为 `docs/deployment/quickstart-deployment-evidence.json`，将所有 `evidenceRef` 替换为本次新输出后，在 `server/` 下开启仓库根目录校验：

```bash
uv run python scripts/verify_quickstart_deployment.py ../docs/deployment/quickstart-deployment-evidence.json --repo-root ..
```

验证器会要求完整 Docker service set、每个 service 的 healthy 状态与唯一 evidenceRef、10 分钟内启动、API/Web/worker health、demo seed、链路 A smoke、regression 输出证据、唯一 check evidenceRef，以及仓库根目录下真实存在的本地证据文件。

验证器要求完整 Docker 服务集、10 分钟内启动、API/Web/worker 健康证据、demo seed 证据、Chain A smoke 证据与 regression 输出证据。

## 数据库迁移路径

SOIT 1.0 支持空 PostgreSQL 数据库升级到 head `20260803090000`，以及从 `20260718140000` 原地升级的显式 N-1 路径。其他历史开发快照不在支持范围内；详见[数据库迁移手册](release-migration.md)。

## 模型源支持

1.0 ModelHub provider 支持矩阵与真实凭据 spot-check 口径，见 [docs/model-provider-support.md](model-provider-support.md)。

1.0 Owner UI spot-check 与 Chain A/B 手工验收记录，复制 `docs/deployment/phase1-manual-acceptance-evidence.example.json` 为 `docs/deployment/phase1-manual-acceptance-evidence.json`，将所有 `evidenceRef` 替换为真实截图或命令输出后，在 `server/` 下开启仓库根目录校验：

```bash
uv run python scripts/verify_phase1_manual_acceptance.py ../docs/deployment/phase1-manual-acceptance-evidence.json --repo-root ..
```

手工验收验证器要求 route 截图 evidenceRef 唯一、每个 route 的 desktop/mobile viewport evidenceRef 唯一、Chain A/B 验收 evidenceRef 唯一；使用 `--repo-root` 时还会要求本地证据文件真实存在。
