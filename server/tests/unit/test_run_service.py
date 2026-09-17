"""test_run_service

Unit tests for RunService cost summaries and filtering.
"""

from datetime import UTC, datetime

import pytest

from app.kernel.commons.ids import (
    generate_artifact_id,
    generate_run_id,
    generate_step_id,
)
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep
from app.kernel.runtime.runs.service import RunService


@pytest.mark.asyncio
async def test_run_cost_summary_filters(async_db):
    """Cost summary aggregates only matching runs."""

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )

    run_id_chat = generate_run_id()
    run_id_agent = generate_run_id()

    run_chat = Run(
        id=run_id_chat,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="chat",
        subject_kind="thread",
        subject_id="thr-chat",
        subject_version_id="conv-1",
        status="succeeded",
    )
    run_agent = Run(
        id=run_id_agent,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="agent",
        subject_kind="agent",
        subject_id="agt-runtime",
        subject_version_id="agtv-1",
        status="succeeded",
    )
    async_db.add(run_chat)
    async_db.add(run_agent)

    cost_chat = RunCostEntry(
        run_id=run_id_chat,
        step_id=None,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        currency="USD",
        amount=0,
        billing_basis="tokens",
        billed_quantity=19,
        provider="openai",
        model_ref="model:openai:gpt-4",
        prompt_tokens=12,
        completion_tokens=7,
        total_tokens=19,
    )
    cost_agent = RunCostEntry(
        run_id=run_id_agent,
        step_id=None,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        currency="USD",
        amount=0,
        billing_basis="tokens",
        billed_quantity=6,
        provider="openai",
        model_ref="model:openai:gpt-5.1",
        prompt_tokens=4,
        completion_tokens=2,
        total_tokens=6,
    )
    async_db.add(cost_chat)
    async_db.add(cost_agent)
    await async_db.commit()

    service = RunService(async_db, ctx)
    summary = await service.summarize_costs(mode="chat")

    assert summary.tokens_prompt == 12
    assert summary.tokens_completion == 7
    assert summary.embedding_count == 0
    assert summary.rerank_count == 0
    assert summary.ms_total == 0


@pytest.mark.asyncio
async def test_list_cost_entries_scope_since_and_order(async_db):
    """Cost entry listing scopes by workspace, filters by since, orders ascending."""

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )

    run_id = generate_run_id()
    async_db.add(
        Run(
            id=run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            mode="chat",
            subject_kind="thread",
            subject_id="thr-cost",
            subject_version_id="ver-cost",
            status="succeeded",
        )
    )

    early = RunCostEntry(
        run_id=run_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        billing_basis="tokens",
        billed_quantity=5,
        prompt_tokens=3,
        completion_tokens=2,
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    late = RunCostEntry(
        run_id=run_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        billing_basis="tokens",
        billed_quantity=9,
        prompt_tokens=6,
        completion_tokens=3,
        created_at=datetime(2026, 7, 20, tzinfo=UTC),
    )
    foreign = RunCostEntry(
        run_id=run_id,
        tenant_id="other_tenant",
        workspace_id=ctx.workspace_id,
        billing_basis="tokens",
        billed_quantity=1,
        created_at=datetime(2026, 7, 5, tzinfo=UTC),
    )
    async_db.add(early)
    async_db.add(late)
    async_db.add(foreign)
    await async_db.commit()

    service = RunService(async_db, ctx)

    entries = await service.list_cost_entries(limit=10, offset=0)
    assert [entry.id for entry in entries] == [early.id, late.id]
    assert entries[0].run_id == run_id
    assert entries[0].prompt_tokens == 3

    since_entries = await service.list_cost_entries(since=datetime(2026, 7, 10, tzinfo=UTC))
    assert [entry.id for entry in since_entries] == [late.id]

    paged = await service.list_cost_entries(limit=1, offset=1)
    assert [entry.id for entry in paged] == [late.id]


@pytest.mark.asyncio
async def test_list_runs_scope_filtering(async_db):
    """List runs respects tenant/workspace scope."""

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )

    run_id = generate_run_id()
    run_local = Run(
        id=run_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="chat",
        subject_kind="thread",
        subject_id="thr-local",
        subject_version_id="ver-chat",
        status="succeeded",
    )
    run_other = Run(
        id=generate_run_id(),
        tenant_id="other_tenant",
        workspace_id=ctx.workspace_id,
        mode="chat",
        subject_kind="thread",
        subject_id="thr-other",
        subject_version_id="ver-chat",
        status="succeeded",
    )
    async_db.add(run_local)
    async_db.add(run_other)
    await async_db.commit()

    service = RunService(async_db, ctx)
    runs = await service.list_runs(limit=10, offset=0)

    assert len(runs) == 1
    assert runs[0].id == run_id


@pytest.mark.asyncio
async def test_get_run_includes_steps_artifacts_costs(async_db):
    """Run detail returns steps, artifacts, and cost summary."""

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )

    run_id = generate_run_id()
    step_id = generate_step_id()
    artifact_id = generate_artifact_id()

    run = Run(
        id=run_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="chat",
        kind="chat",
        subject_kind="thread",
        subject_id="thr-detail",
        subject_version_id="ver-chat",
        status="succeeded",
        trace_id="trace-1",
    )
    step = RunStep(
        id=step_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run_id,
        step_id="st_llm",
        step_type="llm",
        status="succeeded",
    )
    artifact = RunArtifact(
        id=artifact_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run_id,
        step_id=step_id,
        type="log",
        storage_key="logs/test.log",
        mime="text/plain",
        size_bytes=12,
        sha256="deadbeef",
    )
    cost = RunCostEntry(
        run_id=run_id,
        step_id=step_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        currency="USD",
        amount=0,
        billing_basis="tokens",
        billed_quantity=10,
        provider="openai",
        model_ref="model:openai:gpt-4",
        prompt_tokens=6,
        completion_tokens=4,
        total_tokens=10,
    )
    async_db.add(run)
    async_db.add(step)
    async_db.add(artifact)
    async_db.add(cost)
    await async_db.commit()

    service = RunService(async_db, ctx)
    detail = await service.get_run(run_id)

    assert detail.run.id == run_id
    assert len(detail.steps) == 1
    assert detail.steps[0].id == step_id
    assert len(detail.artifacts) == 1
    assert detail.artifacts[0].id == artifact_id
    assert detail.usage_summary.tokens_prompt == 6
    assert detail.usage_summary.tokens_completion == 4


@pytest.mark.asyncio
async def test_list_runs_filters_by_trace_id(async_db):
    """List runs can filter by trace id."""

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )

    run_a = Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="chat",
        subject_kind="thread",
        subject_id="thr-a",
        subject_version_id="ver-chat",
        status="succeeded",
        trace_id="trace-a",
    )
    run_b = Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="chat",
        subject_kind="thread",
        subject_id="thr-b",
        subject_version_id="ver-chat",
        status="succeeded",
        trace_id="trace-b",
    )
    async_db.add(run_a)
    async_db.add(run_b)
    await async_db.commit()

    service = RunService(async_db, ctx)
    runs = await service.list_runs(trace_id="trace-a", limit=10, offset=0)

    assert len(runs) == 1
    assert runs[0].id == run_a.id


@pytest.mark.asyncio
async def test_cost_summaries_group_by_day_mode_subject(async_db):
    """Cost summaries aggregate by day, mode, and subject."""

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )

    run_day1 = Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="chat",
        status="succeeded",
        subject_kind="thread",
        subject_id="thr-day-1",
        subject_version_id="subj-1",
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    run_day2 = Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="workflow",
        status="succeeded",
        subject_kind="workflow",
        subject_id="wf-day-2",
        subject_version_id="subj-2",
        started_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    async_db.add(run_day1)
    async_db.add(run_day2)
    await async_db.commit()

    async_db.add(
        RunCostEntry(
            run_id=run_day1.id,
            step_id=None,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            currency="USD",
            amount=0,
            billing_basis="tokens",
            billed_quantity=5,
            provider="openai",
            model_ref="model:openai:gpt-4",
            prompt_tokens=3,
            completion_tokens=2,
            total_tokens=5,
        )
    )
    async_db.add(
        RunCostEntry(
            run_id=run_day2.id,
            step_id=None,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            currency="USD",
            amount=0,
            billing_basis="tokens",
            billed_quantity=7,
            provider="anthropic",
            model_ref="model:anthropic:claude-3",
            prompt_tokens=4,
            completion_tokens=3,
            total_tokens=7,
        )
    )
    await async_db.commit()

    service = RunService(async_db, ctx)

    by_day = await service.summarize_costs_by_day()
    assert len(by_day) == 2
    assert by_day[0].tokens_prompt == 3
    assert by_day[1].tokens_prompt == 4

    by_mode = await service.summarize_costs_by_mode()
    assert {item.mode for item in by_mode} == {"chat", "workflow"}

    by_mode_filtered = await service.summarize_costs_by_mode(mode="chat")
    assert len(by_mode_filtered) == 1
    assert by_mode_filtered[0].mode == "chat"

    by_subject = await service.summarize_costs_by_subject()
    assert {item.subject_version_id for item in by_subject} == {"subj-1", "subj-2"}

    by_provider = await service.summarize_costs_by_provider()
    assert {item.provider for item in by_provider} == {"openai", "anthropic"}

    by_model = await service.summarize_costs_by_model()
    assert {item.model_ref for item in by_model} == {"model:openai:gpt-4", "model:anthropic:claude-3"}


@pytest.mark.asyncio
async def test_list_steps_filters_by_run_and_scope(async_db):
    """List steps respects tenant/workspace scope and run filters."""

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )

    run_id = generate_run_id()
    other_run_id = generate_run_id()

    async_db.add(
        Run(
            id=run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            mode="workflow",
            subject_kind="workflow",
            subject_id="wf-steps-a",
            subject_version_id="ver-workflow",
            status="succeeded",
        )
    )
    async_db.add(
        Run(
            id=other_run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            mode="workflow",
            subject_kind="workflow",
            subject_id="wf-steps-b",
            subject_version_id="ver-workflow",
            status="succeeded",
        )
    )
    await async_db.commit()

    step_ok = RunStep(
        id=generate_step_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run_id,
        step_id="st_ok",
        step_type="tool",
        status="succeeded",
    )
    step_other_run = RunStep(
        id=generate_step_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=other_run_id,
        step_id="st_other",
        step_type="tool",
        status="succeeded",
    )
    step_other_scope = RunStep(
        id=generate_step_id(),
        tenant_id="other_tenant",
        workspace_id=ctx.workspace_id,
        run_id=run_id,
        step_id="st_other_scope",
        step_type="tool",
        status="succeeded",
    )
    async_db.add(step_ok)
    async_db.add(step_other_run)
    async_db.add(step_other_scope)
    await async_db.commit()

    service = RunService(async_db, ctx)
    steps = await service.list_steps(run_id=run_id, limit=10, offset=0)

    assert len(steps) == 1
    assert steps[0].id == step_ok.id


@pytest.mark.asyncio
async def test_summarize_step_metrics(async_db):
    """Summarize step metrics by type/status."""

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )
    run_id = generate_run_id()
    async_db.add(
        Run(
            id=run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            mode="workflow",
            subject_kind="workflow",
            subject_id="wf-metrics",
            subject_version_id="ver-workflow",
            status="succeeded",
        )
    )
    await async_db.commit()

    steps = [
        RunStep(
            id=generate_step_id(),
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run_id,
            step_id="st_tool_1",
            step_type="tool",
            status="succeeded",
            metrics_json={"latency_ms": 100},
        ),
        RunStep(
            id=generate_step_id(),
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run_id,
            step_id="st_tool_2",
            step_type="tool",
            status="succeeded",
            metrics_json={"latency_ms": 300},
        ),
        RunStep(
            id=generate_step_id(),
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run_id,
            step_id="st_tool_failed",
            step_type="tool",
            status="failed",
            metrics_json={"latency_ms": 50},
        ),
        RunStep(
            id=generate_step_id(),
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run_id,
            step_id="st_llm",
            step_type="llm",
            status="succeeded",
            metrics_json={"latency_ms": 120},
        ),
    ]
    for step in steps:
        async_db.add(step)
    await async_db.commit()

    service = RunService(async_db, ctx)
    summary = await service.summarize_step_metrics(run_id=run_id)

    summary_map = {(item.step_type, item.status): item for item in summary}
    tool_ok = summary_map[("tool", "succeeded")]
    assert tool_ok.count == 2
    assert tool_ok.min_latency_ms == 100
    assert tool_ok.max_latency_ms == 300
    assert tool_ok.avg_latency_ms == 200.0
    assert summary_map[("tool", "failed")].count == 1
    assert summary_map[("llm", "succeeded")].count == 1

