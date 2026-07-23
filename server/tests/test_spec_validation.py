"""tests.test_spec_validation

Spec validation tests - verify JSON Schema validation and $ref resolution.
"""

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.runtime.runs.exporter import to_runtrace_spec
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.specs import (
    list_schemas,
    load_schema,
    validate_runtime_spec,
    validate_spec,
    validator,
)
from tests.fixtures.workflow_specs import canonical_workflow_spec


def test_list_and_load_schemas():
    assert "app_spec" not in list_schemas()
    schema = load_schema("workflow_spec")
    assert isinstance(schema, dict)
    assert schema.get("$schema") is not None


def test_app_runtime_schema_is_not_supported():
    with pytest.raises(ValidationError) as exc:
        validate_runtime_spec("app.v1", {})

    assert exc.value.details is not None
    assert exc.value.details["spec_schema"] == "app.v1"


def test_tool_spec_validation_with_refs():
    # endpoint_ref and auth.secret_ids use $ref to refs.schema.json
    tool_doc = {
        "name": "demo_http_tool",
        "adapter": "http",
        "input_schema": {},
        "output_schema": {},
        "policy": {"audit_level": "basic"},
        "endpoint_ref": "endpoint:default",
        "auth": {"type": "api_key", "secret_ids": ["sec_demo_api_key"], "api_key": {"in": "header", "name": "X-Api-Key", "secret_id": "sec_demo_api_key"}},
        "http": {"method": "GET"},
    }
    assert validate_spec(tool_doc, "tool_spec") is True


@pytest.mark.parametrize(
    "auth",
    [
        {
            "type": "api_key",
            "secret_refs": ["secret:demo_api_key"],
            "api_key": {
                "in": "header",
                "name": "X-Api-Key",
                "secret_ref": "secret:demo_api_key",
            },
        },
        {
            "type": "api_key",
            "secret_ids": ["secret:demo_api_key"],
            "api_key": {
                "in": "header",
                "name": "X-Api-Key",
                "secret_id": "secret:demo_api_key",
            },
        },
    ],
)
def test_tool_spec_rejects_legacy_or_raw_secret_references(auth):
    with pytest.raises(ValidationError):
        validate_spec(
            {
                "name": "demo_http_tool",
                "adapter": "http",
                "input_schema": {},
                "output_schema": {},
                "policy": {"audit_level": "basic"},
                "endpoint_ref": "endpoint:default",
                "auth": auth,
                "http": {"method": "GET"},
            },
            "tool_spec",
        )


def test_tool_spec_validation_supports_explicit_approval_policy():
    tool_doc = {
        "name": "governed_ticket_tool",
        "adapter": "function",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "policy": {
            "audit_level": "full",
            "approval": {"mode": "required", "risk_level": "high"},
        },
        "function": {"entrypoint": "app.utils.demo_ticket_tools:create_review_ticket"},
    }

    assert validate_spec(tool_doc, "tool_spec") is True
    with pytest.raises(ValidationError):
        validate_spec(
            {
                **tool_doc,
                "policy": {
                    "audit_level": "full",
                    "approval": {"mode": "sometimes", "risk_level": "high"},
                },
            },
            "tool_spec",
        )


def test_run_step_tool_call_spec_exposes_safe_execution_control_fields_only():
    document = {
        "id": "rstc_01JEXAMPLE",
        "tenant_id": "tenant_01JEXAMPLE",
        "workspace_id": "workspace_01JEXAMPLE",
        "run_id": "run_01JEXAMPLE",
        "run_step_id": "step_01JEXAMPLE",
        "tool_call_id": "call_weather",
        "idempotency_key": "tool:run_01JEXAMPLE:call_weather",
        "request_hash": "a" * 64,
        "tool_ref": "tool:function:get_weather",
        "status": "succeeded",
        "attempt_count": 1,
        "parameters_summary": {"city": "Beijing"},
        "result": {"temperature": 28},
        "created_at": "2026-07-17T10:00:00Z",
        "updated_at": "2026-07-17T10:00:01Z",
        "completed_at": "2026-07-17T10:00:01Z",
    }

    assert validate_spec(document, "run_step_tool_call_spec") is True
    with pytest.raises(ValidationError):
        validate_spec(
            {**document, "parameters_json": {"api_key": "must-not-be-exposed"}},
            "run_step_tool_call_spec",
        )


def test_plugin_spec_validation_with_refs():
    plugin_doc = {
        "name": "demo_plugin",
        "publisher": "soit",
        "version": "0.1.0",
        "runtime_level": "L0",
        "capabilities": ["tools"],
        "exports": {"tools": ["tool:http:demo_http_tool"]},
        "permissions": {"network": ["api.example.com"]},
        "integrity": {"digest": "sha256:deadbeef"},
    }
    assert validate_spec(plugin_doc, "plugin_spec") is True


def test_workflow_spec_validation_minimal():
    wf_doc = {
        "name": "demo_workflow",
        "inputs_schema": {},
        "outputs_schema": {},
        "graph": {
            "nodes": [{"id": "n1", "type": "output", "params": {"value": "ok"}}],
            "edges": [],
        },
    }
    assert validate_spec(wf_doc, "workflow_spec") is True


@pytest.mark.parametrize(
    ("node_type", "params"),
    [
        ("input", {}),
        ("transform", {"mapping": {"value": "{{ inputs.value }}"}}),
        ("set_var", {"key": "ticket_id", "value": "{{ inputs.ticket_id }}"}),
        ("llm", {"model": "model:test:chat", "prompt": "hello"}),
        (
            "retrieve",
            {
                "knowledge_ref": "knowledge:kb-1",
                "query": "hello",
                "top_k": 3,
            },
        ),
        (
            "tool",
            {
                "tool_ref": "tool:test:echo",
                "arguments": {"value": "hello"},
            },
        ),
        ("condition", {"condition": "{{ inputs.accepted }}"}),
        ("output", {"value": "{{ inputs.value }}"}),
        (
            "http",
            {
                "url": "https://example.test/items",
                "method": "POST",
                "headers": {"X-Request-ID": "request-1"},
                "query": {"page": 1},
                "body": {"value": True},
            },
        ),
        (
            "node",
            {
                "node_ref": "node:test:echo",
                "parameters": {"value": "hello"},
            },
        ),
    ],
)
def test_workflow_schema_accepts_canonical_and_compatibility_node_contracts(
    node_type: str,
    params: dict,
) -> None:
    spec = canonical_workflow_spec(node_type=node_type, params=params)

    validate_runtime_spec("workflow.v1", spec, raise_on_error=True)


@pytest.mark.parametrize("node_type", ["loop", "code", "agent", "parallel", "join"])
def test_workflow_schema_rejects_new_unsupported_node_types(node_type: str) -> None:
    spec = canonical_workflow_spec(node_type=node_type, params={})

    with pytest.raises(ValidationError):
        validate_runtime_spec("workflow.v1", spec, raise_on_error=True)


@pytest.mark.parametrize(
    ("node_type", "params"),
    [
        ("input", {"unknown": True}),
        ("transform", {}),
        ("set_var", {"key": "", "value": None}),
        ("llm", {"model": "", "prompt": "hello"}),
        ("llm", {"model": "model:test:chat", "prompt": ""}),
        ("llm", {"model": "model:test:chat", "prompt": "hello", "temperature": 2.1}),
        ("llm", {"model": "model:test:chat", "prompt": "hello", "max_tokens": 0}),
        ("retrieve", {"knowledge_ref": "", "query": "hello"}),
        ("retrieve", {"knowledge_ref": "knowledge:kb-1", "query": ""}),
        ("retrieve", {"knowledge_ref": "knowledge:kb-1", "query": "hello", "top_k": 0}),
        ("tool", {"tool_ref": ""}),
        ("condition", {"condition": ""}),
        ("output", {}),
        ("http", {"url": "", "method": "GET"}),
        ("http", {"url": "https://example.test", "method": "TRACE"}),
        ("node", {"node_ref": ""}),
    ],
)
def test_workflow_schema_rejects_invalid_node_parameters(
    node_type: str,
    params: dict,
) -> None:
    spec = canonical_workflow_spec(node_type=node_type, params=params)

    with pytest.raises(ValidationError):
        validate_runtime_spec("workflow.v1", spec, raise_on_error=True)


@pytest.mark.parametrize(
    "limits",
    [
        {"timeout_ms": 0},
        {"max_steps": 0},
        {"budget": -0.01},
        {"max_tool_calls": -1},
        {"budget_currency": "usd"},
        {"budget_currency": "US"},
        {"budget_currency": "USDT"},
    ],
)
def test_workflow_schema_rejects_invalid_execution_limits(limits: dict) -> None:
    spec = canonical_workflow_spec()
    spec["limits"] = limits

    with pytest.raises(ValidationError):
        validate_runtime_spec("workflow.v1", spec, raise_on_error=True)


def test_workflow_schema_accepts_historical_budget_without_currency() -> None:
    spec = canonical_workflow_spec()
    spec["limits"] = {"budget": 3.5}

    validate_runtime_spec("workflow.v1", spec, raise_on_error=True)
    budget_currency = load_schema("workflow_spec")["properties"]["limits"]["properties"][
        "budget_currency"
    ]
    assert budget_currency["default"] == "USD"


def test_workflow_schema_rejects_non_positive_concurrency() -> None:
    spec = canonical_workflow_spec()
    spec["semantics"] = {"concurrency": 0}

    with pytest.raises(ValidationError):
        validate_runtime_spec("workflow.v1", spec, raise_on_error=True)


def test_workflow_schema_rejects_negative_default_retry_count() -> None:
    spec = canonical_workflow_spec()
    spec["policy"] = {"default_retry_policy": {"max_retries": -1}}

    with pytest.raises(ValidationError):
        validate_runtime_spec("workflow.v1", spec, raise_on_error=True)


def test_workflow_schema_accepts_equal_condition_and_when_during_migration() -> None:
    spec = canonical_workflow_spec()
    spec["graph"]["edges"][0].update(
        condition="{{ inputs.enabled }}",
        when="{{ inputs.enabled }}",
    )

    validate_runtime_spec("workflow.v1", spec, raise_on_error=True)


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
        },
        "policies": {"verify": True},
    }

    assert validate_spec(agent_doc, "agent_spec") is True


@pytest.mark.parametrize(
    "binding_name",
    ["knowledge_refs", "tool_refs", "workflow_refs", "skill_refs"],
)
def test_agent_spec_rejects_null_capability_bindings(binding_name: str) -> None:
    bindings = {
        "model_ref": "model:openai:gpt-4",
        "knowledge_refs": [],
        "tool_refs": [],
        "workflow_refs": [],
        "skill_refs": [],
    }
    bindings[binding_name] = None

    with pytest.raises(ValidationError):
        validate_spec(
            {
                "runtime": "agent_runtime_v1",
                "bindings": bindings,
            },
            "agent_spec",
        )


def test_agent_spec_validation_rejects_plugin_refs_binding():
    with pytest.raises(ValidationError):
        validate_spec(
            {
                "runtime": "agent_runtime_v1",
                "bindings": {
                    "model_ref": "model:openai:gpt-4",
                    "plugin_refs": ["plugin:soit:search:1.0.0"],
                },
            },
            "agent_spec",
        )


@pytest.mark.parametrize(
    "legacy_fragment",
    [
        {"model": {"ref_key": "model:openai:gpt-4"}},
        {"model_ref": "model:openai:gpt-4"},
        {"rag": {"knowledges": ["knowledge:kb_support"]}},
    ],
)
def test_agent_spec_validation_rejects_legacy_binding_fragments(legacy_fragment):
    with pytest.raises(ValidationError):
        validate_spec(
            {
                "runtime": "agent_runtime_v1",
                "bindings": {"model_ref": "model:openai:gpt-4"},
                **legacy_fragment,
            },
            "agent_spec",
        )


def test_chat_spec_validation_accepts_current_binding_shape():
    chat_doc = {
        "runtime": "chat_runtime_v1",
        "model_ref": "model:openai:gpt-4",
        "tool_refs": ["tool:test:echo"],
        "rag": {"knowledge_refs": ["knowledge:kb_support"]},
    }

    assert validate_spec(chat_doc, "chat_spec") is True


@pytest.mark.parametrize(
    "legacy_fragment",
    [
        {"model": {"ref_key": "model:openai:gpt-4"}},
        {"tools": {"allowlist": ["tool:test:echo"]}},
        {"rag": {"knowledge_ids": ["kb_support"]}},
        {"rag": {"knowledges": ["knowledge:kb_support"]}},
    ],
)
def test_chat_spec_validation_rejects_legacy_binding_fragments(legacy_fragment):
    with pytest.raises(ValidationError):
        validate_spec(
            {
                "runtime": "chat_runtime_v1",
                "model_ref": "model:openai:gpt-4",
                **legacy_fragment,
            },
            "chat_spec",
        )


def test_invalid_tool_spec_returns_rich_errors():
    # missing required: input_schema/output_schema/policy
    bad_doc = {"name": "bad", "adapter": "http"}

    with pytest.raises(ValidationError) as ei:
        validator.validate("tool_spec", bad_doc, raise_on_error=True)

    err = ei.value
    assert err.details is not None
    assert err.details.get("spec") == "tool_spec"
    assert err.details.get("error_count", 0) >= 1
    # ensure paths are present
    first = err.details["errors"][0]
    assert "instance_path" in first
    assert "schema_path" in first


def test_node_spec_validation_with_refs():
    node_doc = {
        "name": "llm_chat",
        "id": "node:builtin:llm_chat",
        "adapter": "builtin",
        "node_type": "llm",
        "input_schema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]},
        "output_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    }
    assert validate_spec(node_doc, "node_spec") is True


def test_actual_runtrace_export_matches_runtime_contract(db, ctx):
    writer = TraceWriter(db, ctx)
    run = writer.create_run(
        "response",
        kind="response",
        request_id="request-trace",
        source_run_id="run_previous",
        attempt_no=2,
    )
    step = writer.create_step(run.id, "llm")
    writer.update_step_status(step.id, "running")
    writer.update_step_status(step.id, "succeeded")
    usage = writer.record_cost(
        run_id=run.id,
        step_id=step.id,
        unit="tokens",
        quantity=5,
        provider_id="provider_1",
        provider_slug="openai-primary",
        provider_kind="openai",
        model_ref="model:openai-primary:gpt-5.1",
        upstream_model="gpt-5.1",
        prompt_tokens=3,
        completion_tokens=2,
        total_tokens=5,
    )
    charge = writer.record_cost(
        run_id=run.id,
        step_id=step.id,
        entry_type="charge",
        unit="tokens",
        quantity=5,
        currency="USD",
        amount="0.001",
        provider_id="provider_1",
        provider_slug="openai-primary",
        provider_kind="openai",
        model_ref="model:openai-primary:gpt-5.1",
        upstream_model="gpt-5.1",
    )

    document = to_runtrace_spec(run, [step], cost_entries=[usage, charge])

    assert document["run"]["request_id"] == "request-trace"
    assert document["usage_summary"]["tokens_prompt"] == 3
    assert document["charge_summary"]["amounts"] == {"USD": 0.001}
    assert {entry["entry_type"] for entry in document["entries"]} == {"usage", "charge"}
    assert validate_spec(document, "runtrace_spec") is True
