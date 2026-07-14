"""Enterprise MVP extended scenario seed integration tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import and_, select

from app.kernel.runtime.db.models.responses import Response
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.db.models.threads import Thread
from app.modules.agent.domain.models import Agent, AgentBinding, AgentVersion
from app.modules.knowledge.domain.models import Knowledge
from app.modules.modelhub.domain.models import Provider, ProviderModel  # noqa: F401
from app.modules.observe.domain.models import ApprovalRequest, RunFeedback  # noqa: F401
from app.modules.plugin.domain.models import PluginInstalledArtifact
from app.modules.secrets.domain.models import Secret  # noqa: F401
from app.modules.workflow.domain.models import Workflow, WorkflowRun


def _unwrap(row):
    if row is None:
        return None
    if isinstance(row, tuple):
        return row[0]
    try:
        return row[0]
    except Exception:
        return row


def _args(**overrides):
    data = {
        "email": "scenario-seed@example.com",
        "password": "changeme123",
        "name": "Scenario Seed User",
        "tenant_name": "scenario-seed-tenant",
        "workspace_name": "default",
        "profile": "broad",
        "reset": True,
        "json_output": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_enterprise_mvp_scenario_seed_is_idempotent_and_preserves_non_seed_data(db):
    from scripts.seed_enterprise_mvp_scenarios import (
        SEED_SOURCE,
        seed_enterprise_mvp_scenarios,
    )

    first = await seed_enterprise_mvp_scenarios(db, _args())
    manual_thread = Thread(
        id="thread_manual_non_seed",
        tenant_id=first.tenant_id,
        workspace_id=first.workspace_id,
        title="Manual non-seed thread",
        thread_type="chat",
        status="active",
        metadata_json={"seed_source": "manual"},
    )
    db.add(manual_thread)
    db.commit()

    second = await seed_enterprise_mvp_scenarios(db, _args())
    third = await seed_enterprise_mvp_scenarios(db, _args(reset=False))

    assert second.model_dump() == third.model_dump()
    assert db.get(Thread, "thread_manual_non_seed") is not None

    assert len(second.agent_ids) >= 3
    assert len(second.thread_ids) >= 5
    assert len(second.knowledge_ids) >= 4
    assert len(second.workflow_ids) >= 4
    assert len(second.run_ids) >= 6
    assert len(second.task_ids) >= 7
    assert len(second.plugin_refs) >= 3
    assert len(second.secret_ids) >= 2
    assert len(second.agent_chain_refs) >= 5

    assert db.exec(
        select(Agent).where(
            and_(
                Agent.tenant_id == second.tenant_id,
                Agent.workspace_id == second.workspace_id,
                Agent.profile_json["seed_source"].as_string() == SEED_SOURCE,
            )
        )
    ).first()
    assert db.exec(
        select(Knowledge).where(
            and_(
                Knowledge.tenant_id == second.tenant_id,
                Knowledge.workspace_id == second.workspace_id,
                Knowledge.settings_json["seed_source"].as_string() == SEED_SOURCE,
            )
        )
    ).first()
    assert db.exec(
        select(Workflow).where(
            and_(
                Workflow.tenant_id == second.tenant_id,
                Workflow.workspace_id == second.workspace_id,
                Workflow.metadata_json["seed_source"].as_string() == SEED_SOURCE,
            )
        )
    ).first()

    task_statuses = {
        _unwrap(row)
        for row in db.exec(
            select(Task.status).where(
                and_(
                    Task.tenant_id == second.tenant_id,
                    Task.workspace_id == second.workspace_id,
                    Task.input_json["seed_source"].as_string() == SEED_SOURCE,
                )
            )
        ).all()
    }
    assert {"queued", "running", "waiting_input", "waiting_approval", "succeeded", "failed"} <= task_statuses
    assert "long_running" in {item.get("scenario") for item in (db.get(Task, task_id).input_json for task_id in second.task_ids)}

    assert db.exec(
        select(PluginInstalledArtifact).where(
            and_(
                PluginInstalledArtifact.tenant_id == second.tenant_id,
                PluginInstalledArtifact.workspace_id == second.workspace_id,
                PluginInstalledArtifact.metadata_json["seed_source"].as_string() == SEED_SOURCE,
            )
        )
    ).first()


@pytest.mark.asyncio
async def test_enterprise_mvp_scenario_seed_creates_complete_agent_binding_chains(db):
    from scripts.seed_enterprise_mvp_scenarios import seed_enterprise_mvp_scenarios

    summary = await seed_enterprise_mvp_scenarios(db, _args())
    assert len(summary.agent_chain_refs) >= 5

    all_binding_types: set[str] = set()
    all_bound_plugin_refs: set[str] = set()
    for chain in summary.agent_chain_refs:
        agent = db.get(Agent, chain["agent_id"])
        assert agent is not None
        assert agent.published_version_id == chain["agent_version_id"]

        version = db.get(AgentVersion, chain["agent_version_id"])
        assert version is not None
        bindings_spec = version.spec_json["bindings"]
        assert bindings_spec["model_ref"] == "model:test:agent"

        rows = [
            _unwrap(row)
            for row in db.exec(
                select(AgentBinding).where(AgentBinding.agent_version_id == version.id)
            ).all()
        ]
        by_type: dict[str, set[str]] = {}
        for row in rows:
            by_type.setdefault(row.binding_type, set()).add(row.target_key)
            all_binding_types.add(row.binding_type)

        assert bindings_spec["model_ref"] in by_type["model"]
        assert set(bindings_spec["knowledge_refs"]) <= by_type["knowledge"]
        assert set(bindings_spec["workflow_refs"]) <= by_type["workflow"]
        assert set(bindings_spec.get("tool_refs") or []) <= by_type.get("tool", set())
        assert set(bindings_spec.get("skill_refs") or []) <= by_type.get("skill", set())

        plugin_refs = set(chain["plugin_capability_refs"])
        all_bound_plugin_refs.update(plugin_refs)
        bound_plugin_refs = by_type.get("tool", set()) | by_type.get("skill", set())
        assert plugin_refs <= bound_plugin_refs

    assert "tool" in all_binding_types
    assert "skill" in all_binding_types
    assert "plugin_tool:seed.ticket.audit" in all_bound_plugin_refs
    assert "mcp_tool:seed-compliance-mcp:deny_external_post" in all_bound_plugin_refs
    assert "plugin_skill:seed-support-playbook" in all_bound_plugin_refs


@pytest.mark.asyncio
async def test_enterprise_mvp_scenario_seed_agent_chains_have_replayable_run_evidence(db):
    from scripts.seed_enterprise_mvp_scenarios import seed_enterprise_mvp_scenarios

    summary = await seed_enterprise_mvp_scenarios(db, _args())
    for chain in summary.agent_chain_refs:
        parent_run = db.get(Run, chain["parent_run_id"])
        workflow_trace = db.get(Run, chain["workflow_run_id"])
        task = db.get(Task, chain["task_id"])
        assert parent_run is not None
        assert workflow_trace is not None
        assert task is not None

        workflow_run = _unwrap(
            db.exec(select(WorkflowRun).where(WorkflowRun.run_id == chain["workflow_run_id"])).first()
        )
        assert workflow_run is not None

        steps = [
            _unwrap(row)
            for row in db.exec(select(RunStep).where(RunStep.run_id == parent_run.id)).all()
        ]
        costs = [
            _unwrap(row)
            for row in db.exec(select(RunCostEntry).where(RunCostEntry.run_id == parent_run.id)).all()
        ]
        tool_refs = {
            (step.metrics_json or {}).get("tool_call", {}).get("tool_ref")
            for step in steps
            if isinstance((step.metrics_json or {}).get("tool_call"), dict)
        }

        assert any(step.step_type == "retrieval" for step in steps)
        assert any((step.metrics_json or {}).get("audit_json") for step in steps)
        assert set(chain["plugin_capability_refs"]) & tool_refs or "plugin_skill:seed-support-playbook" in chain["plugin_capability_refs"]
        assert costs

        parent_response = _unwrap(
            db.exec(select(Response).where(Response.run_id == parent_run.id)).first()
        )
        assert parent_response is not None
        citations = parent_response.output_json.get("citations")
        assert citations
        assert all(citation.get("source", "").endswith(".md") for citation in citations)


@pytest.mark.asyncio
async def test_enterprise_mvp_scenario_seed_creates_observe_run_evidence(db):
    from scripts.seed_enterprise_mvp_scenarios import seed_enterprise_mvp_scenarios

    summary = await seed_enterprise_mvp_scenarios(db, _args())
    parent_run = db.get(Run, summary.run_ids[0])
    assert parent_run is not None

    steps = [_unwrap(row) for row in db.exec(select(RunStep).where(RunStep.run_id == parent_run.id)).all()]
    costs = [_unwrap(row) for row in db.exec(select(RunCostEntry).where(RunCostEntry.run_id == parent_run.id)).all()]

    assert any((step.metrics_json or {}).get("tool_call") for step in steps)
    assert any((step.metrics_json or {}).get("audit_json") for step in steps)
    assert costs
    assert summary.citation_sources
    assert any(source.endswith(".md") for source in summary.citation_sources)
