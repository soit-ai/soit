"""Workflow ``spec.limits`` are enforced while the DAG executes."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.ports.llm.interface import ChatMessage, ChatResponse, LLMPort
from app.kernel.runtime.db.models.runs import (
    Run,
    RunCostEntry,
    RunStep,
    RunStepToolCall,
)
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.workflow.runtime.engine import ExecutionEngine
from app.modules.workflow.runtime.executor import WorkflowExecutor
from app.modules.workflow.runtime.executors.base import ExecutionContext
from app.modules.workflow.runtime.limits import (
    COST_BUDGET_EXCEEDED,
    MAX_STEPS,
    TIME_BUDGET_EXCEEDED,
    TOOL_BUDGET_EXCEEDED,
    WorkflowLimitExceeded,
    WorkflowRunLimits,
)
from tests.unit.test_workflow_executor import FakeLLMPort, FakeToolPort


class SlowLLMPort(FakeLLMPort):
    """An LLM that takes longer than the workflow's time budget."""

    def __init__(self) -> None:
        self.cancelled = False

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return await super().chat(messages, model, temperature, max_tokens, **kwargs)


def _linear_plan(run_id: str, limits: dict[str, Any], *, llm: bool = False) -> ExecutionPlan:
    middle: dict[str, Any] = (
        {
            "id": "middle",
            "type": "llm",
            "input": {"model": "model:fake:fake", "prompt": "{{ inputs.text }}"},
        }
        if llm
        else {"id": "middle", "type": "transform", "input": {"value": "{{ inputs.text }}"}}
    )
    return ExecutionPlan(
        run_id=run_id,
        mode="workflow",
        inputs={"text": "hello"},
        subject_kind="workflow",
        subject_id="wf_limits",
        subject_version_id="ver_limits",
        plan_data={
            "nodes": {
                "start": {"id": "start", "type": "input", "input": {"text": "{{ inputs.text }}"}},
                "middle": middle,
                "out": {"id": "out", "type": "output", "input": {"value": "done"}},
            },
            "edges": [{"from": "start", "to": "middle"}, {"from": "middle", "to": "out"}],
            "execution_order": ["start", "middle", "out"],
            "semantics": {"concurrency": 1},
            "policy": {},
            "limits": limits,
        },
    )


async def _executor(
    async_db: AsyncSession, ctx: RequestContext, llm_port: LLMPort | None = None
) -> tuple[Run, WorkflowExecutor, ExecutionContext]:
    trace_writer = TraceWriter(async_db, ctx)
    run = await trace_writer.create_run(
        mode="workflow",
        subject_kind="workflow",
        subject_id="wf_limits",
        subject_version_id="ver_limits",
    )
    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        llm_port=llm_port or FakeLLMPort(),
        tool_port=FakeToolPort(),
        vector_port=None,
        plugin_runtime_port=None,
        workflow_policy={},
    )
    return run, WorkflowExecutor(ExecutionEngine(async_db, ctx, trace_writer)), context


async def _executed_nodes(async_db: AsyncSession, run_id: str) -> set[str]:
    rows = (await async_db.exec(select(RunStep).where(RunStep.run_id == run_id))).all()
    steps = [row if isinstance(row, RunStep) else row[0] for row in rows]
    return {str(step.node_id) for step in steps if step.node_id}


def test_limits_normalise_from_plan_data() -> None:
    limits = WorkflowRunLimits.from_plan_data(
        {"limits": {"timeout_ms": 1500, "max_steps": 4, "budget": 0.5, "max_tool_calls": 0}}
    )
    assert limits.timeout_ms == 1500
    assert limits.max_steps == 4
    assert limits.budget == Decimal("0.5")
    assert limits.budget_currency == "USD"
    assert limits.max_tool_calls == 0
    assert limits.any

    empty = WorkflowRunLimits.from_plan_data({"limits": {"budget_currency": "USD"}})
    assert not empty.any
    assert not WorkflowRunLimits.from_plan_data({}).any


@pytest.mark.asyncio
async def test_max_steps_stops_before_the_next_node(async_db, ctx) -> None:
    run, executor, context = await _executor(async_db, ctx)

    with pytest.raises(WorkflowLimitExceeded) as raised:
        await executor.execute(_linear_plan(run.id, {"max_steps": 2}), context)

    assert raised.value.reason == MAX_STEPS
    assert raised.value.details["node_id"] == "out"
    assert "out" not in await _executed_nodes(async_db, run.id)


@pytest.mark.asyncio
async def test_no_limits_leave_execution_unchanged(async_db, ctx) -> None:
    run, executor, context = await _executor(async_db, ctx)

    result = await executor.execute(_linear_plan(run.id, {"budget_currency": "USD"}), context)

    assert result == {"value": "done"}


@pytest.mark.asyncio
async def test_time_budget_cancels_the_node_in_flight(async_db, ctx) -> None:
    slow = SlowLLMPort()
    run, executor, context = await _executor(async_db, ctx, slow)

    with pytest.raises(WorkflowLimitExceeded) as raised:
        await executor.execute(_linear_plan(run.id, {"timeout_ms": 200}, llm=True), context)

    assert raised.value.reason == TIME_BUDGET_EXCEEDED
    assert slow.cancelled is True
    assert "out" not in await _executed_nodes(async_db, run.id)


@pytest.mark.asyncio
async def test_cost_budget_stops_a_run_that_has_spent_it(async_db, ctx) -> None:
    run, executor, context = await _executor(async_db, ctx)
    async_db.add(
        RunCostEntry(
            run_id=run.id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            source_ref=f"cost_{run.id}",
            currency="USD",
            amount=Decimal("0.75"),
            billing_basis="tokens",
        )
    )
    await async_db.flush()

    with pytest.raises(WorkflowLimitExceeded) as raised:
        await executor.execute(_linear_plan(run.id, {"budget": 0.5}), context)

    assert raised.value.reason == COST_BUDGET_EXCEEDED
    assert raised.value.details["spent"] == "0.750000"
    assert await _executed_nodes(async_db, run.id) == set()


@pytest.mark.asyncio
async def test_cost_in_another_currency_does_not_count(async_db, ctx) -> None:
    run, executor, context = await _executor(async_db, ctx)
    async_db.add(
        RunCostEntry(
            run_id=run.id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            source_ref=f"cost_eur_{run.id}",
            currency="EUR",
            amount=Decimal("9"),
            billing_basis="tokens",
        )
    )
    await async_db.flush()

    result = await executor.execute(
        _linear_plan(run.id, {"budget": 0.5, "budget_currency": "USD"}), context
    )

    assert result == {"value": "done"}


@pytest.mark.asyncio
async def test_tool_call_limit_stops_the_run(async_db, ctx) -> None:
    run, executor, context = await _executor(async_db, ctx)
    async_db.add(
        RunStepToolCall(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run.id,
            run_step_id="step_prior",
            tool_call_id="call_prior",
            idempotency_key="idem_prior",
            request_hash="hash_prior",
            tool_ref="tool:test:prior",
        )
    )
    await async_db.flush()

    with pytest.raises(WorkflowLimitExceeded) as raised:
        await executor.execute(_linear_plan(run.id, {"max_tool_calls": 1}), context)

    assert raised.value.reason == TOOL_BUDGET_EXCEEDED


@pytest.mark.asyncio
async def test_engine_records_the_limit_as_the_run_error_code(
    async_db, ctx, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeContainer:
        def get_llm_port(self, **_: Any) -> LLMPort:
            return FakeLLMPort()

        def get_tool_port(self, **_: Any) -> FakeToolPort:
            return FakeToolPort()

        def get_vector_port(self, **_: Any) -> None:
            return None

        def get_plugin_runtime_port(self, **_: Any) -> None:
            return None

    monkeypatch.setattr("app.wiring.get_container", lambda: FakeContainer())
    engine = ExecutionEngine(async_db, ctx, TraceWriter(async_db, ctx))
    plan = _linear_plan("", {"max_steps": 1})

    with pytest.raises(WorkflowLimitExceeded):
        await engine.execute(plan)

    runs = (await async_db.exec(select(Run).where(Run.subject_id == "wf_limits"))).all()
    run = runs[0] if isinstance(runs[0], Run) else runs[0][0]
    assert run.status == "failed"
    assert run.error_code == MAX_STEPS
