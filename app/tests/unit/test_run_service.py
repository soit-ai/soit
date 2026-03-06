"""test_run_service

Unit tests for RunService cost summaries and filtering.
"""

from datetime import datetime, timezone
from sqlmodel import SQLModel

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.ids import generate_run_id, generate_step_id, generate_artifact_id
from app.kernel.trace.models import Run, RunCostEntry, RunStep, RunArtifact
from app.kernel.trace.service import RunService


def test_run_cost_summary_filters(db):
    """Cost summary aggregates only matching runs."""
    SQLModel.metadata.create_all(db.get_bind())

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )

    run_id_chat = generate_run_id()
    run_id_bot = generate_run_id()

    run_chat = Run(
        id=run_id_chat,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="chat",
        app_id="app-chat",
        app_version_id="conv-1",
        status="succeeded",
    )
    run_bot = Run(
        id=run_id_bot,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="bot",
        app_id="app-bot",
        app_version_id="bot-1",
        status="succeeded",
    )
    db.add(run_chat)
    db.add(run_bot)

    cost_chat = RunCostEntry(
        run_id=run_id_chat,
        step_id=None,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        currency="USD",
        amount=0,
        unit="tokens",
        quantity=19,
        provider="openai",
        model_ref="model:openai:gpt-4",
        prompt_tokens=12,
        completion_tokens=7,
        total_tokens=19,
    )
    cost_bot = RunCostEntry(
        run_id=run_id_bot,
        step_id=None,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        currency="USD",
        amount=0,
        unit="tokens",
        quantity=6,
        provider="openai",
        model_ref="model:openai:gpt-5.1",
        prompt_tokens=4,
        completion_tokens=2,
        total_tokens=6,
    )
    db.add(cost_chat)
    db.add(cost_bot)
    db.commit()

    service = RunService(db, ctx)
    summary = service.summarize_costs(mode="chat")

    assert summary.tokens_prompt == 12
    assert summary.tokens_completion == 7
    assert summary.embedding_count == 0
    assert summary.rerank_count == 0
    assert summary.ms_total == 0


def test_list_runs_scope_filtering(db):
    """List runs respects tenant/workspace scope."""
    SQLModel.metadata.create_all(db.get_bind())

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
        app_id="app-chat",
        app_version_id="ver-chat",
        status="succeeded",
    )
    run_other = Run(
        id=generate_run_id(),
        tenant_id="other_tenant",
        workspace_id=ctx.workspace_id,
        mode="chat",
        app_id="app-chat",
        app_version_id="ver-chat",
        status="succeeded",
    )
    db.add(run_local)
    db.add(run_other)
    db.commit()

    service = RunService(db, ctx)
    runs = service.list_runs(limit=10, offset=0)

    assert len(runs) == 1
    assert runs[0].id == run_id


def test_get_run_includes_steps_artifacts_costs(db):
    """Run detail returns steps, artifacts, and cost summary."""
    SQLModel.metadata.create_all(db.get_bind())

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
        app_id="app-chat",
        app_version_id="ver-chat",
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
        unit="tokens",
        quantity=10,
        provider="openai",
        model_ref="model:openai:gpt-4",
        prompt_tokens=6,
        completion_tokens=4,
        total_tokens=10,
    )
    db.add(run)
    db.add(step)
    db.add(artifact)
    db.add(cost)
    db.commit()

    service = RunService(db, ctx)
    detail = service.get_run(run_id)

    assert detail.run.id == run_id
    assert len(detail.steps) == 1
    assert detail.steps[0].id == step_id
    assert len(detail.artifacts) == 1
    assert detail.artifacts[0].id == artifact_id
    assert detail.cost_summary.tokens_prompt == 6
    assert detail.cost_summary.tokens_completion == 4


def test_list_runs_filters_by_trace_id(db):
    """List runs can filter by trace id."""
    SQLModel.metadata.create_all(db.get_bind())

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
        app_id="app-chat",
        app_version_id="ver-chat",
        status="succeeded",
        trace_id="trace-a",
    )
    run_b = Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="chat",
        app_id="app-chat",
        app_version_id="ver-chat",
        status="succeeded",
        trace_id="trace-b",
    )
    db.add(run_a)
    db.add(run_b)
    db.commit()

    service = RunService(db, ctx)
    runs = service.list_runs(trace_id="trace-a", limit=10, offset=0)

    assert len(runs) == 1
    assert runs[0].id == run_a.id


def test_cost_summaries_group_by_day_mode_app(db):
    """Cost summaries aggregate by day, mode, and app."""
    SQLModel.metadata.create_all(db.get_bind())

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
        app_id="app-chat",
        status="succeeded",
        app_version_id="app-1",
        started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    run_day2 = Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        mode="workflow",
        app_id="app-workflow",
        status="succeeded",
        app_version_id="app-2",
        started_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )
    db.add(run_day1)
    db.add(run_day2)
    db.commit()

    db.add(
        RunCostEntry(
            run_id=run_day1.id,
            step_id=None,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            currency="USD",
            amount=0,
            unit="tokens",
            quantity=5,
            provider="openai",
            model_ref="model:openai:gpt-4",
            prompt_tokens=3,
            completion_tokens=2,
            total_tokens=5,
        )
    )
    db.add(
        RunCostEntry(
            run_id=run_day2.id,
            step_id=None,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            currency="USD",
            amount=0,
            unit="tokens",
            quantity=7,
            provider="anthropic",
            model_ref="model:anthropic:claude-3",
            prompt_tokens=4,
            completion_tokens=3,
            total_tokens=7,
        )
    )
    db.commit()

    service = RunService(db, ctx)

    by_day = service.summarize_costs_by_day()
    assert len(by_day) == 2
    assert by_day[0].tokens_prompt == 3
    assert by_day[1].tokens_prompt == 4

    by_mode = service.summarize_costs_by_mode()
    assert {item.mode for item in by_mode} == {"chat", "workflow"}

    by_mode_filtered = service.summarize_costs_by_mode(mode="chat")
    assert len(by_mode_filtered) == 1
    assert by_mode_filtered[0].mode == "chat"

    by_app = service.summarize_costs_by_app()
    assert {item.app_version_id for item in by_app} == {"app-1", "app-2"}

    by_provider = service.summarize_costs_by_provider()
    assert {item.provider for item in by_provider} == {"openai", "anthropic"}

    by_model = service.summarize_costs_by_model()
    assert {item.model_ref for item in by_model} == {"model:openai:gpt-4", "model:anthropic:claude-3"}


def test_list_steps_filters_by_run_and_scope(db):
    """List steps respects tenant/workspace scope and run filters."""
    SQLModel.metadata.create_all(db.get_bind())

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )

    run_id = generate_run_id()
    other_run_id = generate_run_id()

    db.add(
        Run(
            id=run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            mode="workflow",
            app_id="app-workflow",
            app_version_id="ver-workflow",
            status="succeeded",
        )
    )
    db.add(
        Run(
            id=other_run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            mode="workflow",
            app_id="app-workflow",
            app_version_id="ver-workflow",
            status="succeeded",
        )
    )
    db.commit()

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
    db.add(step_ok)
    db.add(step_other_run)
    db.add(step_other_scope)
    db.commit()

    service = RunService(db, ctx)
    steps = service.list_steps(run_id=run_id, limit=10, offset=0)

    assert len(steps) == 1
    assert steps[0].id == step_ok.id


def test_summarize_step_metrics(db):
    """Summarize step metrics by type/status."""
    SQLModel.metadata.create_all(db.get_bind())

    ctx = RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )
    run_id = generate_run_id()
    db.add(
        Run(
            id=run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            mode="workflow",
            app_id="app-workflow",
            app_version_id="ver-workflow",
            status="succeeded",
        )
    )
    db.commit()

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
        db.add(step)
    db.commit()

    service = RunService(db, ctx)
    summary = service.summarize_step_metrics(run_id=run_id)

    summary_map = {(item.step_type, item.status): item for item in summary}
    tool_ok = summary_map[("tool", "succeeded")]
    assert tool_ok.count == 2
    assert tool_ok.min_latency_ms == 100
    assert tool_ok.max_latency_ms == 300
    assert tool_ok.avg_latency_ms == 200.0
    assert summary_map[("tool", "failed")].count == 1
    assert summary_map[("llm", "succeeded")].count == 1
