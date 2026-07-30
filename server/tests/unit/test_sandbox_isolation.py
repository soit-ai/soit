"""Rehearsal runs are marked, isolated from side effects, and costed apart."""

from decimal import Decimal
from typing import Any

import pytest

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.ports.tools.sandbox import DRY_RUN_METADATA_KEY, SandboxToolPort
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.kernel.runtime.runs.service import RunService
from app.kernel.runtime.runs.writer import TraceWriter


class _RecordingToolPort(ToolPort):
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def invoke(
        self,
        tool_ref: str,
        parameters: dict[str, Any],
        **kwargs: Any,
    ) -> ToolResponse:
        self.calls.append(tool_ref)
        return ToolResponse(result={"executed": True}, success=True)


@pytest.mark.asyncio
async def test_sandbox_does_not_execute_a_side_effectful_tool():
    inner = _RecordingToolPort()
    port = SandboxToolPort(inner)

    response = await port.invoke("tool:http:create_ticket", {"subject": "hi"})

    # Rehearsing a release must not file real tickets.
    assert inner.calls == []
    assert response.success
    assert response.metadata[DRY_RUN_METADATA_KEY] is True
    assert response.result["sandbox"] is True


@pytest.mark.asyncio
async def test_sandbox_records_parameter_names_but_not_their_values():
    port = SandboxToolPort(_RecordingToolPort())

    response = await port.invoke(
        "tool:http:create_ticket",
        {"subject": "customer ssn 123-45-6789", "priority": "high"},
    )

    assert response.metadata["parameter_names"] == ["priority", "subject"]
    assert "123-45-6789" not in str(response.metadata)


@pytest.mark.asyncio
async def test_explicitly_listed_tools_still_run():
    inner = _RecordingToolPort()
    port = SandboxToolPort(
        inner,
        passthrough_tool_refs=frozenset({"tool:local:search"}),
    )

    await port.invoke("tool:local:search", {"q": "refund"})

    # A read-only tool can be allowed so the rehearsal still has data to reason
    # over.
    assert inner.calls == ["tool:local:search"]


def test_runs_are_real_unless_the_writer_says_otherwise(db, ctx: RequestContext):
    run = TraceWriter(db, ctx).create_run(mode="agent", subject_id="a", subject_kind="agent")

    assert run.sandbox is False


def test_a_sandbox_writer_marks_every_run_it_creates(db, ctx: RequestContext):
    run = TraceWriter(db, ctx, sandbox=True).create_run(
        mode="agent",
        subject_id="a",
        subject_kind="agent",
    )

    assert run.sandbox is True


def _cost(db, ctx: RequestContext, *, run_id: str, sandbox: bool, tokens: int) -> None:
    db.add(
        Run(
            id=run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            trace_id=f"tr_{run_id}",
            mode="agent",
            kind="agent",
            status="succeeded",
            sandbox=sandbox,
        )
    )
    db.add(
        RunCostEntry(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run_id,
            currency="USD",
            amount=Decimal("0"),
            billing_basis="tokens",
            billed_quantity=Decimal(tokens),
            prompt_tokens=tokens,
        )
    )
    db.commit()


def test_sandbox_spend_is_excluded_from_workspace_cost(db, ctx: RequestContext):
    _cost(db, ctx, run_id="run_real", sandbox=False, tokens=10)
    _cost(db, ctx, run_id="run_rehearsal", sandbox=True, tokens=90)
    service = RunService(db=db, ctx=ctx)

    default_summary = service.summarize_costs()
    with_sandbox = service.summarize_costs(include_sandbox=True)

    # Counting rehearsal spend as production would misstate what the workspace
    # actually cost.
    assert default_summary.tokens_prompt == 10
    assert with_sandbox.tokens_prompt == 100
