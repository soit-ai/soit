# Agent Bindings-Only Version Contract Design

Date: 2026-04-09
Status: Proposed
Scope: Backend agent version contract, spec persistence, runtime resolution

## 1. Goal

Make `bindings` the only capability-binding entry for `AgentVersionCreate` and the only persisted binding source in `agent.v1` version specs.

This change intentionally breaks old payload and old stored spec compatibility in order to remove duplicated binding semantics and silent merge behavior.

## 2. Context

The current agent version contract is structurally inconsistent.

`AgentVersionCreate` accepts both:

- top-level `model_ref`
- top-level `knowledge_refs`
- top-level `tool_refs`
- top-level `workflow_refs`
- top-level `skill_refs`
- nested `bindings.*`

The application service then merges these fields into one `AgentCapabilityBindings` object before building the version spec.

This creates several problems:

- the same capability can be expressed through two different API shapes
- `model_ref` is treated specially with explicit conflict validation, while list fields are silently merged
- persisted `spec_json` duplicates the same meaning across `bindings`, `model`, `tools`, and `rag`
- readers must keep fallback logic for old mirror fields instead of consuming one authoritative structure

The codebase is already moving toward consolidation.

- `plugin_refs` is already rejected as a top-level create field
- version rows are the release truth source and should not carry duplicate semantic representations
- `AgentBinding` synchronization and projection logic already treat capability references as structured bindings

## 3. Decisions Locked In

### 3.1 `bindings` is the only binding input

`AgentVersionCreate` will no longer accept top-level capability binding fields.

Removed top-level fields:

- `model_ref`
- `knowledge_refs`
- `tool_refs`
- `workflow_refs`
- `skill_refs`

`plugin_refs` is already removed and remains removed.

### 3.2 `bindings.model_ref` is mandatory

The model remains a version binding, not a loose runtime default.

The only valid model input path is:

- `bindings.model_ref`

This keeps the model in the same conceptual category as the other capability references and avoids a permanent schema exception.

### 3.3 Persisted version specs have one binding truth source

Capability bindings are persisted only under:

- `spec_json["bindings"]`

The following mirror fields are no longer written:

- `spec_json["model"]["ref_key"]`
- `spec_json["tools"]["allowlist"]`
- `spec_json["rag"]["knowledges"]`

### 3.4 No compatibility path for old specs

This change is a clean breaking change.

The system does not attempt to read or execute legacy `agent.v1` specs that rely on:

- top-level create fields
- `spec.model.ref_key`
- `spec.tools.allowlist`
- `spec.rag.knowledges`

Only the new bindings-only shape is supported after the cutover.

## 4. Chosen Approach

The chosen approach is `Bindings-Only Canonical Spec`.

Rules:

- API input uses `bindings` for all capability references
- spec persistence stores one binding structure
- runtime request derivation reads only that binding structure
- projection and binding sync read only that binding structure
- tests reject old payload shapes instead of accepting or translating them

This approach was chosen because it removes semantic duplication at the source instead of preserving compatibility shims in API, persistence, and runtime layers.

## 5. Contract Design

### 5.1 `AgentCapabilityBindings`

`AgentCapabilityBindings` becomes the canonical capability map for an agent version.

Fields:

- `model_ref: str`
- `knowledge_refs: list[str] | None`
- `tool_refs: list[str] | None`
- `workflow_refs: list[str] | None`
- `skill_refs: list[str] | None`
- `plugin_refs: list[str] | None`

Rules:

- `model_ref` is required
- all other lists are optional
- empty lists may be normalized to `None` when persisted
- no additional fields are allowed

### 5.2 `AgentVersionCreate`

`AgentVersionCreate` keeps only:

- `system_prompt`
- `bindings`
- `temperature`
- `max_iterations`
- `max_tool_calls`
- `max_llm_calls`
- `max_failures`
- `max_runtime_seconds`
- `max_tokens_total`
- `max_cost`
- `cost_currency`
- `memory_strategy`
- `memory_top_k`
- `verify`
- `failure_strategy`

Validation rules:

- `bindings` is required
- `bindings.model_ref` is required
- any removed top-level binding field causes validation failure

There is no merge behavior and no conflict resolution because there is only one valid source.

## 6. Persisted Spec Shape

### 6.1 New canonical shape

The version spec keeps configuration categories separate from capability identity.

Canonical shape:

```json
{
  "runtime": "agent_runtime_v1",
  "planner": null,
  "system_prompt": "...",
  "temperature": 0.1,
  "bindings": {
    "model_ref": "model:openai:gpt-5.1",
    "knowledge_refs": ["knowledge:kb_support"],
    "tool_refs": ["tool:test:echo"],
    "workflow_refs": ["wf:handoff"],
    "skill_refs": ["skill:triage"],
    "plugin_refs": ["plugin:soit:search:1.0.0"]
  },
  "memory": {
    "enabled": true,
    "type": "planner_only",
    "policy": {
      "top_k": 3
    }
  },
  "limits": {
    "max_iterations": 8,
    "max_tool_calls": 8,
    "max_llm_calls": 16,
    "max_failures": 2,
    "timeout_ms": 30000,
    "max_tokens": null,
    "budget": null
  },
  "policies": {
    "verify": true,
    "failure_strategy": "respond",
    "cost_currency": "USD"
  }
}
```

### 6.2 Forbidden mirror structures

The following structures are no longer part of the canonical spec contract for agent bindings:

- `model.ref_key`
- `tools.allowlist`
- `rag.knowledges`

If similar runtime views are needed internally, they must be derived in memory from `bindings` and must not be persisted as separate truth sources.

`temperature` remains a first-class execution configuration value, but it is no longer stored under `model.params` because the `model` object is no longer part of the canonical binding contract.

## 7. Runtime Resolution

### 7.1 Version creation

`create_version()` reads only `data.bindings`.

It does not:

- merge top-level and nested fields
- backfill missing bindings from legacy fields
- keep mirror binding state in multiple spec sections

### 7.2 Request derivation

`_request_from_version()` derives execution request fields from `spec["bindings"]` only.

Derived mapping:

- request `model` <- `bindings.model_ref`
- request `temperature` <- `spec.temperature`
- request `tool_refs` <- `bindings.tool_refs`
- request `knowledge_refs` <- `bindings.knowledge_refs`

`workflow_refs`, `skill_refs`, and `plugin_refs` remain version-level bindings and synchronized metadata even if the current execution loop does not directly consume them.

### 7.3 Binding synchronization

`_sync_bindings()` reads only `spec["bindings"]`.

It creates:

- one `model` binding from `bindings.model_ref`
- ordered `tool`, `knowledge`, `workflow`, `skill`, and `plugin` bindings from the corresponding lists

There is no fallback to `spec.model`, `spec.tools`, or `spec.rag`.

### 7.4 Projection and reference extraction

Projection code reads only `spec["bindings"]` for capability references.

This removes duplicate extracted references and removes the need to deduplicate the same binding identity from multiple spec paths.

## 8. Validation Changes

The runtime spec validator for `agent.v1` must be updated to recognize the bindings-only contract.

Required validation behavior:

- `bindings` must exist
- `bindings.model_ref` must exist
- removed mirror fields must not be required
- persisted specs that still include forbidden mirror binding structures must be rejected

Strict rejection is required because this is an intentional clean cutover, not a compatibility migration.

## 9. Error Handling

### 9.1 Create payload failures

Requests fail validation when:

- `bindings` is missing
- `bindings.model_ref` is missing
- a removed top-level binding field is present

### 9.2 Version execution failures

Execution fails fast when a version spec does not satisfy the new bindings-only contract.

This is acceptable because historical spec compatibility is explicitly out of scope for this change.

### 9.3 Publish behavior

Publish continues to validate and publish existing versions, but only versions created under the new contract are considered valid for execution.

## 10. Testing Strategy

Required test updates:

- schema tests proving old top-level fields are rejected
- schema tests proving `bindings.model_ref` is required
- integration tests creating versions only through `bindings`
- service tests proving request derivation reads only `spec.bindings`
- projection tests proving only `bindings` paths are emitted
- validation tests proving bindings-only specs are accepted
- validation tests proving legacy mirrored binding specs are rejected if strict validation is enabled

Required removals:

- tests that rely on top-level `model_ref`
- tests that rely on top-level `knowledge_refs`
- tests that rely on top-level `tool_refs`
- tests that rely on top-level `workflow_refs`
- tests that rely on fallback reads from `spec.model`, `spec.tools`, or `spec.rag`

## 11. Risks And Controls

Risk:

- breaking existing callers that still send top-level binding fields

Control:

- fail validation immediately and update all first-party callers and tests in the same change

Risk:

- historical versions in the database become non-executable

Control:

- accept this as part of the cutover and treat the new contract as the only supported runtime source

Risk:

- engineers reintroduce mirror fields later for convenience

Control:

- keep spec validation strict
- keep projection and execution code reading only `bindings`
- add tests that assert legacy shapes are invalid

## 12. Out Of Scope

This design does not include:

- a compatibility migration for existing stored agent versions
- automatic backfill of old version specs
- introducing a separate preview execution path for draft legacy versions
- redesigning workflow, skill, or plugin version contracts in this change

## 13. Success Criteria

The design is successful when:

- `AgentVersionCreate` has one capability-binding input shape
- `bindings.model_ref` is the only model binding entry
- agent version specs persist one canonical binding structure
- runtime request derivation reads only that structure
- binding sync and projection read only that structure
- old top-level binding payloads fail immediately
- old mirrored spec shapes are not part of the supported agent runtime contract
