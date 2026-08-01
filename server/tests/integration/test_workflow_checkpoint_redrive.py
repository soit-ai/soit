"""Crash checkpoints accumulate during execution and drive a manual redrive."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlmodel import Session

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import LLMPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.db.models.runs import Run, RunStep
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


def _plan(workflow_id: str, run_id: str, *, fail_second: bool = False) -> ExecutionPlan:
    second = (
        {"id": "b", "type": "transform", "input": {"mapping": {"boom": "{{ steps.missing.output }}"}}}
        if fail_second
        else {"id": "b", "type": "set_var", "input": {"set": {"y": 2}}}
    )
    return ExecutionPlan(
        mode="workflow",
        subject_kind="workflow",
        subject_id=workflow_id,
        subject_version_id="ver-checkpoint",
        run_id=run_id,
        inputs={"topic": "checkpoint"},
        plan_data={
            "nodes": {
                "a": {"id": "a", "type": "set_var", "input": {"set": {"x": 1}}},
                "b": second,
                "c": {"id": "c", "type": "output", "input": {"value": "{{ steps.a.output.x }}"}},
            },
            "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
            "execution_order": ["a", "b", "c"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )


def _seed_workflow(db: Session, ctx: RequestContext, workflow_id: str) -> None:
    db.add(
        Workflow(
            id=workflow_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            name=workflow_id,
        )
    )
    db.commit()


@pytest.mark.asyncio
@patch("app.wiring.get_container")
async def test_checkpoint_records_progress_and_clears_on_success(
    mock_get_container: MagicMock,
    db: Session,
    ctx: RequestContext,
) -> None:
    mock_get_container.return_value = _patched_container()
    _seed_workflow(db, ctx, "wf-ckpt-ok")

    engine = ExecutionEngine(db, ctx, TraceWriter(db, ctx), response_service=None)
    await engine.execute(_plan("wf-ckpt-ok", "run_ckpt_ok"))

    row = (
        db.execute(select(WorkflowRun).where(WorkflowRun.run_id == "run_ckpt_ok"))
        .scalars()
        .one()
    )
    assert row.status == "succeeded"
    # A finished run keeps no checkpoint: there is nothing left to resume.
    assert row.checkpoint_json is None


@pytest.mark.asyncio
@patch("app.wiring.get_container")
async def test_failed_run_keeps_a_checkpoint_of_completed_nodes(
    mock_get_container: MagicMock,
    db: Session,
    ctx: RequestContext,
) -> None:
    mock_get_container.return_value = _patched_container()
    _seed_workflow(db, ctx, "wf-ckpt-fail")

    engine = ExecutionEngine(db, ctx, TraceWriter(db, ctx), response_service=None)
    with pytest.raises(ValidationError):
        await engine.execute(_plan("wf-ckpt-fail", "run_ckpt_fail", fail_second=True))

    row = (
        db.execute(select(WorkflowRun).where(WorkflowRun.run_id == "run_ckpt_fail"))
        .scalars()
        .one()
    )
    assert row.status == "failed"
    checkpoint = row.checkpoint_json or {}
    # The node that finished before the failure is durable, so a resume can
    # skip it instead of re-running its work.
    assert checkpoint["node_states"].get("a") == "succeeded"
    assert "b" not in checkpoint["node_states"]
    assert checkpoint["node_outputs"].get("a") == {"x": 1}
    assert checkpoint["inputs"] == {"topic": "checkpoint"}


@pytest.mark.asyncio
@patch("app.wiring.get_container")
async def test_redrive_resumes_from_checkpoint_without_rerunning_done_nodes(
    mock_get_container: MagicMock,
    db: Session,
    ctx: RequestContext,
) -> None:
    mock_get_container.return_value = _patched_container()
    _seed_workflow(db, ctx, "wf-redrive")

    engine = ExecutionEngine(db, ctx, TraceWriter(db, ctx), response_service=None)
    with pytest.raises(ValidationError):
        await engine.execute(_plan("wf-redrive", "run_redrive", fail_second=True))

    row = (
        db.execute(select(WorkflowRun).where(WorkflowRun.run_id == "run_redrive"))
        .scalars()
        .one()
    )
    checkpoint = dict(row.checkpoint_json or {})

    # Stage the redrive the way the dead-letter source does.
    row.status = "queued"
    row.lease_owner = "redrive-test"
    db.add(row)
    run = db.get(Run, "run_redrive")
    assert run is not None
    run.status = "retrying"
    db.add(run)
    db.commit()

    # The healthy plan stands in for a fixed workflow version.
    result = await engine.redrive_workflow(
        _plan("wf-redrive", "run_redrive"),
        workflow_run_id=row.id,
        checkpoint=checkpoint,
    )

    assert result.get("value") == 1
    refreshed = db.get(WorkflowRun, row.id)
    assert refreshed is not None
    assert refreshed.status == "succeeded"
    assert refreshed.lease_owner is None
    steps_for_a = (
        db.execute(
            select(RunStep).where(
                RunStep.run_id == "run_redrive",
                RunStep.node_id == "a",
            )
        )
        .scalars()
        .all()
    )
    # The completed node was restored from the checkpoint, not executed again.
    assert len(steps_for_a) == 1
