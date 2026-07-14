# SOIT 平台架构图

本文档汇总 SOIT-Pro 当前平台架构。图中边界来自根目录 `README.md`、`server/docs/architecture/PROJECT_STRUCTURE.md`、`web/docs/PROJECT_STRUCTURE.md` 以及当前源码目录。

## 平台总览

```mermaid
flowchart TB
  Users["用户 / 管理员 / 开发者"]

  subgraph Web["web/ 前端应用"]
    WebRoutes["路由工作台<br/>agents · chat · workflow · knowledge · tasks · observability"]
    WebUI["共享 UI 与业务组件<br/>components · hooks · stores · i18n"]
    WebServices["API 客户端<br/>services · request · config"]
    WebRoutes --> WebUI
    WebRoutes --> WebServices
  end

  subgraph Server["server/app 后端平台"]
    Main["main.py<br/>FastAPI 入口与路由注册"]
    Middleware["middleware<br/>request_id · error · envelope"]

    subgraph API["api/v1 传输层"]
      APIRoutes["REST · WebSocket · SSE<br/>agents · threads · tasks · knowledge · workflows · runs · plugins · responses"]
    end

    subgraph Modules["modules 业务域"]
      Agent["agent"]
      Workflow["workflow"]
      Knowledge["knowledge"]
      Capability["capability_registry"]
      ModelHub["modelhub"]
      Plugin["plugin / skill"]
      Observability["observability"]
      Security["identity · security · secrets"]
      Notification["notification"]
    end

    subgraph Kernel["kernel 稳定核心"]
      Contracts["contracts · specs"]
      Runtime["runtime · execution · responses"]
      Registry["registry · projections"]
      Identity["identity · security"]
      Trace["trace · observability"]
      Events["events"]
      Ports["ports<br/>llm · tools · vector · storage · secrets"]
    end

    subgraph Adapters["adapters 端口实现"]
      LLM["llm"]
      Tools["tools"]
      Vector["vector"]
      Storage["storage"]
      Secrets["secrets"]
      PluginAdapters["plugins"]
    end

    subgraph Infra["infra 基础设施"]
      DBSession["db session"]
    end

    Main --> Middleware
    Middleware --> APIRoutes
    APIRoutes --> Modules
    Modules --> Kernel
    Modules --> Ports
    Adapters -. implements .-> Ports
    Modules --> Infra
    Adapters --> Infra
  end

  subgraph DataInfra["数据与运行基础设施"]
    PostgreSQL["PostgreSQL<br/>业务数据 · 运行账本 · outbox"]
    Redis["Redis<br/>缓存 · 队列"]
    Milvus["Milvus<br/>向量检索"]
    MinIO["MinIO<br/>对象存储"]
    Vault["Vault<br/>密钥管理"]
    Celery["Celery / workers<br/>异步任务 · 事件分发"]
  end

  subgraph External["外部能力"]
    ModelProviders["模型供应商<br/>OpenAI · Anthropic · DeepSeek · Qwen · compatible APIs"]
    MCP["MCP servers"]
    PluginSources["插件 / 内置工具"]
    ThirdParty["受控外部 HTTP / 企业系统"]
  end

  Users --> Web
  WebServices -->|"REST / WS / SSE"| APIRoutes

  Infra --> PostgreSQL
  Infra --> Redis
  Infra --> Celery
  Vector --> Milvus
  Storage --> MinIO
  Secrets --> Vault
  LLM --> ModelProviders
  Tools --> MCP
  Tools --> ThirdParty
  PluginAdapters --> PluginSources
```

## 核心执行链路

```mermaid
sequenceDiagram
  autonumber
  participant User as 用户
  participant Web as web 工作台
  participant API as api/v1
  participant Module as domain module
  participant Kernel as kernel runtime
  participant DB as PostgreSQL
  participant Outbox as outbox / events
  participant Worker as Celery worker
  participant Adapter as governed adapter
  participant External as 外部模型/工具/存储

  User->>Web: 发起聊天、任务、工作流或知识操作
  Web->>API: REST / WebSocket / SSE
  API->>Module: 编排请求并调用业务服务
  Module->>Kernel: 使用 specs、registry、runtime、security、ports
  Kernel->>DB: 写入 Run / Task / RunStep / Trace / 状态变更
  Kernel->>Outbox: 记录待分发事件
  Outbox->>Worker: 可靠分发异步事件
  Worker->>Adapter: 通过端口实现执行副作用
  Adapter->>External: 调用模型、工具、向量库、对象存储或密钥服务
  Adapter-->>Kernel: 返回结果、成本、延迟、错误信息
  Kernel->>DB: 更新账本、trace、观测数据
  API-->>Web: 返回同步结果或流式事件
  Web-->>User: 展示运行状态、审批、反馈和详情
```

## 架构边界

- `web/` 负责用户工作台、路由、状态和 API 客户端，不承载后端业务规则。
- `api/` 只做 HTTP、WebSocket、SSE 传输和请求编排，保持薄层。
- `modules/` 承载 agent、workflow、knowledge、plugin、observability 等业务域逻辑。
- `kernel/` 是稳定核心，定义 contracts、specs、runtime、registry、security、trace、events 和 ports；`kernel/` 不依赖 `modules/`。
- `adapters/` 实现 kernel ports，连接模型、工具、向量库、对象存储和密钥系统，不放业务逻辑。
- `infra/` 提供数据库会话等基础设施能力。
- 外部调用必须经由受治理的 adapters/gateways，业务代码不直接调用模型 SDK、HTTP 客户端或外部服务。

## 设计原则映射

- Spec-first: Agent、Workflow、Tool、Knowledge、Plugin 等平台原语由版本化 specs/contracts 约束。
- Scope-by-default: API、业务域和数据层围绕 tenant/workspace 作用域组织。
- Trace everything: 执行统一落到 Run、Task、RunStep、Trace 和 observability 数据。
- Gateway-only: LLM、tool、vector、storage、secrets 通过 ports/adapters 接入。
- Immutable versions: agent、workflow、skill、plugin 等版本追加写入，release 指针表达当前发布状态。

## 部署拓扑图

```mermaid
flowchart TB
  Browser["Browser<br/>SOIT workspace"]
  WebApp["web app<br/>React Router · Vite build"]
  API["server/app<br/>FastAPI API"]
  Worker["workers<br/>Celery · event dispatch"]

  subgraph RuntimeInfra["runtime infrastructure"]
    Postgres["PostgreSQL<br/>business data · run ledger · outbox"]
    Redis["Redis<br/>broker · cache"]
    Milvus["Milvus<br/>vector collections"]
    MinIO["MinIO<br/>documents · artifacts"]
    Vault["Vault<br/>workspace secrets"]
  end

  subgraph Providers["external providers"]
    LLMs["LLM providers"]
    MCPServers["MCP servers"]
    Enterprise["enterprise systems"]
  end

  Browser -->|"HTTP"| WebApp
  WebApp -->|"REST / WS / SSE"| API
  API --> Postgres
  API --> Redis
  API --> Milvus
  API --> MinIO
  API --> Vault
  Redis --> Worker
  Postgres --> Worker
  Worker --> Postgres
  Worker --> LLMs
  Worker --> MCPServers
  Worker --> Enterprise
```

## 前端信息架构图

```mermaid
flowchart TB
  Root["root.tsx / routes.ts"]
  Layout["layout<br/>root layout · nav layout · sidebar"]
  Services["services<br/>agent · knowledge · workflow · responses · security"]
  State["state layer<br/>stores · hooks · React Query"]
  UI["shared UI<br/>components · styles · i18n"]

  subgraph Workspaces["workspace routes"]
    Agents["agents<br/>agent workbench"]
    Chat["chat<br/>threaded execution"]
    Workflow["workflow<br/>DAG design surface"]
    Knowledge["knowledge<br/>base · documents · analytics"]
    Tasks["tasks<br/>execution queue · detail control"]
    Observability["observability<br/>runs · approvals · feedback"]
  end

  subgraph Admin["admin routes"]
    Plugins["plugin / skill / mcp"]
    Models["model"]
    Settings["setting / system"]
    Auth["auth"]
  end

  Root --> Layout
  Layout --> Workspaces
  Layout --> Admin
  Workspaces --> Services
  Admin --> Services
  Workspaces --> State
  Admin --> State
  State --> UI
  Services -->|"REST / WS / SSE"| Backend["api/v1"]
```

## 后端边界图

```mermaid
flowchart LR
  Transport["api/v1<br/>transport orchestration"]
  AppServices["modules/*/application<br/>business use cases"]
  Domain["modules<br/>agent · workflow · knowledge · plugin · modelhub · security"]
  KernelContracts["kernel contracts/specs<br/>stable platform language"]
  KernelRuntime["kernel runtime<br/>execution · responses · events · trace"]
  KernelPorts["kernel ports<br/>llm · tools · vector · storage · secrets"]
  Adapters["adapters<br/>replaceable implementations"]
  Infra["infra<br/>db session and infrastructure"]
  External["external systems"]

  Transport --> AppServices
  AppServices --> Domain
  Domain --> KernelContracts
  Domain --> KernelRuntime
  Domain --> KernelPorts
  Adapters -. implements .-> KernelPorts
  AppServices --> Infra
  Adapters --> Infra
  Adapters --> External
```

## 运行时事件图

```mermaid
flowchart TB
  Request["incoming request<br/>chat · task · workflow · knowledge"]
  Scope["identity and scope check<br/>tenant · workspace · RBAC"]
  Service["domain service"]
  Runtime["kernel runtime"]

  subgraph Transaction["database transaction"]
    State["domain state"]
    Ledger["run ledger<br/>Run · Task · RunStep · Trace"]
    Outbox["outbox events"]
  end

  Dispatcher["event dispatcher"]
  Worker["worker execution"]
  Gateway["governed adapter"]
  Result["result projection<br/>status · metrics · trace · SSE"]

  Request --> Scope
  Scope --> Service
  Service --> Runtime
  Runtime --> Transaction
  State --> Ledger
  Ledger --> Outbox
  Outbox --> Dispatcher
  Dispatcher --> Worker
  Worker --> Gateway
  Gateway --> Result
  Result --> Ledger
```

## 能力与版本治理图

```mermaid
flowchart TB
  subgraph Sources["capability sources"]
    Builtin["built-in tools"]
    Plugins["plugins"]
    MCP["MCP servers"]
    Models["model providers"]
    KnowledgeBase["knowledge bases"]
    Workflows["workflows"]
  end

  Registry["capability registry<br/>source-agnostic catalog"]
  Binding["typed binding<br/>capability id · source kind · version"]
  Policy["governance policy<br/>allowlist · egress · RBAC"]
  Secrets["workspace secrets<br/>Vault-backed visibility"]

  subgraph Versions["immutable versions"]
    AgentVersion["agent version"]
    WorkflowVersion["workflow version"]
    SkillVersion["skill/plugin version"]
  end

  Release["release pointer<br/>current production version"]
  RuntimeUse["runtime resolution<br/>model · tool · knowledge · workflow"]
  Audit["audit and trace<br/>who used what version"]

  Sources --> Registry
  Registry --> Binding
  Binding --> Versions
  Policy --> Binding
  Secrets --> Binding
  Versions --> Release
  Release --> RuntimeUse
  RuntimeUse --> Audit
```
