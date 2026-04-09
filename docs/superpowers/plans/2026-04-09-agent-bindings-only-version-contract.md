# Agent Bindings-Only Version Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `bindings` the only capability-binding entry for `AgentVersionCreate` and the only supported persisted binding source for `agent.v1` specs while preserving non-binding execution settings such as `temperature`.

**Architecture:** The change removes top-level binding inputs from the create schema, makes `bindings.model_ref` mandatory, and rewires version creation, spec validation, projection, and execution to read only `spec.bindings`. The implementation is a clean breaking change: new writes use only the canonical bindings shape, and old mirrored spec shapes are rejected instead of translated.

**Tech Stack:** Python, FastAPI, Pydantic v2, SQLAlchemy, JSON Schema Draft 2020-12, pytest

---

## File Map

- Modify: `server/app/modules/agent/application/schemas.py`
  Responsibility: remove legacy top-level binding inputs from `AgentVersionCreate` and require `bindings.model_ref`.

- Modify: `server/app/modules/agent/application/application_service.py`
  Responsibility: stop merging legacy binding fields, persist only canonical `bindings`, derive runtime request fields only from `spec.bindings`, and sync DB bindings only from `spec.bindings`.

- Modify: `server/app/kernel/specs/v1/agent_spec.schema.json`
  Responsibility: define the bindings-only canonical spec shape, keep `temperature` as a top-level execution setting, and reject mirror binding structures such as `model`, `model_ref`, and `rag`.

- Modify: `server/app/kernel/projections/agent_projection.py`
  Responsibility: extract agent references only from `spec.bindings` plus non-binding inline refs that still belong in projection output.

- Modify: `server/tests/unit/test_agent_schema_naming_cleanup.py`
  Responsibility: cover schema-level breaking changes for the create payload.

- Modify: `server/tests/test_spec_validation.py`
  Responsibility: cover the new canonical `agent.v1` schema and rejection of forbidden mirror binding structures.

- Modify: `server/tests/unit/test_agent_ref_extractor.py`
  Responsibility: prove projection now reads bindings-only specs and no longer reads mirrored model/tool/rag bindings.

- Modify: `server/tests/integration/test_agent_publish_and_execute.py`
  Responsibility: create agent versions only through `bindings`, validate persisted spec shape, and validate execution reads runtime bindings from `spec.bindings`.

- Modify: `server/tests/entrypoints/test_agent_api.py`
  Responsibility: update API payloads to use `bindings` only and add request validation coverage for removed top-level fields.

- Optional inspect-only reference: `server/app/kernel/specs/validator.py`
  Responsibility: no direct logic change expected, but keep in view while adjusting schema-driven tests.

## Constraints

- This plan follows the approved breaking-change spec at `docs/superpowers/specs/2026-04-09-agent-bindings-only-version-contract-design.md`.
- Do not preserve compatibility reads for old persisted `agent.v1` specs.
- Do not introduce new fallback logic.
- Per user instruction, stage changes with `git add`; do not create commits while executing this plan.

### Task 1: Lock the create payload to `bindings`

**Files:**
- Modify: `server/app/modules/agent/application/schemas.py`
- Test: `server/tests/unit/test_agent_schema_naming_cleanup.py`

- [ ] **Step 1: Replace the schema tests with bindings-only expectations**

```python
import pytest
from pydantic import ValidationError

from app.modules.agent.application.schemas import AgentVersionCreate


def test_agent_version_create_requires_bindings_model_ref():
    payload = AgentVersionCreate(
        bindings={"model_ref": "model:test:primary"},
        verify=True,
    )

    assert payload.bindings is not None
    assert payload.bindings.model_ref == "model:test:primary"


@pytest.mark.parametrize(
    "legacy_field, legacy_value",
    [
        ("model_ref", "model:test:legacy"),
        ("knowledge_refs", ["knowledge:kb_support"]),
        ("tool_refs", ["tool:test:echo"]),
        ("workflow_refs", ["wf:handoff"]),
        ("skill_refs", ["skill:triage"]),
        ("plugin_refs", ["plugin:legacy"]),
    ],
)
def test_agent_version_create_rejects_legacy_top_level_binding_fields(legacy_field, legacy_value):
    with pytest.raises(ValidationError):
        AgentVersionCreate(
            bindings={"model_ref": "model:test:primary"},
            **{legacy_field: legacy_value},
        )


def test_agent_version_create_requires_bindings():
    with pytest.raises(ValidationError):
        AgentVersionCreate(
            verify=True,
        )
```

- [ ] **Step 2: Run the schema test file and verify it fails on the current contract**

Run: `uv run pytest server/tests/unit/test_agent_schema_naming_cleanup.py -q`
Expected: FAIL because `AgentVersionCreate` still accepts top-level `model_ref` and does not require `bindings`.

- [ ] **Step 3: Update `AgentCapabilityBindings` and `AgentVersionCreate` to remove legacy top-level binding fields**

```python
class AgentCapabilityBindings(BaseModel):
    """Unified capability bindings attached to an agent version."""

    model_config = ConfigDict(extra="forbid")

    model_ref: str
    knowledge_refs: Optional[List[str]] = None
    tool_refs: Optional[List[str]] = None
    workflow_refs: Optional[List[str]] = None
    skill_refs: Optional[List[str]] = None
    plugin_refs: Optional[List[str]] = None


class AgentVersionCreate(BaseModel):
    """Schema for creating an agent version."""

    model_config = ConfigDict(extra="forbid")

    system_prompt: Optional[str] = Field(default=None, max_length=8000)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_iterations: Optional[int] = Field(default=None, ge=1, le=50)
    max_tool_calls: Optional[int] = Field(default=None, ge=0, le=100)
    max_llm_calls: Optional[int] = Field(default=None, ge=1, le=200)
    max_failures: Optional[int] = Field(default=None, ge=0, le=10)
    max_runtime_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    max_tokens_total: Optional[int] = Field(default=None, ge=1)
    max_cost: Optional[float] = Field(default=None, ge=0.0)
    cost_currency: Optional[str] = None
    bindings: AgentCapabilityBindings
    memory_strategy: Optional[str] = Field(
        default=None,
        pattern="^(planner_only|system_message|user_message)$",
    )
    memory_top_k: Optional[int] = Field(default=None, ge=1, le=50)
    verify: Optional[bool] = None
    failure_strategy: Optional[str] = Field(
        default=None,
        pattern="^(respond|abort|continue)$",
    )
```

- [ ] **Step 4: Run the schema tests again and verify they pass**

Run: `uv run pytest server/tests/unit/test_agent_schema_naming_cleanup.py -q`
Expected: PASS

- [ ] **Step 5: Stage only the schema and schema-test changes**

Run: `git add server/app/modules/agent/application/schemas.py server/tests/unit/test_agent_schema_naming_cleanup.py`
Expected: `git diff --cached --name-only` includes only those two paths for this task.

### Task 2: Make `agent.v1` a bindings-only persisted spec

**Files:**
- Modify: `server/app/kernel/specs/v1/agent_spec.schema.json`
- Test: `server/tests/test_spec_validation.py`

- [ ] **Step 1: Rewrite the spec validation tests around the new canonical shape**

```python
import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.specs import validate_spec


def test_agent_spec_validation_with_bindings_only_shape():
    agent_doc = {
        "runtime": "agent_runtime_v1",
        "temperature": 0.1,
        "bindings": {
            "model_ref": "model:openai:gpt-4",
            "knowledge_refs": ["knowledge:kb_support"],
            "tool_refs": ["tool:test:echo"],
            "workflow_refs": ["wf:handoff"],
            "skill_refs": ["skill:triage"],
            "plugin_refs": ["plugin:soit:search:1.0.0"],
        },
        "policies": {"verify": True},
    }

    assert validate_spec(agent_doc, "agent_spec") is True


@pytest.mark.parametrize(
    "legacy_fragment",
    [
        {"model": {"ref_key": "model:openai:gpt-4"}},
        {"model_ref": "model:openai:gpt-4"},
        {"rag": {"knowledges": ["knowledge:kb_support"]}},
    ],
)
def test_agent_spec_validation_rejects_legacy_binding_mirrors(legacy_fragment):
    agent_doc = {
        "runtime": "agent_runtime_v1",
        "bindings": {"model_ref": "model:openai:gpt-4"},
        **legacy_fragment,
    }

    with pytest.raises(ValidationError):
        validate_spec(agent_doc, "agent_spec")
```

- [ ] **Step 2: Run the spec validation tests and verify they fail before the schema update**

Run: `uv run pytest server/tests/test_spec_validation.py -q`
Expected: FAIL because the current JSON schema still accepts `model` and `rag` mirror structures.

- [ ] **Step 3: Update `agent_spec.schema.json` to require `bindings.model_ref` and remove mirrored binding sections**

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["runtime", "bindings"],
  "properties": {
    "runtime": {
      "type": "string",
      "const": "agent_runtime_v1"
    },
    "temperature": {
      "type": ["number", "null"],
      "minimum": 0,
      "maximum": 2
    },
    "system_prompt": {
      "type": ["string", "null"],
      "maxLength": 8000
    },
    "planner": {
      "type": ["object", "null"],
      "additionalProperties": false,
      "properties": {
        "type": { "type": "string" },
        "params": { "type": ["object", "null"] }
      }
    },
    "bindings": {
      "type": "object",
      "additionalProperties": false,
      "required": ["model_ref"],
      "properties": {
        "model_ref": {
          "$ref": "refs.schema.json#/$defs/ModelRef"
        },
        "knowledge_refs": {
          "type": ["array", "null"],
          "items": {
            "$ref": "refs.schema.json#/$defs/KnowledgeRef"
          }
        },
        "tool_refs": {
          "type": ["array", "null"],
          "items": {
            "type": "string"
          }
        },
        "workflow_refs": {
          "type": ["array", "null"],
          "items": {
            "$ref": "refs.schema.json#/$defs/WorkflowRef"
          }
        },
        "skill_refs": {
          "type": ["array", "null"],
          "items": {
            "$ref": "refs.schema.json#/$defs/SkillRef"
          }
        },
        "plugin_refs": {
          "type": ["array", "null"],
          "items": {
            "$ref": "refs.schema.json#/$defs/PluginRef"
          }
        }
      }
    },
    "memory": {
      "type": ["object", "null"],
      "additionalProperties": false,
      "properties": {
        "enabled": { "type": ["boolean", "null"] },
        "type": { "type": ["string", "null"] },
        "policy": { "type": ["object", "null"] }
      }
    },
    "limits": {
      "type": ["object", "null"],
      "additionalProperties": false
    },
    "policies": {
      "type": ["object", "null"]
    }
  }
}
```

- [ ] **Step 4: Run the spec validation tests again and verify they pass**

Run: `uv run pytest server/tests/test_spec_validation.py -q`
Expected: PASS

- [ ] **Step 5: Stage only the schema JSON and spec-validation test changes**

Run: `git add server/app/kernel/specs/v1/agent_spec.schema.json server/tests/test_spec_validation.py`
Expected: `git diff --cached --name-only` now includes the files from Task 1 plus these two paths.

### Task 3: Remove legacy merge and mirror writes from `AgentApplicationService`

**Files:**
- Modify: `server/app/modules/agent/application/application_service.py`
- Test: `server/tests/integration/test_agent_publish_and_execute.py`

- [ ] **Step 1: Update the integration tests to create versions through `bindings` only and assert canonical persisted spec shape**

```python
version = await service.create_version(
    agent.id,
    AgentVersionCreate(
        system_prompt="You are precise.",
        bindings={
            "model_ref": "model:test:primary",
            "tool_refs": ["tool:test:echo"],
            "knowledge_refs": ["knowledge:kb_support"],
            "workflow_refs": ["wf:handoff"],
            "skill_refs": ["skill:triage"],
            "plugin_refs": ["plugin:soit:search:1.0.0"],
        },
        temperature=0.1,
        memory_strategy="planner_only",
        memory_top_k=3,
        verify=True,
    ),
)

assert version.spec_json["bindings"]["model_ref"] == "model:test:primary"
assert version.spec_json["bindings"]["tool_refs"] == ["tool:test:echo"]
assert version.spec_json["bindings"]["knowledge_refs"] == ["knowledge:kb_support"]
assert version.spec_json["temperature"] == 0.1
assert "model" not in version.spec_json
assert "tools" not in version.spec_json
assert "rag" not in version.spec_json
```

- [ ] **Step 2: Run the integration test file and verify it fails before the service update**

Run: `uv run pytest server/tests/integration/test_agent_publish_and_execute.py -q`
Expected: FAIL because the service still expects top-level fields and still writes mirrored `model`, `tools`, and `rag` sections.

- [ ] **Step 3: Rewrite `_build_spec`, `_request_from_version`, and `_sync_bindings` to consume `bindings` only**

```python
def _build_spec(
    self,
    data: AgentVersionCreate,
) -> Dict[str, Any]:
    bindings = data.bindings
    memory_enabled = data.memory_strategy is not None or data.memory_top_k is not None
    memory_policy: Dict[str, Any] = {}
    if data.memory_top_k is not None:
        memory_policy["top_k"] = data.memory_top_k
    return {
        "runtime": "agent_runtime_v1",
        "planner": None,
        "system_prompt": data.system_prompt,
        "temperature": data.temperature,
        "bindings": {
            "model_ref": bindings.model_ref,
            "knowledge_refs": bindings.knowledge_refs or None,
            "tool_refs": bindings.tool_refs or None,
            "workflow_refs": bindings.workflow_refs or None,
            "skill_refs": bindings.skill_refs or None,
            "plugin_refs": bindings.plugin_refs or None,
        },
        "memory": {
            "enabled": memory_enabled or None,
            "type": data.memory_strategy,
            "policy": memory_policy or None,
        },
        "limits": {
            "max_iterations": data.max_iterations,
            "max_tool_calls": data.max_tool_calls,
            "max_llm_calls": data.max_llm_calls,
            "max_failures": data.max_failures,
            "timeout_ms": data.max_runtime_seconds * 1000 if data.max_runtime_seconds else None,
            "max_tokens": data.max_tokens_total,
            "budget": data.max_cost,
        },
        "policies": {
            "verify": data.verify,
            "failure_strategy": data.failure_strategy,
            "cost_currency": data.cost_currency,
        },
    }


def _request_from_version(self, version: AgentVersion, inputs: Dict[str, Any]) -> AgentRunRequest:
    spec = version.spec_json or {}
    binding_spec = spec.get("bindings") or {}
    memory_spec = spec.get("memory") or {}
    memory_policy = memory_spec.get("policy") or {} if isinstance(memory_spec, dict) else {}
    limits = spec.get("limits") or {}
    policies = spec.get("policies") or {}
    messages = list(inputs.get("messages") or [])
    system_prompt = spec.get("system_prompt")
    if system_prompt and not any(message.get("role") == "system" for message in messages):
        messages = [{"role": "system", "content": system_prompt}] + messages
    payload = {
        "messages": messages,
        "model": inputs.get("model") or binding_spec.get("model_ref"),
        "temperature": inputs.get("temperature", spec.get("temperature")),
        "tool_refs": inputs.get("tool_refs", binding_spec.get("tool_refs")),
        "knowledge_refs": inputs.get("knowledge_refs", binding_spec.get("knowledge_refs")),
        "max_iterations": inputs.get("max_iterations", limits.get("max_iterations") or 8),
        "max_tool_calls": inputs.get("max_tool_calls", limits.get("max_tool_calls") or 8),
        "max_llm_calls": inputs.get("max_llm_calls", limits.get("max_llm_calls") or 16),
        "max_failures": inputs.get("max_failures", limits.get("max_failures") or 2),
        "max_runtime_seconds": inputs.get(
            "max_runtime_seconds",
            int(limits["timeout_ms"] / 1000) if limits.get("timeout_ms") else None,
        ),
        "max_tokens_total": inputs.get("max_tokens_total", limits.get("max_tokens")),
        "max_cost": inputs.get("max_cost", limits.get("budget")),
        "cost_currency": inputs.get("cost_currency", policies.get("cost_currency") or "USD"),
        "rag_top_k": inputs.get("rag_top_k", 5),
        "rag_strategy": inputs.get("rag_strategy", "system_message"),
        "memory_query": inputs.get("memory_query"),
        "memory_strategy": inputs.get("memory_strategy", memory_spec.get("type") or "planner_only"),
        "memory_top_k": inputs.get("memory_top_k", memory_policy.get("top_k") or 5),
        "context_window_messages": inputs.get("context_window_messages"),
        "context_window_chars": inputs.get("context_window_chars"),
        "verify": inputs.get("verify", policies.get("verify") if policies.get("verify") is not None else True),
        "failure_strategy": inputs.get("failure_strategy", policies.get("failure_strategy") or "respond"),
        "thread_id": inputs.get("thread_id"),
        "thread_title": inputs.get("thread_title"),
    }
    return AgentRunRequest.model_validate(payload)
```

- [ ] **Step 4: Remove `_resolve_version_bindings()` and legacy fallbacks from binding synchronization**

```python
def _sync_bindings(
    self,
    agent: Agent,
    version: AgentVersion,
) -> None:
    spec = version.spec_json or {}
    binding_spec = spec.get("bindings") or {}
    bindings_to_create: List[AgentBinding] = [
        AgentBinding(
            agent_id=agent.id,
            agent_version_id=version.id,
            binding_type="model",
            target_key=binding_spec["model_ref"],
            config_json={},
        )
    ]

    binding_groups = [
        ("tool", binding_spec.get("tool_refs") or []),
        ("knowledge", binding_spec.get("knowledge_refs") or []),
        ("workflow", binding_spec.get("workflow_refs") or []),
        ("skill", binding_spec.get("skill_refs") or []),
        ("plugin", binding_spec.get("plugin_refs") or []),
    ]
    for binding_type, values in binding_groups:
        for sort_order, target_key in enumerate(values):
            bindings_to_create.append(
                AgentBinding(
                    agent_id=agent.id,
                    agent_version_id=version.id,
                    binding_type=binding_type,
                    target_key=target_key,
                    config_json={},
                    sort_order=sort_order,
                )
            )

    self.binding_repo.create_many(bindings_to_create)
```

- [ ] **Step 5: Run the integration tests again and verify they pass**

Run: `uv run pytest server/tests/integration/test_agent_publish_and_execute.py -q`
Expected: PASS

- [ ] **Step 6: Stage only the service and integration-test changes**

Run: `git add server/app/modules/agent/application/application_service.py server/tests/integration/test_agent_publish_and_execute.py`
Expected: `git diff --cached --name-only` now includes the files from Tasks 1-2 plus these two paths.

### Task 4: Make projection bindings-only and remove mirrored ref extraction

**Files:**
- Modify: `server/app/kernel/projections/agent_projection.py`
- Test: `server/tests/unit/test_agent_ref_extractor.py`

- [ ] **Step 1: Replace the projection tests with bindings-only coverage**

```python
import pytest

from app.kernel.projections.agent_projection import build_agent_refs


def test_build_agent_refs_extracts_bindings_and_inline_secret_refs():
    spec = {
        "runtime": "agent_runtime_v1",
        "bindings": {
            "model_ref": "model:openai:gpt-4",
            "tool_refs": ["tool:http:demo"],
            "knowledge_refs": ["knowledge:kb_1"],
            "workflow_refs": ["wf:handoff"],
            "skill_refs": ["skill:triage"],
            "plugin_refs": ["plugin:soit:search:1.0.0"],
        },
        "policies": {
            "tool_auth": {"secret_ref": "secret:demo"}
        },
    }

    refs = build_agent_refs(spec)
    types = {(ref.get("ref_type"), ref.get("ref_key"), ref.get("ref_id")) for ref in refs}

    assert ("model", "model:openai:gpt-4", None) in types
    assert ("tool", "tool:http:demo", None) in types
    assert ("knowledge", "knowledge:kb_1", None) in types
    assert ("workflow", "wf:handoff", None) in types
    assert ("skill", "skill:triage", None) in types
    assert ("plugin", "plugin:soit:search:1.0.0", None) in types
    assert ("secret", "secret:demo", None) in types


@pytest.mark.parametrize(
    "legacy_fragment",
    [
        {"model": {"ref_key": "model:openai:gpt-4"}},
        {"tools": {"allowlist": ["tool:http:demo"]}},
        {"rag": {"knowledges": ["knowledge:kb_1"]}},
    ],
)
def test_build_agent_refs_ignores_legacy_binding_mirror_paths(legacy_fragment):
    spec = {
        "runtime": "agent_runtime_v1",
        "bindings": {"model_ref": "model:openai:gpt-4"},
        **legacy_fragment,
    }

    refs = build_agent_refs(spec)
    ref_types = {(ref["ref_type"], ref.get("ref_key") or ref.get("ref_id"), ref["spec_path"]) for ref in refs}

    assert ("model", "model:openai:gpt-4", "$.bindings.model_ref") in ref_types
    assert all(not path.startswith("$.model") for _, _, path in ref_types)
    assert all(not path.startswith("$.tools") for _, _, path in ref_types)
    assert all(not path.startswith("$.rag") for _, _, path in ref_types)
```

- [ ] **Step 2: Run the projection tests and verify they fail before code changes**

Run: `uv run pytest server/tests/unit/test_agent_ref_extractor.py -q`
Expected: FAIL because `build_agent_refs()` still reads legacy `model`, `tools`, and `rag` sections.

- [ ] **Step 3: Simplify `build_agent_refs()` to consume only `bindings` for capability references**

```python
def build_agent_refs(spec_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []

    bindings = spec_json.get("bindings") or {}
    if isinstance(bindings, dict):
        model_ref = bindings.get("model_ref")
        if model_ref:
            entry = _build_ref_entry("model", model_ref, "$.bindings.model_ref")
            if entry:
                refs.append(entry)

        binding_lists = [
            ("knowledge", bindings.get("knowledge_refs") or [], "$.bindings.knowledge_refs"),
            ("tool", bindings.get("tool_refs") or [], "$.bindings.tool_refs"),
            ("workflow", bindings.get("workflow_refs") or [], "$.bindings.workflow_refs"),
            ("skill", bindings.get("skill_refs") or [], "$.bindings.skill_refs"),
            ("plugin", bindings.get("plugin_refs") or [], "$.bindings.plugin_refs"),
        ]
        for ref_type, values, base_path in binding_lists:
            if not isinstance(values, list):
                continue
            for idx, raw_value in enumerate(values):
                entry = _build_ref_entry(ref_type, raw_value, f"{base_path}[{idx}]")
                if entry:
                    refs.append(entry)

    tool_configs = (spec_json.get("tools") or {}).get("configs") or {}
    refs.extend(_extract_inline_refs(tool_configs, "$.tools.configs"))
    planner = spec_json.get("planner") or {}
    refs.extend(_extract_inline_refs(planner, "$.planner"))
    memory = spec_json.get("memory") or {}
    refs.extend(_extract_inline_refs(memory, "$.memory"))
    policies = spec_json.get("policies") or {}
    refs.extend(_extract_inline_refs(policies, "$.policies"))

    deduped: List[Dict[str, Any]] = []
    seen: set[tuple[str, Optional[str], Optional[str]]] = set()
    for item in refs:
        key = (item["ref_type"], item.get("ref_key"), item.get("ref_id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
```

- [ ] **Step 4: Run the projection tests again and verify they pass**

Run: `uv run pytest server/tests/unit/test_agent_ref_extractor.py -q`
Expected: PASS

- [ ] **Step 5: Stage only the projection and projection-test changes**

Run: `git add server/app/kernel/projections/agent_projection.py server/tests/unit/test_agent_ref_extractor.py`
Expected: `git diff --cached --name-only` now includes the files from Tasks 1-3 plus these two paths.

### Task 5: Update API payload tests and add explicit breaking-change coverage

**Files:**
- Modify: `server/tests/entrypoints/test_agent_api.py`

- [ ] **Step 1: Rewrite the API version-create payloads to use nested bindings only**

```python
version_response = client.post(
    f"/api/v1/agents/{agent_id}/versions",
    json={
        "system_prompt": "You are precise.",
        "bindings": {
            "model_ref": "model:test:primary",
            "knowledge_refs": ["knowledge:kb_support"],
            "tool_refs": ["tool:test:echo"],
            "workflow_refs": ["wf:handoff"],
            "skill_refs": ["skill:triage"],
            "plugin_refs": ["plugin:soit:search:1.0.0"],
        },
        "verify": True,
    },
    headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
)

assert version_response.status_code == status.HTTP_201_CREATED
```

- [ ] **Step 2: Add one API-level validation test for a removed top-level binding field**

```python
def test_agent_api_rejects_legacy_top_level_model_ref(client, db, ctx):
    from app.main import app

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort([]),
            tool_port=StubToolPort(),
            memory_service=None,
        )

    app.dependency_overrides[get_agent_application_service] = _override_agent_application_service
    try:
        create_response = client.post(
            "/api/v1/agents",
            json={"name": "api-agent-legacy", "description": "legacy payload", "visibility": "private"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        agent_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "model_ref": "model:test:primary",
                "bindings": {"model_ref": "model:test:primary"},
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )

        assert version_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)
```

- [ ] **Step 3: Run the API test file and verify the new coverage passes**

Run: `uv run pytest server/tests/entrypoints/test_agent_api.py -q`
Expected: PASS

- [ ] **Step 4: Stage only the API test changes**

Run: `git add server/tests/entrypoints/test_agent_api.py`
Expected: `git diff --cached --name-only` now includes the files from Tasks 1-4 plus this path.

### Task 6: Run the focused regression suite and stage the full change set

**Files:**
- Modify: none
- Test: `server/tests/unit/test_agent_schema_naming_cleanup.py`
- Test: `server/tests/test_spec_validation.py`
- Test: `server/tests/unit/test_agent_ref_extractor.py`
- Test: `server/tests/integration/test_agent_publish_and_execute.py`
- Test: `server/tests/entrypoints/test_agent_api.py`

- [ ] **Step 1: Run the full focused suite together**

Run: `uv run pytest server/tests/unit/test_agent_schema_naming_cleanup.py server/tests/test_spec_validation.py server/tests/unit/test_agent_ref_extractor.py server/tests/integration/test_agent_publish_and_execute.py server/tests/entrypoints/test_agent_api.py -q`
Expected: PASS

- [ ] **Step 2: Inspect the staged diff before handoff**

Run: `git diff --cached --stat`
Expected: only the planned agent contract, spec, projection, and test files appear in the staged diff.

- [ ] **Step 3: Stage the complete planned file set**

Run: `git add server/app/modules/agent/application/schemas.py server/app/modules/agent/application/application_service.py server/app/kernel/specs/v1/agent_spec.schema.json server/app/kernel/projections/agent_projection.py server/tests/unit/test_agent_schema_naming_cleanup.py server/tests/test_spec_validation.py server/tests/unit/test_agent_ref_extractor.py server/tests/integration/test_agent_publish_and_execute.py server/tests/entrypoints/test_agent_api.py`
Expected: `git diff --cached --name-only` matches that exact list.

- [ ] **Step 4: Record the final verification output for handoff**

Run: `git diff --cached --name-only`
Expected:

```text
server/app/kernel/projections/agent_projection.py
server/app/kernel/specs/v1/agent_spec.schema.json
server/app/modules/agent/application/application_service.py
server/app/modules/agent/application/schemas.py
server/tests/entrypoints/test_agent_api.py
server/tests/integration/test_agent_publish_and_execute.py
server/tests/test_spec_validation.py
server/tests/unit/test_agent_ref_extractor.py
server/tests/unit/test_agent_schema_naming_cleanup.py
```

## Self-Review Notes

- Spec coverage: the plan covers schema contract, persisted spec shape, preserved `temperature` handling, runtime derivation, binding sync, projection, and API/test fallout from the approved design.
- Placeholder scan: there are no `TODO` or deferred implementation notes in the task steps.
- Type consistency: every task uses `bindings.model_ref`, `bindings.tool_refs`, and `bindings.knowledge_refs` consistently; no task reintroduces top-level binding fields or compatibility fallbacks.
