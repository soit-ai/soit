# SOIT-Pro

企业级 Agent 中心 AI 编排平台，提供 Agent、Knowledge、Workflow、Task、Plugin 与 Observability 的统一构建和运行能力。

## 项目概述

SOIT-Pro 是一个企业级的 LLM 开发平台，采用前后端分离架构。当前产品主结构已经收敛到 Agent 中心：Agent 作为主业务对象，Thread/Task/Run 作为统一执行账本，Knowledge/Workflow/Skill 作为能力层，Plugin/MCP 作为安装与集成层。项目遵循清晰分层与稳定内核原则，确保核心层稳定、领域层可持续迭代。

## 技术栈

### 后端技术栈 (app/)

**核心框架与运行时：**
- **Web 框架**: FastAPI 0.114+ (Python 3.11+)
- **ORM**: SQLModel 0.0.24 (基于 SQLAlchemy 2.0.31)
- **异步支持**: asyncio, aiohttp 3.11+, httpx 0.25+
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
- **OpenAI**: openai 1.6.1 (GPT 模型调用)
- **LangChain**: langchain 0.3.25, langchain-community 0.3.20 (AI 应用框架)
- **向量模型**: sentence-transformers 4.1+, langchain-huggingface 0.0.6 (嵌入模型)
- **Token 计算**: tiktoken 0.9+ (Token 计数)

**文档处理：**
- **PDF**: pypdf 5.6.0
- **Word**: python-docx 1.0.1
- **Excel**: pandas 2.1.4, openpyxl 3.1.2
- **PowerPoint**: python-pptx 1.0.2
- **Markdown**: markdown 3.5.1
- **HTML**: beautifulsoup4 4.12.2
- **文件类型检测**: python-magic 0.4.27

**开发工具：**
- **代码质量**: ruff 0.2+ (linting 和格式化)
- **类型检查**: mypy 1.15+ (静态类型检查)
- **测试框架**: pytest 7.4+, pytest-asyncio 0.23+ (单元测试和集成测试)
- **Git Hooks**: pre-commit 3.6+ (代码提交前检查)

### 前端技术栈 (web/)

**核心框架：**
- **框架**: React Router 7 (SSR 支持)
- **语言**: TypeScript 5.8
- **构建工具**: Vite 6

**UI 与样式：**
- **UI 组件库**: Radix UI (无障碍组件)
- **样式框架**: TailwindCSS 4 (实用优先的 CSS 框架)

**状态管理与数据获取：**
- **状态管理**: Zustand (轻量级状态管理)
- **数据获取**: React Query (服务端状态管理)

**可视化：**
- **图表库**: ECharts + Recharts (数据可视化)
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
- Nginx (反向代理和负载均衡)
- API 服务 (FastAPI 应用)
- Web 服务 (React Router SSR 应用)
- Celery Worker (异步任务处理)
- Flower (Celery 监控界面)

## 项目结构

```
soit-pro/
├── app/                    # 后端应用
│   ├── app/               # 应用代码
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
- [后端架构文档](app/docs/architecture/PROJECT_STRUCTURE.md)
- [前端结构文档](web/docs/PROJECT_STRUCTURE.md)
- [AGENTS规范文档](AGENTS.md)
- [开发规范文档](dev.md)
- [工程指南](app/docs/engineering/ENGINEERING_GUIDE.md)
- [架构文档](app/docs/architecture/)
- [历史规划归档](docs/archive/README.md)

## 快速开始

### 后端开发

```bash
cd app
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
docker compose up -d
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

## 许可证

[待补充]
