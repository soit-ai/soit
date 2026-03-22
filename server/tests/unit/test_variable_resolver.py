"""test_variable_resolver

Unit tests for workflow variable resolution.
"""

from __future__ import annotations

import pytest

from app.kernel.commons.errors import ValidationError
from app.modules.workflow.application.variable_resolver import VariableResolver


def test_resolve_inputs_field_and_root() -> None:
    resolver = VariableResolver(inputs={"query": "hello", "nested": {"value": 42}})
    assert resolver.resolve("{{ inputs.query }}") == "hello"
    assert resolver.resolve("{{ inputs.nested.value }}") == 42
    assert resolver.resolve("{{ inputs }}") == {"query": "hello", "nested": {"value": 42}}


def test_resolve_context_field_and_root() -> None:
    resolver = VariableResolver(inputs={}, context={"tenant_id": "t1", "workspace": {"id": "w1"}})
    assert resolver.resolve("{{ context.tenant_id }}") == "t1"
    assert resolver.resolve("{{ context.workspace.id }}") == "w1"
    assert resolver.resolve("{{ context }}") == {"tenant_id": "t1", "workspace": {"id": "w1"}}


def test_resolve_steps_output_field_and_root() -> None:
    steps_outputs = {"s1": {"text": "ok", "meta": {"score": 0.9}}}
    resolver = VariableResolver(inputs={}, steps_outputs=steps_outputs)
    assert resolver.resolve("{{ steps.s1.output.text }}") == "ok"
    assert resolver.resolve("{{ steps.s1.output.meta.score }}") == 0.9
    assert resolver.resolve("{{ steps.s1.output }}") == steps_outputs["s1"]


def test_resolve_embedded_string_and_collections() -> None:
    resolver = VariableResolver(
        inputs={"query": "hi"},
        context={"tenant_id": "t1"},
        steps_outputs={"s1": {"text": "ok"}},
    )
    assert resolver.resolve("Query={{ inputs.query }}, Tenant={{ context.tenant_id }}") == "Query=hi, Tenant=t1"
    payload = resolver.resolve(
        {
            "message": "Answer: {{ steps.s1.output.text }}",
            "items": ["{{ inputs.query }}", "{{ context.tenant_id }}"],
        }
    )
    assert payload["message"] == "Answer: ok"
    assert payload["items"] == ["hi", "t1"]


def test_missing_variable_raises_clear_error() -> None:
    resolver = VariableResolver(inputs={"query": "hi"})
    with pytest.raises(ValidationError) as exc:
        resolver.resolve("{{ inputs.missing }}")
    assert "inputs.missing" in str(exc.value)


def test_invalid_steps_expression_raises() -> None:
    resolver = VariableResolver(inputs={}, steps_outputs={"s1": {"text": "ok"}})
    with pytest.raises(ValidationError) as exc:
        resolver.resolve("{{ steps.s1.text }}")
    assert "Invalid steps variable" in str(exc.value)


def test_skipped_step_resolves_to_none_or_empty_string() -> None:
    resolver = VariableResolver(inputs={}, steps_outputs={}, skipped_steps={"s2"})
    assert resolver.resolve("{{ steps.s2.output }}") is None
    assert resolver.resolve("value={{ steps.s2.output }}") == "value="
