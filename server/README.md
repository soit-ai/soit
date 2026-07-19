# SOIT Backend

Main backend workspace for SOIT.

- `app/kernel/`: long-term stable core (contracts, ports, specs, trace, security)
- `app/modules/`: product domains (services/repositories/models)
- `app/adapters/`: infra implementations (LLM/vector/storage/secrets/tools)
- `app/api/`: FastAPI transport layer (routers, SSE/WS)
- `docs/`: engineering/architecture/spec assets


# SOIT 项目架构

## 项目概述

SOIT 是一个企业级的AI可编排平台，提供完整的 AI 应用构建、部署和管理能力。项目采用前后端分离架构，支持多租户、知识库管理、工作流编排、插件系统等核心功能。

## 技术架构

### 后端架构 (API)

**核心技术栈：**
- **Web 框架**: FastAPI (Python 3.11+)
- **ORM**: SQLModel (基于 SQLAlchemy 2.0)
- **数据库**: PostgreSQL 15
- **缓存/任务队列**: Redis + Celery
- **向量数据库**: Milvus 2.5
- **对象存储**: MinIO (支持 S3、OSS、COS、GCS 等)
- **包管理**: uv
- **数据库迁移**: Alembic
- **监控**: Sentry
- **代码质量**: ruff (linting), Pyright (type checking), pytest (testing)


### 前端架构 (Web)

**核心技术栈：**
- **框架**: React Router 7 (SSR 支持)
- **语言**: TypeScript 5.8
- **UI 库**: Radix UI + TailwindCSS 4
- **状态管理**: Zustand + React Query
- **国际化**: i18next
- **图表**: Recharts
- **工作流可视化**: React Flow (@xyflow/react)
- **代码高亮**: Shiki
- **构建工具**: Vite 6

### 基础设施

**Docker Compose 服务：**
- PostgreSQL 15 (主数据库)
- Redis 7 (缓存和消息队列)
- Milvus 2.5 (向量数据库)
- etcd (Milvus 元数据存储)
- MinIO (对象存储)
- Nginx (反向代理)
- API 服务 (FastAPI)
- Web 服务 (React Router SSR)

### 项目结构
SOIT 是一个功能完整、架构清晰的 LLM 开发平台项目。项目采用了现代化的技术栈，具有良好的扩展性和可维护性。通过以上优化建议的实施，可以进一步提升项目的质量、性能和用户体验。
