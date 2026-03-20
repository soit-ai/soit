# SOIT Current Object Landscape

This document summarizes the active platform object model after the refactor.

## Primary Objects

| Active Object | Role |
|---|---|
| Agent | Primary user-facing intelligent capability |
| AgentVersion | Immutable agent configuration snapshot |
| AgentBinding | Agent-scoped resource binding |
| AgentPublish | Agent publish lifecycle record |
| Workflow | Structured execution capability |
| WorkflowVersion | Immutable workflow graph snapshot |
| Thread | Conversation/session container |
| ThreadMessage | Conversation ledger entry |
| Knowledge | Knowledge storage and retrieval capability |
| Run | Unified execution record |
| RunStep | Step-level execution trace |
| RunArtifact | Execution artifact record |
| RunCostEntry | Normalized execution cost record |

## Capability Areas

| Module Area | Responsibility |
|---|---|
| `modules/agent` | Agent CRUD, publish, and execution |
| `modules/workflow` | Workflow definition, versioning, and runtime execution |
| `modules/knowledge` | Knowledge storage, ingest, indexing, and retrieval |
| `modules/plugin` | Plugin installation and lifecycle |
| `modules/modelhub` | Model registry and provider policy |
| `modules/memory` | Memory capability services |
| `modules/integrations/mcp` | MCP integration services |

## Runtime Areas

| Runtime Surface | Responsibility |
|---|---|
| `kernel/runtime` | Shared runtime contracts and orchestration primitives |
| `kernel/trace` | Unified run/step/artifact/cost trace ledger |
| `kernel/responses` | Response resource and semantic projection layer |
| `kernel/projections` | Derived projection builders for active specs |
