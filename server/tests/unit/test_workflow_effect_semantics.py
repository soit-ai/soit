"""Node effect classification and resume-policy spec contracts."""

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.specs.validator import validator
from app.modules.workflow.application.capabilities import (
    COMPATIBILITY_NODE_TYPES,
    get_workflow_node_capabilities,
)
from app.modules.workflow.domain.effects import (
    DEFAULT_NODE_EFFECT_CLASS,
    DEFAULT_RESUME_POLICY,
    EFFECT_CLASSES,
    EFFECT_EFFECTFUL,
    EFFECT_PURE,
    EFFECT_READ,
    ON_RESUME_FAIL,
    ON_RESUME_REQUIRE_APPROVAL,
    RESUME_POLICY_MANUAL,
    resolve_node_effect_class,
    resolve_node_on_resume,
    resolve_resume_policy,
)
from tests.fixtures.workflow_specs import canonical_workflow_spec


def _tool_workflow_spec(**node_extra: object) -> dict:
    spec = canonical_workflow_spec(node_type="tool", params={"tool_ref": "tool:function:time_now"})
    spec["graph"]["nodes"][0].update(node_extra)
    return spec


def test_every_node_type_has_a_default_effect_class() -> None:
    capability_types = {c.type for c in get_workflow_node_capabilities()}
    declared = set(DEFAULT_NODE_EFFECT_CLASS)
    assert capability_types <= declared
    assert set(COMPATIBILITY_NODE_TYPES) <= declared
    assert set(DEFAULT_NODE_EFFECT_CLASS.values()) <= set(EFFECT_CLASSES)


def test_capabilities_expose_effect_class() -> None:
    by_type = {c.type: c.effect_class for c in get_workflow_node_capabilities()}
    assert by_type["transform"] == EFFECT_PURE
    assert by_type["llm"] == EFFECT_READ
    assert by_type["tool"] == EFFECT_EFFECTFUL


def test_schema_accepts_effect_fields_on_externally_reaching_nodes() -> None:
    spec = _tool_workflow_spec(effect_class="read", on_resume="require_approval")
    spec["semantics"] = {"resume_policy": "manual"}
    assert validator.validate_workflow_spec(spec) == []


def test_schema_rejects_pure_claim_and_unknown_resume_policy() -> None:
    with pytest.raises(ValidationError):
        validator.validate_workflow_spec(_tool_workflow_spec(effect_class="pure"))
    spec = canonical_workflow_spec()
    spec["semantics"] = {"resume_policy": "sometimes"}
    with pytest.raises(ValidationError):
        validator.validate_workflow_spec(spec)


def test_schema_rejects_effect_fields_on_pure_nodes() -> None:
    spec = canonical_workflow_spec()
    spec["graph"]["nodes"][0]["effect_class"] = "read"
    with pytest.raises(ValidationError):
        validator.validate_workflow_spec(spec)


def test_effect_class_resolution_honors_narrowing_override_only() -> None:
    assert resolve_node_effect_class({"type": "tool"}) == EFFECT_EFFECTFUL
    assert resolve_node_effect_class({"type": "http", "effect_class": "read"}) == EFFECT_READ
    # A pure claim on an externally reaching node is ignored, never honored.
    assert resolve_node_effect_class({"type": "tool", "effect_class": "pure"}) == EFFECT_EFFECTFUL
    # Pure node types cannot be widened from the node instance.
    assert resolve_node_effect_class({"type": "transform", "effect_class": "effectful"}) == EFFECT_PURE
    # Unknown node types are treated as effectful, never silently safe.
    assert resolve_node_effect_class({"type": "mystery"}) == EFFECT_EFFECTFUL


def test_on_resume_defaults_to_fail() -> None:
    assert resolve_node_on_resume({"type": "tool"}) == ON_RESUME_FAIL
    assert (
        resolve_node_on_resume({"type": "tool", "on_resume": "require_approval"})
        == ON_RESUME_REQUIRE_APPROVAL
    )
    assert resolve_node_on_resume({"type": "tool", "on_resume": "bogus"}) == ON_RESUME_FAIL


def test_resume_policy_defaults_to_manual() -> None:
    assert DEFAULT_RESUME_POLICY == RESUME_POLICY_MANUAL
    assert resolve_resume_policy(None) == RESUME_POLICY_MANUAL
    assert resolve_resume_policy({}) == RESUME_POLICY_MANUAL
    assert resolve_resume_policy({"resume_policy": "auto"}) == "auto"
    assert resolve_resume_policy({"resume_policy": "bogus"}) == RESUME_POLICY_MANUAL
