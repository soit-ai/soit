import pytest
from pydantic import ValidationError

from app.modules.agent.application.schemas import AgentVersionCreate


def test_agent_version_create_rejects_legacy_top_level_plugin_refs():
    with pytest.raises(ValidationError):
        AgentVersionCreate(
            model_ref="model:test:primary",
            plugin_refs=["plugin:legacy"],
        )


def test_agent_version_create_accepts_plugin_refs_in_bindings():
    payload = AgentVersionCreate(
        model_ref="model:test:primary",
        bindings={"plugin_refs": ["plugin:soit:search:1.0.0"]},
    )

    assert payload.bindings is not None
    assert payload.bindings.plugin_refs == ["plugin:soit:search:1.0.0"]
