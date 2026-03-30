# Agent-Centered Platform Convergence Design

Date: 2026-03-30
Status: Proposed
Scope: Product IA, naming convergence, runtime capability model, observability console

## 1. Goal

Reshape SOIT into an Agent-centered platform without removing the first-level `Chat` entry, while cleaning out legacy `App/Application/Dataset` semantics and aligning frontend IA, backend contracts, capability binding, and observability around a single long-term model.

## 2. Context

The current codebase is already partially converged:

- Frontend routes are centered on `agents`, `chat`, `workflow`, `knowledge`, `tasks`, and `observability`.
- Backend public APIs are centered on `/api/v1/agents`, `/threads`, `/tasks`, `/knowledge`, `/workflows`, `/runs`, `/plugins`, `/responses`.
- Agent versioning and release management already exist.
- Agent version create contracts already support `workflow_refs`, `skill_refs`, and `plugin_refs`.

But the platform still has structural drift:

- Frontend i18n and page copy still contain `App` semantics.
- Navigation still behaves like parallel product domains rather than an Agent-centered platform.
- Capability binding is only partially unified.
- Observability is still close to a run explorer, not a workspace control console.
- Legacy naming and compatibility fields still exist in runtime-facing code.

## 3. Decisions Locked In

### 3.1 Platform Core

SOIT is centered on `Agent` as the primary runtime subject.

### 3.2 Chat Positioning

`Chat` remains a first-level navigation entry, but it is not an independent product domain.

It is the `Agent-focused workbench` for using Agents through multiple sessions.

### 3.3 Chat Workbench Behavior

- `/chat` defaults to the last used Agent.
- `/chat` shows only the selected Agent's threads.
- Switching Agent switches the thread list to that Agent.
- After switching Agent, the UI opens that Agent's last thread.
- Agent creation and configuration stay in `/agents`.
- `/chat` is for selection, usage, and session management only.

### 3.4 Capability Governance vs Runtime Capability

`Knowledge`, `Skill`, `Plugin`, and `MCP` remain first-level entries, but they are governance surfaces, not competing primary product subjects.

### 3.5 Observability Positioning

`/observability` defaults to a `Workspace Console`, not a run list and not a single-Agent homepage.

### 3.6 Capability Registry Model

The unified runtime capability registry must not treat `MCP` as a top-level runtime capability type.

Instead:

- `Plugin` is an installation and distribution unit.
- `MCP` is an integration and discovery unit.
- Runtime capability types are:
  - `model`
  - `knowledge`
  - `workflow`
  - `skill`
  - `tool`

Each capability entry carries origin metadata such as:

- `source_kind`: `builtin | native | plugin | mcp`
- `source_id`
- `source_version`
- provider-specific metadata when needed

## 4. Chosen Approach

The chosen product shape is `Hybrid Workbench`.

This means:

- `Agents` is the assembly console.
- `Chat` is the Agent-focused usage workbench.
- `Workflow` is the orchestration surface.
- `Knowledge / Skill / Plugin / MCP` are global governance surfaces that also feed Agent assembly.
- `Tasks` is the execution control surface.
- `Observability` is the workspace control console.

This approach was chosen because it preserves the current route and module structure while still producing a clear Agent-centered long-term model.

## 5. Information Architecture

### 5.1 Navigation Order

The navigation should converge to:

1. `Agents`
2. `Chat`
3. `Workflow`
4. `Knowledge`
5. `Skills`
6. `Plugins`
7. `MCP`
8. `Tasks`
9. `Observability`
10. `Models`
11. `Settings`

### 5.2 Meaning of Each Entry

#### Agents

Primary assembly surface for:

- creating Agents
- editing Agent profile and runtime shell
- binding capabilities
- creating versions
- publishing releases
- entering chat and runtime views

#### Chat

Primary usage surface for:

- choosing an Agent
- opening an Agent's threads
- creating new threads for the current Agent
- continuing prior threads
- jumping from a thread into run, task, or trace evidence

#### Workflow

Orchestration capability surface for:

- designing workflow graphs
- publishing workflows
- understanding which Agents use each workflow
- understanding which runs invoked each workflow

#### Knowledge / Skills / Plugins / MCP

Global capability governance surfaces for:

- install/register
- configure
- publish or enable
- inspect usage by Agents
- inspect execution and failure signals

#### Tasks

Execution control surface for:

- queued work
- blocked work
- approval-required work
- failed work
- retry/cancel/control operations

#### Observability

Workspace console for:

- workspace health
- run and task volume
- Agent-level performance and failure rates
- model cost
- knowledge retrieval quality
- tool reliability
- workflow bottlenecks

### 5.3 Navigation Rules

- No first-level `App` or `Application` entry may remain.
- `Chat` must not be described as an independent product ontology.
- Governance surfaces must not visually compete with Agent as the primary platform subject.
- Breadcrumbs, buttons, empty states, filters, search placeholders, and metrics labels must follow the same terminology.

## 6. Page Responsibilities

### 6.1 `/agents`

`/agents` is the assembly console.

The Agent detail page should evolve into a structured assembly surface with sections or tabs for:

- `Overview`
- `Bindings`
- `Versions`
- `Releases`
- `Runtime Entry`

The `Bindings` section becomes the formal configuration panel for all Agent-attached runtime capabilities.

Primary actions:

- bind model
- bind knowledge
- bind workflow
- bind skill
- bind plugin
- bind tool
- create version
- publish version
- open chat
- open runs/observability

### 6.2 `/chat`

`/chat` is the Agent-focused workbench.

Layout:

- Agent switcher
- thread list for the selected Agent only
- thread view

Behavior:

- default Agent = last used Agent
- default thread = that Agent's last thread
- creating a new thread attaches it to the current Agent
- thread view must expose run/task/trace links
- if the Agent is not runnable, the workbench must show an explicit blocked state

Blocked states include:

- no publishable or active version
- missing required model binding
- disabled or invalid tool dependency
- permission failure for current workspace/user

### 6.3 `/workflow`

`/workflow` remains a first-level entry, but its framing changes from standalone product domain to orchestration capability domain.

Every workflow detail view should answer:

- which Agents bind or reference this workflow
- which runs recently executed it
- where bottlenecks or failures occur

### 6.4 `/knowledge`, `/skills`, `/plugins`, `/mcp`

These pages remain as global governance surfaces.

Each detail page must expose:

- installation or registration state
- publish/enable state
- which Agents bind it
- recent execution usage
- success/failure health

They are not just CRUD pages. They must participate in the lifecycle:

- install/register
- bind
- execute
- observe

### 6.5 `/tasks`

`/tasks` is the control plane for execution work, not a passive archive.

Default prioritization:

- pending approvals
- blocked tasks
- failed tasks
- retryable tasks

### 6.6 `/observability`

`/observability` is the workspace console.

Default sections:

- workspace summary
- active Agents
- run volume
- cost summary
- failure summary
- approvals summary

Main drill-down views:

- by Agent
- by Workflow
- model cost
- knowledge retrieval quality
- tool health
- workflow bottlenecks
- run explorer

The run explorer remains available, but it becomes a child view, not the default landing page.

## 7. Runtime Capability Model

### 7.1 Agent Assembly Contract

The formal Agent version assembly contract should converge to:

- `model_ref`
- `knowledge_refs`
- `workflow_refs`
- `skill_refs`
- `plugin_refs`
- `tool_refs`

This contract intentionally does not include:

- `mcp_server_refs`
- `mcp_tool_refs`
- `mcp_resource_refs`

Reason:

- Agent assembly should not depend on MCP integration internals.
- Runtime invocation should unify on `tool` as the execution-facing abstraction.
- MCP remains visible in governance and source metadata, not in the Agent's runtime-facing binding vocabulary.

### 7.2 Tool Unification

`tool_refs` is the unified runtime binding channel for executable external or built-in tools, including:

- native platform tools
- plugin-provided tools
- MCP-provided tools
- future tool providers

### 7.3 Capability Registry

The unified runtime capability registry should only classify runtime-consumed capability forms:

- `model`
- `knowledge`
- `workflow`
- `skill`
- `tool`

It should not classify by integration source.

Integration source remains metadata:

- `source_kind`
- `source_id`
- `source_version`

### 7.4 Governance Layer

Governance surfaces may still maintain richer source-domain objects such as:

- plugin package and installation records
- MCP server configuration, discovery, and exposed resources/tools

But those should resolve into the runtime capability registry before Agent binding and runtime invocation.

## 8. Observability Model

### 8.1 Runtime Ledger

The workspace console should be built on a unified runtime ledger:

- `Thread`
- `Task`
- `Run`
- `RunStep`
- `Response / ResponseEvent`
- `Artifact`
- `Trace`
- `Cost`

### 8.2 Required Workspace Console Views

The workspace console must support:

- workspace summary
- Agent summary
- workflow bottlenecks
- model cost analysis
- knowledge retrieval quality
- tool reliability and failure rate

### 8.3 Capability Observability Rules

Every registry-backed capability should answer:

- who binds me
- who invoked me
- how often I fail
- how much time and cost I add

For tools, the console should support source-based drill-down such as:

- tool calls by `source_kind=mcp`
- tool calls by `source_kind=plugin`

This preserves MCP-specific visibility without turning MCP into a first-class runtime capability type.

## 9. Naming Convergence and Compatibility Removal

### 9.1 Allowed Platform Vocabulary

Runtime and UI vocabulary should converge to:

- Agent
- Thread / Chat
- Task
- Run / RunStep / Artifact / Cost
- Response / ResponseEvent
- Workflow
- Skill
- Knowledge
- Plugin
- MCP
- Trace / Observability

### 9.2 Forbidden Legacy Runtime Vocabulary

New runtime-facing code must not introduce or preserve:

- `app`
- `application`
- `dataset`
- `legacy`
- `compatibility`
- `bridge`
- `facade`

Exceptions:

- historical migration comments
- tests that explicitly assert legacy routes are offline

### 9.3 Compatibility Removal Targets

P0 cleanup must cover:

- frontend i18n
- page copy
- button and action labels
- route aliases
- API aliases
- compatibility DTO fields
- compatibility tests
- database fields and constraint names where still misleading

## 10. Iteration Plan

### Iteration 1: P0 Semantic Cutover

Goals:

- remove `App/Application/Dataset` runtime-facing language
- delete compatibility routes and aliases
- clean i18n, page copy, empty states, labels
- clean compatibility schema fields where possible
- keep only explicit anti-regression tests for removed legacy endpoints

Exit criteria:

- no runtime-facing UI or API entry point uses old subject names
- no new code path depends on compatibility alias behavior

### Iteration 2: Agent-Centered Frontend IA

Goals:

- reorder navigation
- reframe `Agents`, `Chat`, and `Observability`
- turn Agent detail into the assembly console
- turn Chat into the Agent-focused workbench

Exit criteria:

- users can understand the platform as `assemble -> use -> observe`

### Iteration 3: Unified Capability Registry and Binding

Goals:

- formalize runtime capability registry
- unify tool binding through `tool_refs`
- normalize governance surfaces to feed the registry
- remove source-specific runtime binding vocabulary

Exit criteria:

- Agent assembly vocabulary is stable
- tools can come from native, plugin, or MCP without changing Agent contract

### Iteration 4: Observability Workspace Console

Goals:

- replace run-list-first observability landing
- add workspace, Agent, workflow, model cost, retrieval quality, and tool health views

Exit criteria:

- `/observability` behaves like a platform console

### Iteration 5: Hardening and Anti-Regression

Goals:

- clean docs, seeds, fixtures, tests, and migration naming
- add guardrails against legacy term reintroduction

Exit criteria:

- convergence is durable and does not regress with normal feature work

## 11. Error Handling and Risk Controls

### 11.1 Chat Workbench Failure Modes

The UI must explicitly handle:

- no last-used Agent
- last-used Agent deleted
- selected Agent has no threads
- selected Agent not runnable
- missing permissions

### 11.2 Registry Migration Risk

Main risk:

- capability governance and runtime consumption drift apart again

Mitigation:

- keep a single registry identity model
- let governance pages resolve into registry entries instead of inventing separate runtime identities

### 11.3 Observability Risk

Main risk:

- UI-first observability without ledger alignment

Mitigation:

- build the console from runtime ledger entities and capability identities, not from ad hoc frontend summaries

## 12. Test Strategy

Required verification for implementation:

- frontend route and navigation tests for IA changes
- i18n/text checks for removed legacy subject names
- API tests proving legacy routes remain offline
- Agent version binding tests for unified `tool_refs`
- registry resolution tests proving plugin and MCP tools converge into `tool` runtime type
- observability query tests for Agent, workflow, cost, and tool-health views

## 13. Out of Scope

This design does not include:

- multi-Agent conversation inside a single thread
- replacing governance surfaces with Agent-only configuration
- removing the first-level Chat entry
- full visual redesign unrelated to information architecture and terminology convergence

## 14. Success Criteria

The convergence is successful when:

- users understand the platform as Agent-centered within one navigation pass
- Chat remains easy to use while clearly subordinate to Agent ownership
- capability binding vocabulary is stable and source-agnostic at runtime
- observability is a true workspace console rather than a run table
- legacy `App/Application/Dataset` semantics stop leaking into product, API, and data design
