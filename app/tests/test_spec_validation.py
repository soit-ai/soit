"""tests.test_spec_validation

Spec validation tests - verify JSON Schema validation and $ref resolution.
"""

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.specs import load_schema, validate_spec, validator


def test_list_and_load_schemas():
    schema = load_schema("workflow_spec")
    assert isinstance(schema, dict)
    assert schema.get("$schema") is not None


def test_tool_spec_validation_with_refs():
    # endpoint_ref and auth.secret_refs use $ref to refs.schema.json
    tool_doc = {
        "name": "demo_http_tool",
        "adapter": "http",
        "input_schema": {},
        "output_schema": {},
        "policy": {"audit_level": "basic"},
        "endpoint_ref": "endpoint:default",
        "auth": {"secret_refs": ["secret:demo_api_key"]},
    }
    assert validate_spec(tool_doc, "tool_spec") is True


def test_plugin_spec_validation_with_refs():
    plugin_doc = {
        "name": "demo_plugin",
        "publisher": "soit",
        "version": "0.1.0",
        "runtime_level": "standard",
        "capabilities": {"tools": True},
        "exports": {"tools": ["tool:http:demo_http_tool"]},
        "permissions": {"egress": {"allow": ["https://api.example.com"]}},
        "integrity": {"digest": "sha256:deadbeef"},
    }
    assert validate_spec(plugin_doc, "plugin_spec") is True


def test_workflow_spec_validation_minimal():
    wf_doc = {
        "name": "demo_workflow",
        "inputs_schema": {},
        "nodes": [{"id": "n1", "type": "output", "input": {}}],
        "edges": [],
        "outputs": {},
    }
    assert validate_spec(wf_doc, "workflow_spec") is True


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
