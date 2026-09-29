"""An agent file carries a version's specification losslessly."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.portable import AgentFile, version_create_from_spec
from app.modules.agent.application.schemas import (
    AgentCapabilityBindings,
    AgentVersionCreate,
)


def _build_spec(data: AgentVersionCreate) -> dict:
    # The builder reads nothing from the service but its ref normaliser.
    service = AgentApplicationService.__new__(AgentApplicationService)
    return service._build_spec(data)


FULL = AgentVersionCreate(
    system_prompt="Answer briefly.",
    temperature=0.3,
    max_iterations=4,
    max_tool_calls=6,
    max_llm_calls=8,
    max_failures=1,
    max_runtime_seconds=90,
    max_tokens_total=4000,
    max_cost=1.5,
    cost_currency="USD",
    rag_top_k=5,
    rag_strategy="planner_context",
    context_window_messages=20,
    context_window_chars=8000,
    bindings=AgentCapabilityBindings(
        model_ref="model:openai:gpt-6",
        knowledge_refs=["knowledge:kb_1"],
        tool_refs=["tool:web.search", "tool:web.search"],
        workflow_refs=[],
        skill_refs=["skill:summarise"],
    ),
    memory_strategy="system_message",
    memory_top_k=3,
    verify=True,
    failure_strategy="abort",
)


@pytest.mark.parametrize(
    "create",
    [FULL, AgentVersionCreate(bindings=AgentCapabilityBindings(model_ref="model:test:chat"))],
    ids=["every field", "bindings only"],
)
def test_a_spec_read_back_builds_the_same_spec(create: AgentVersionCreate) -> None:
    spec = _build_spec(create)

    again = version_create_from_spec(spec)

    assert _build_spec(again) == spec


def test_reading_back_drops_the_duplicate_ref_the_builder_dropped() -> None:
    again = version_create_from_spec(_build_spec(FULL))

    assert again.bindings.tool_refs == ["tool:web.search"]


def test_a_file_takes_no_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        AgentFile.model_validate({"soit": "agent/v1", "agent": {"name": "a", "id": "agt_1"}})
    with pytest.raises(ValidationError):
        AgentFile.model_validate({"soit": "agent/v2", "agent": {"name": "a"}})


def test_a_file_without_a_version_is_an_agent_alone() -> None:
    document = AgentFile.model_validate({"soit": "agent/v1", "agent": {"name": "bare"}})

    assert document.version is None
    assert document.agent.as_create().visibility == "private"
