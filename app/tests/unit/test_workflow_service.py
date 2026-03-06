"""test_workflow_service

Unit tests for WorkflowAppFacadeService run controls and DSL handling.
"""

import pytest

from app.kernel.commons.ids import generate_run_id
from app.kernel.trace.models import Run
from app.modules.workflow.application.app_facade import WorkflowAppFacadeService
from app.modules.workflow.application.schemas import WorkflowCreate, WorkflowVersionCreate
from app.modules.appcenter.infra.repository import AppRepository, AppVersionRepository


def _sample_workflow_spec() -> dict:
    return {
        "name": "Test Flow",
        "inputs_schema": {"type": "object", "properties": {}},
        "outputs_schema": {"type": "object", "properties": {"value": {"type": "string"}}},
        "graph": {
            "nodes": [
                {
                    "id": "n1",
                    "type": "llm",
                    "params": {"prompt": "Hello"},
                },
                {
                    "id": "n2",
                    "type": "output",
                    "params": {"value": "{{ steps.n1.output.text }}"},
                },
            ],
            "edges": [{"id": "e1", "from": "n1", "to": "n2"}],
        },
    }


def _build_service(db, ctx) -> WorkflowAppFacadeService:
    return WorkflowAppFacadeService(
        db=db,
        ctx=ctx,
        app_repo=AppRepository(db, ctx),
        version_repo=AppVersionRepository(db, ctx),
    )


@pytest.mark.asyncio
async def test_workflow_export_import_dsl(db, tenant1_ctx):
    """Export returns current version and import creates new version."""
    service = _build_service(db, tenant1_ctx)

    workflow = await service.create_workflow(
        WorkflowCreate(name="wf-demo", description="demo workflow")
    )
    version = await service.publish_version(
        workflow.id,
        WorkflowVersionCreate(
            graph_json=_sample_workflow_spec(),
            created_by=tenant1_ctx.user_id,
        ),
    )

    exported = await service.export_dsl(workflow.id)
    assert exported["format"] == "json"
    assert exported["dsl"] == version.spec_json

    new_spec = _sample_workflow_spec()
    new_spec["name"] = "Test Flow V2"
    imported = await service.import_dsl(
        workflow.id,
        new_spec,
        created_by=tenant1_ctx.user_id,
    )

    assert imported.spec_json == new_spec
    updated = await service.get_workflow(workflow.id)
    assert updated.current_version_id == imported.id

    exported_yaml = await service.export_dsl(workflow.id, format="yaml")
    assert exported_yaml["format"] == "yaml"
    assert isinstance(exported_yaml["dsl"], str)

    imported_yaml = await service.import_dsl(
        workflow.id,
        exported_yaml["dsl"],
        created_by=tenant1_ctx.user_id,
        format="yaml",
    )
    assert imported_yaml.spec_json["name"] == new_spec["name"]


@pytest.mark.asyncio
async def test_workflow_pause_resume(db, tenant1_ctx):
    """Pause/resume toggles workflow run status."""
    service = _build_service(db, tenant1_ctx)
    app_id = "wf_test"
    run_id = generate_run_id()
    run = Run(
        id=run_id,
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        mode="workflow",
        app_id=app_id,
        app_version_id="ver_test",
        status="running",
    )
    db.add(run)
    db.commit()

    paused = await service.pause_run(app_id, run_id)
    assert paused["status"] == "paused"
    assert db.get(Run, run_id).status == "paused"

    resumed = await service.resume_run(app_id, run_id)
    assert resumed["status"] == "running"
    assert db.get(Run, run_id).status == "running"


@pytest.mark.asyncio
async def test_workflow_retry_replay_use_inputs(db, tenant1_ctx, monkeypatch):
    """Retry/replay reuse input_summary when inputs not provided."""
    service = _build_service(db, tenant1_ctx)
    app_id = "wf_retry"
    run_id = generate_run_id()
    run = Run(
        id=run_id,
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        mode="workflow",
        app_id=app_id,
        app_version_id="ver_retry",
        status="failed",
        input_summary='{"query": "hello"}',
    )
    db.add(run)
    db.commit()

    calls = []

    async def _fake_execute(app_id_arg, inputs):
        calls.append((app_id_arg, inputs))
        return {"run_id": "run_new", "output": "ok"}

    monkeypatch.setattr(service, "execute_workflow", _fake_execute)

    retry_result = await service.retry_run(app_id, run_id)
    assert retry_result["run_id"] == "run_new"
    assert calls[0] == (app_id, {"query": "hello"})

    replay_result = await service.replay_run(app_id, run_id)
    assert replay_result["run_id"] == "run_new"
    assert calls[1] == (app_id, {"query": "hello"})
