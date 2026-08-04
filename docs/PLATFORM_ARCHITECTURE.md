# SOIT Platform Architecture

This document summarizes the current SOIT platform architecture. The
boundaries in the diagrams come from the root `README.md`,
`server/docs/architecture/PROJECT_STRUCTURE.md`,
`web/docs/PROJECT_STRUCTURE.md`, and the current source tree.

## Platform Overview

```mermaid
flowchart TB
  Users["Users / Admins / Developers"]

  subgraph Web["web/ frontend application"]
    WebRoutes["route workbenches<br/>agents · chat · workflow · knowledge · tasks · observe"]
    WebUI["shared UI and business components<br/>components · hooks · stores · i18n"]
    WebServices["API clients<br/>services · request · config"]
    WebRoutes --> WebUI
    WebRoutes --> WebServices
  end

  subgraph Server["server/app backend platform"]
    Main["main.py<br/>FastAPI entry and router registration"]
    Middleware["middleware<br/>request_id · error · envelope"]

    subgraph API["api/v1 transport layer"]
      APIRoutes["REST · WebSocket · SSE<br/>agents · threads · tasks · knowledge · workflows · runs · plugins · responses"]
    end

    subgraph Modules["modules business domains"]
      Agent["agent"]
      Workflow["workflow"]
      Knowledge["knowledge"]
      ModelHub["modelhub"]
      Plugin["plugin / skill"]
      Observe["observe"]
      Security["identity · security · secrets"]
      Notification["notification"]
    end

    subgraph Kernel["kernel stable core"]
      Contracts["contracts · specs"]
      Runtime["runtime · execution · responses"]
      Registry["registry · projections"]
      Identity["identity · security"]
      Trace["trace · observe"]
      Events["events"]
      Ports["ports<br/>llm · tools · vector · storage · secrets"]
    end

    subgraph Adapters["adapters port implementations"]
      LLM["llm"]
      Tools["tools"]
      Vector["vector"]
      Storage["storage"]
      Secrets["secrets"]
      PluginAdapters["plugins"]
    end

    subgraph Infra["infra infrastructure"]
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

  subgraph DataInfra["data and runtime infrastructure"]
    PostgreSQL["PostgreSQL<br/>business data · run ledger · outbox"]
    Redis["Redis<br/>cache · queues"]
    Milvus["Milvus<br/>vector retrieval"]
    MinIO["MinIO<br/>object storage"]
    Vault["Vault<br/>secret management"]
    Celery["Celery / workers<br/>async tasks · event dispatch"]
  end

  subgraph External["external capabilities"]
    ModelProviders["model providers<br/>OpenAI · Anthropic · DeepSeek · Qwen · compatible APIs"]
    MCP["MCP servers"]
    PluginSources["plugins / built-in tools"]
    ThirdParty["governed external HTTP / enterprise systems"]
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

## Core Execution Path

```mermaid
sequenceDiagram
  autonumber
  participant User as User
  participant Web as web workspace
  participant API as api/v1
  participant Module as domain module
  participant Kernel as kernel runtime
  participant DB as PostgreSQL
  participant Outbox as outbox / events
  participant Worker as Celery worker
  participant Adapter as governed adapter
  participant External as external model/tool/storage

  User->>Web: start a chat, task, workflow, or knowledge operation
  Web->>API: REST / WebSocket / SSE
  API->>Module: orchestrate the request and call business services
  Module->>Kernel: use specs, registry, runtime, security, ports
  Kernel->>DB: write Run / Task / RunStep / Trace / state transitions
  Kernel->>Outbox: record events pending dispatch
  Outbox->>Worker: reliably dispatch async events
  Worker->>Adapter: execute side effects through port implementations
  Adapter->>External: call models, tools, vector store, object storage, or secret service
  Adapter-->>Kernel: return results, cost, latency, error details
  Kernel->>DB: update ledger, trace, observability data
  API-->>Web: return synchronous results or streamed events
  Web-->>User: show run status, approvals, feedback, and detail
```

## Architecture Boundaries

- `web/` owns the user workspace, routes, state, and API clients; it carries
  no backend business rules.
- `api/` only handles HTTP, WebSocket, and SSE transport plus request
  orchestration, and stays thin.
- `modules/` carries the business domain logic for agent, workflow,
  knowledge, plugin, observe, and related domains.
- `kernel/` is the stable core defining contracts, specs, runtime, registry,
  security, events, and ports; `kernel/` does not depend on `modules/`.
  Execution and persistence state are concentrated in `kernel/runtime/`,
  where run traces belong to `runtime/runs/`.
- `adapters/` implements kernel ports and connects models, tools, the vector
  store, object storage, and secret systems; it contains no business logic.
- `infra/` provides infrastructure capabilities such as database sessions and
  the OpenTelemetry SDK/OTLP configuration.
- External calls must go through governed adapters/gateways; business code
  never calls model SDKs, HTTP clients, or external services directly.

## Design Principle Mapping

- Spec-first: platform primitives such as Agent, Workflow, Tool, Knowledge,
  and Plugin are constrained by versioned specs/contracts.
- Scope-by-default: the API, business domains, and data layer are organized
  around tenant/workspace scope.
- Trace everything: execution lands uniformly in Run, Task, RunStep, Cost,
  and observe data, and W3C Trace Context links API, Outbox, Knowledge
  Worker, database, HTTP, LLM, and Tool spans; `run_id`, `step_id`, and
  `trace_id` are the correlation keys between product audit and the technical
  call chain.
- Gateway-only: LLM, tool, vector, storage, and secrets access goes through
  ports/adapters.
- Immutable versions: agent, workflow, skill, and plugin versions are
  append-only, and release pointers express the currently published state.

## Deployment Topology

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

## Frontend Information Architecture

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
    Observe["observe<br/>runs · approvals · feedback"]
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

## Backend Boundary Diagram

```mermaid
flowchart LR
  Transport["api/v1<br/>transport orchestration"]
  AppServices["modules/*/application<br/>business use cases"]
  Domain["modules<br/>agent · workflow · knowledge · plugin · modelhub · security"]
  KernelContracts["kernel contracts/specs<br/>stable platform language"]
  KernelRuntime["kernel runtime<br/>tasks · threads · runs · responses"]
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

## Runtime Event Diagram

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

## Capability and Version Governance

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

  AgentCatalog["agent capability catalog<br/>assembly candidates"]
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

  Sources --> AgentCatalog
  AgentCatalog --> Binding
  Binding --> Versions
  Policy --> Binding
  Secrets --> Binding
  Versions --> Release
  Release --> RuntimeUse
  RuntimeUse --> Audit
```
