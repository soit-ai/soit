"""Public contract tests for governed stateful Agent execution."""

import pytest
from pydantic import ValidationError

from app.modules.agent.application.schemas import AgentRunRequest


def test_agent_public_request_accepts_only_current_input_and_correlation() -> None:
    request = AgentRunRequest.model_validate(
        {
            "input": "Continue the investigation",
            "thread_id": "thr_existing",
            "request_id": "req_agent_1",
        }
    )

    assert request.input == "Continue the investigation"
    assert request.thread_id == "thr_existing"
    assert request.request_id == "req_agent_1"


@pytest.mark.parametrize(
    "forbidden",
    [
        {"messages": [{"role": "user", "content": "client history"}]},
        {"model_ref": "model:other:model"},
        {"max_iterations": 50},
        {"verify": False},
        {"system_prompt": "override"},
    ],
)
def test_agent_public_request_rejects_runtime_overrides(forbidden) -> None:
    with pytest.raises(ValidationError):
        AgentRunRequest.model_validate({"input": "hello", **forbidden})
