# SOIT

<p>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License: Apache-2.0" /></a>
  <a href="https://github.com/soit-ai/soit/actions/workflows/quality.yml"><img src="https://github.com/soit-ai/soit/actions/workflows/quality.yml/badge.svg" alt="Quality gate" /></a>
  <a href="https://github.com/soit-ai/soit/releases"><img src="https://img.shields.io/github/v/release/soit-ai/soit?include_prereleases&label=release" alt="Latest release" /></a>
</p>

[English](./README.md) · [更新日志](./CHANGELOG.md) · [贡献指南](./CONTRIBUTING.md)

面向企业 AI 系统的可治理 Agent Runtime：把权限、密钥、外联控制、审计、成本、追踪和回放放在 Agent 运行时的核心位置。

## 项目概述

SOIT Community 是开源的 Agent Runtime and Governance Platform，面向已经验证 Agent 价值、但需要把 Agent 接入真实业务系统的团队。它把 Agent 构建、工作流执行、知识检索、工具/MCP 接入、模型路由和运行观测收敛到一个自托管控制平面，并把权限、密钥、基础外联网关、审计、成本、追踪和回放放在运行时边界。

SOIT 采用前后端分离架构。当前产品主结构已经收敛到 Agent 中心：Agent 作为主业务对象，Thread/Task/Run 作为统一执行账本，Knowledge/Workflow/Skill 作为能力层，Plugin/MCP 作为安装与集成层。项目遵循清晰分层与稳定内核原则，确保核心层稳定、领域层可持续迭代。

## 治理优先能力

- **权限**：租户、工作区、资源级 RBAC 与 grant 继承，约束 Agent 能访问什么。
- **密钥**：Vault-backed secret 管理与工作区级可见性，工具调用通过受控注入获取密钥。
- **外联控制**：egress policy 限制外部 HTTP 和工具适配器访问边界。
- **Plugin 优先治理**：MCP server 与 Skill 作为 Plugin artifact 安装，运行时自动继承权限、密钥注入、外联边界、审计、成本归因、追踪和回放能力。
- **审计**：记录特权操作、工具调用、审批、人审 checkpoint 和运行证据。
- **成本**：按 run、模型、工具、工作流和工作区归因 token、延迟与成本。
- **追踪**：以统一 Run/Task/RunStep/Response ledger 串起 Agent、Workflow、Tool 和 Knowledge 事件。
- **回放**：通过 Observe run detail 复盘响应事件、运行步骤、工具调用、子工作流、引用、成本和审计记录。

## 技术栈

### 后端技术栈 (app/)

**核心框架与运行时：**
- **Web 框架**: FastAPI 0.114+ (Python 3.11+)
- **ORM**: SQLModel 0.0.24 (基于 SQLAlchemy 2.0.31)
- **异步支持**: asyncio, httpx
- **包管理**: uv (现代 Python 包管理器)

**数据库与存储：**
- **主数据库**: PostgreSQL 15 (使用 psycopg[binary] 3.1+)
- **缓存/消息队列**: Redis 7 (使用 aioredis 2.0+, redis 5.2+)
- **任务队列**: Celery 5.4+ (异步任务处理)
- **向量数据库**: Milvus 2.5.11 (使用 pymilvus 2.5.11)
- **对象存储**: MinIO (支持 S3/OSS/COS/GCS，使用 boto3/oss2/cos-python-sdk-v5/google-cloud-storage)

**数据库迁移与版本控制：**
- **迁移工具**: Alembic 1.12+ (数据库版本管理)

**认证与安全：**
- **JWT**: PyJWT 2.8+ (身份认证)
- **密码加密**: passlib[bcrypt] 1.7+ (bcrypt 4.0.1)
- **密钥管理**: HashiCorp Vault (通过适配器)

**可观测性与监控：**
- **日志**: 结构化 JSON 日志
- **指标**: Prometheus Client 0.21+ (指标收集)
- **追踪**: OpenTelemetry (分布式追踪)
- **错误监控**: Sentry SDK 1.40+ (错误追踪和性能监控)

**LLM 与 AI 框架：**
- **模型适配**: OpenAI、Anthropic、DeepSeek 和 OpenAI-compatible endpoint
- **向量模型**: sentence-transformers 4.1+, langchain-huggingface 0.0.6 (嵌入模型)
- **Token 计算**: tiktoken 0.9+ (Token 计数)

**文档处理：**
- **文档处理**: PDF、Word、Excel、Markdown 和 HTML 解析边界

**开发工具：**
- **代码质量**: ruff 0.2+ (linting 和格式化)
- **类型检查**: Pyright
- **测试框架**: pytest / pytest-asyncio

### 前端技术栈 (web/)

**核心框架：**
- **框架**: React Router 7 (SSR 支持)
- **语言**: TypeScript 6
- **构建工具**: Vite 8

**UI 与样式：**
- **UI 组件库**: Radix UI (无障碍组件)
- **样式框架**: TailwindCSS 4 (实用优先的 CSS 框架)

**状态管理与数据获取：**
- **状态管理**: Zustand (轻量级状态管理)
- **数据获取**: React Query (服务端状态管理)

**可视化：**
- **图表库**: Recharts (数据可视化)
- **工作流可视化**: React Flow (@xyflow/react) (DAG 图编辑)

**其他工具：**
- **国际化**: i18next (多语言支持)
- **代码高亮**: Shiki (代码语法高亮)

### 基础设施

**Docker Compose 服务：**
- PostgreSQL 15 (主数据库)
- Redis 7 (缓存和消息队列)
- Milvus 2.5 (向量数据库)
- etcd (Milvus 元数据存储)
- MinIO (对象存储)
- API 服务 (FastAPI 应用)
- Web 服务 (React Router SSR 应用)
- Knowledge ingest worker
- Outbox dispatcher (`outbox-dispatcher`)

## 项目结构

```
soit/
├── server/                 # 后端工程
│   ├── app/               # 应用代码（server/app/)
│   │   ├── api/           # HTTP/WS/SSE 入口
│   │   ├── kernel/        # 稳定核心（identity/runtime/trace/specs）
│   │   ├── modules/       # 业务域（agent/chat/workflow/knowledge/plugin 等）
│   │   ├── adapters/      # 外部依赖适配器
│   │   ├── infra/         # 基础设施实现
│   │   ├── middleware/    # 中间件
│   │   ├── wiring/        # 依赖装配
│   │   └── main.py        # FastAPI 入口
│   ├── docs/              # 后端文档
│   ├── tests/             # 后端测试
│   ├── scripts/           # 开发脚本
│   └── alembic/           # 数据库迁移
└── web/                   # 前端应用
```

## 核心架构原则

1. **Spec-First**: 任何新功能先更新 spec
2. **Scope-By-Default**: 所有资源默认带 tenant_id + workspace_id
3. **Trace Everything**: 所有执行必须创建 run + step
4. **Gateway-Only**: 外部调用必须通过网关
5. **Immutable Versions**: 版本不可变，只移动指针

## 开发规范

详细开发规范请参考：
- [后端架构文档](server/docs/architecture/PROJECT_STRUCTURE.md)
- [前端结构文档](web/docs/PROJECT_STRUCTURE.md)
- [AGENTS规范文档](AGENTS.md)
- [工程指南](server/docs/engineering/ENGINEERING_GUIDE.md)
- [架构文档](server/docs/architecture/)

## 快速开始

完整的 Phase 1 双语 Quickstart、demo seed 与 smoke 证据路径见：[docs/quickstart.zh-CN.md](docs/quickstart.zh-CN.md)。

### 后端开发

```bash
cd server
uv sync                    # 安装依赖
uvicorn app.main:app --reload  # 启动开发服务器
```

### 前端开发

```bash
cd web
npm install
npm run dev
```

### Docker Compose 启动

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d postgres redis minio etcd milvus vault migrate bootstrap api web knowledge-ingest-worker outbox-dispatcher
```

启动后默认行为：
- 自动执行数据库迁移（alembic upgrade head）。
- 自动初始化默认管理员/租户（可通过环境变量覆盖）。
- 自动启动 knowledge ingest worker。
- Web 默认端口：`http://localhost:5000`
- API 默认端口：`http://localhost:9200`

默认管理员可通过以下环境变量配置（见 `.env.example`）：
- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `BOOTSTRAP_ADMIN_NAME`
- `BOOTSTRAP_TENANT_NAME`

常见启动问题排查：
- `milvus` 启动失败：确认 `etcd` 和 `minio` 健康后再观察 `milvus` 日志。
- `vault` 健康检查失败：确认端口 `8200` 未被占用，且容器为 dev 模式。
- `api` 启动失败：优先查看 `migrate`/`bootstrap` 容器日志是否失败。
- `web` 无法访问：确认 `web` 容器健康且 `PORT=5000` 生效。

发布与运维参考：

- [Community 发布流程](docs/release-process.md)
- [备份恢复与回滚手册](docs/operations/backup-restore.md)
- [安全政策](SECURITY.md)

## 当前 MVP 聚焦

当前非 Docker MVP 质量门禁聚焦一条可重复企业闭环：退款政策知识问答、引用证据、受治理工单工具调用、子工作流运行，以及 Observe 中可检查的响应事件、运行步骤、成本、引用和审计记录。

这条路径是当前质量基线，用于约束后续扩展，避免平台演变成互不连通的演示功能集合。

## 许可证

SOIT 采用 [Apache License 2.0](LICENSE) 发布，并附加以下使用条件：

1. SOIT 可用于商业用途，包括作为其他应用的后端服务或企业的应用开发平台。满足以下条件时，须向 SOIT LLC 获取商业授权：

   a. **多租户服务**：未经 SOIT LLC 书面明确授权，不得使用 SOIT 源代码运营面向多个组织提供服务的托管服务——无论组织之间的隔离是通过 SOIT 的 tenant、workspace 还是其他机制实现。单一组织内部署 SOIT（包括为其自身团队、部门、子公司或环境开设多个 tenant 或 workspace）无需商业授权。

   b. **LOGO 与版权信息**：在使用 SOIT 前端的过程中，不得移除或修改 SOIT 控制台或应用中的 LOGO 与版权信息。此限制不适用于不涉及前端的 SOIT 使用场景。"前端"指从源码运行时 `web/` 目录下的全部组件，或以 Docker 运行时的 `web` 镜像。

2. 作为贡献者，你同意贡献的代码可被 SOIT LLC 用于商业用途（包括但不限于其云业务运营），且 SOIT LLC 可在必要时调整上述条款。

商业授权咨询请联系 **info@soit.ai**。
