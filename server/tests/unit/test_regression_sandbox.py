"""test_regression_sandbox

Rehearsing a release must not do the thing it is rehearsing. These cover the
tool boundary and the marking that keeps a rehearsal out of what a workspace
reports it spent.
"""

import pytest

from app.kernel.ports.tools.interface import ToolResponse
from app.kernel.ports.tools.sandbox import DRY_RUN_METADATA_KEY, SandboxToolPort


class _RecordingTools:
    """A tool port that would really do something."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def invoke(self, tool_ref: str, parameters: dict, **kwargs) -> ToolResponse:
        self.calls.append((tool_ref, parameters))
        return ToolResponse(result={"ticket": "OPS-1"}, success=True)


@pytest.mark.asyncio
async def test_a_rehearsed_tool_call_is_answered_but_never_made():
    inner = _RecordingTools()
    sandbox = SandboxToolPort(inner)

    response = await sandbox.invoke("plugin:pagerduty.page", {"service": "checkout"})

    assert inner.calls == []
    assert response.success is True
    assert response.result["sandbox"] is True
    assert response.metadata[DRY_RUN_METADATA_KEY] is True


@pytest.mark.asyncio
async def test_the_evidence_names_the_tool_and_its_parameters_but_not_their_values():
    """A rehearsal must not leak the data it was asked to send outward."""
    sandbox = SandboxToolPort(_RecordingTools())

    response = await sandbox.invoke(
        "plugin:mailer.send",
        {"to": "customer@example.com", "body": "account details"},
    )

    assert response.metadata["tool_ref"] == "plugin:mailer.send"
    assert response.metadata["parameter_names"] == ["body", "to"]
    assert "customer@example.com" not in str(response.metadata)


@pytest.mark.asyncio
async def test_a_read_only_tool_can_be_let_through():
    """A rehearsal still has to be able to fetch what it reasons over."""
    inner = _RecordingTools()
    sandbox = SandboxToolPort(inner, passthrough_tool_refs=frozenset({"plugin:docs.search"}))

    await sandbox.invoke("plugin:docs.search", {"q": "refunds"})
    await sandbox.invoke("plugin:pagerduty.page", {"service": "checkout"})

    assert [ref for ref, _ in inner.calls] == ["plugin:docs.search"]


def test_the_replay_path_asks_for_a_rehearsal():
    """The regression runner is the caller that must set the flag."""
    import inspect

    from app.modules.agent.application.application_service import (
        AgentApplicationService,
    )

    source = inspect.getsource(AgentApplicationService._replay_regression_case)

    assert "_INTERNAL_SANDBOX_KEY: True" in source


def test_execute_agent_marks_a_rehearsal_run_as_one():
    """Cost and dashboards exclude sandbox runs, so the mark has to be set."""
    import inspect

    from app.modules.agent.application.application_service import (
        AgentApplicationService,
    )

    source = inspect.getsource(AgentApplicationService.execute_agent)

    assert "sandbox=sandbox" in source
    assert "_build_runner(sandbox=sandbox)" in source
