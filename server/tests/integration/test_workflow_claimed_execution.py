"""The engine adopts a pre-claimed WorkflowRun and settles its lease."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlmodel import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.workflow.domain.models import Workflow, WorkflowRun
from app.modules.workflow.runtime.engine import ExecutionEngine, ExecutionPlan


class _FakeLLMPort(LLMPort):
    async def chat(self, *args: Any, **kwargs: Any):
        raise NotImplementedError

    async def embed(self, *args: Any, **kwargs: Any):
        raise NotImplementedError

    async def rerank(self, *args: Any, **kwargs: Any):
        raise NotImplementedError


class _FakeToolPort(ToolPort):
    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        return ToolResponse(result={}, success=True, metadata={})


def _patched_container() -> MagicMock:
    c = MagicMock()
    c.get_llm_port = lambda ctx, trace_writer: _FakeLLMPort()
    c.get_tool_port = lambda ctx, trace_writer: _FakeToolPort()
    c.get_vector_port = lambda ctx, trace_writer: None
    c.get_plugin_runtime_port = lambda ctx, trace_writer: None
    return c


def _plan(workflow_id: str, run_id: str) -> ExecutionPlan:
    return ExecutionPlan(
        mode="workflow",
        subject_kind="workflow",
        subject_id=workflow_id,
        subject_version_id="ver-claimed",
        run_id=run_id,
        inputs={},
        plan_data={
            "nodes": {
                "a": {"id": "a", "type": "set_var", "input": {"set": {"x": 1}}},
                "b": {"id": "b", "type": "output", "input": {"value": "{{ steps.a.output.x }}"}},
            },
            "edges": [{"from": "a", "to": "b"}],
            "execution_order": ["a", "b"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )


@pytest.mark.asyncio
@patch("app.wiring.get_container")
async def test_engine_adopts_the_claimed_row_and_releases_its_lease(
    mock_get_container: MagicMock,
    db: Session,
    ctx: RequestContext,
) -> None:
    mock_get_container.return_value = _patched_container()

    workflow = Workflow(
        id="wf-claimed",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="workflow-claimed",
    )
    claim = WorkflowRun(
        id="wfr_claimed",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id="run_claimed_exec",
        workflow_id=workflow.id,
        status="running",
        inputs_json={"topic": "claimed"},
        request_context_json={"tenant_id": ctx.tenant_id},
        lease_owner="workflow-api-claimer",
        lease_expires_at=utc_now() + timedelta(minutes=5),
        attempt_count=1,
    )
    db.add(workflow)
    db.add(claim)
    db.commit()

    engine = ExecutionEngine(db, ctx, TraceWriter(db, ctx), response_service=None)
    result = await engine.execute(_plan(workflow.id, "run_claimed_exec"))

    rows = (
        db.execute(
            select(WorkflowRun).where(WorkflowRun.run_id == "run_claimed_exec")
        )
        .scalars()
        .all()
    )
    assert result.get("value") == 1
    # Exactly one aggregate: the engine adopted the claim instead of creating
    # a parallel row for the same run.
    assert len(rows) == 1
    adopted = rows[0]
    assert adopted.id == "wfr_claimed"
    assert adopted.status == "succeeded"
    assert adopted.total_nodes == 2
    # Terminal work must not keep a lease, or the reaper could never tell
    # finished runs from orphans.
    assert adopted.lease_owner is None
    assert adopted.lease_expires_at is None
    # The claim's snapshot survives adoption.
    assert adopted.inputs_json == {"topic": "claimed"}


@pytest.mark.asyncio
@patch("app.wiring.get_container")
async def test_engine_without_a_claim_still_creates_its_own_row(
    mock_get_container: MagicMock,
    db: Session,
    ctx: RequestContext,
) -> None:
    mock_get_container.return_value = _patched_container()

    workflow = Workflow(
        id="wf-unclaimed",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="workflow-unclaimed",
    )
    db.add(workflow)
    db.commit()

    engine = ExecutionEngine(db, ctx, TraceWriter(db, ctx), response_service=None)
    await engine.execute(_plan(workflow.id, "run_unclaimed_exec"))

    rows = (
        db.execute(
            select(WorkflowRun).where(WorkflowRun.run_id == "run_unclaimed_exec")
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].status == "succeeded"
    assert rows[0].lease_owner is None
