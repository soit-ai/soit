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


def test_agent_version_create_rejects_plugin_refs_binding():
    with pytest.raises(ValidationError):
        AgentVersionCreate(
            bindings={
                "model_ref": "model:test:primary",
                "plugin_refs": ["plugin:legacy"],
            },
            verify=True,
        )
