"""Entrypoint tests for owner-only real-time diagnostics."""

from contextlib import contextmanager

from fastapi import status

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.agent.domain.models import Agent
from app.modules.feedback.domain.models import ProductFeedback
from app.modules.workflow.domain.models import Workflow


class _AvailableStorage:
    async def ensure_ready(self) -> None:
        return None


class _UnavailableStorage:
    async def ensure_ready(self) -> None:
        raise RuntimeError("storage unavailable")


@contextmanager
def _as_context(ctx: RequestContext):
    previous = app.dependency_overrides.get(get_current_context)

    async def _override() -> RequestContext:
        return ctx

    app.dependency_overrides[get_current_context] = _override
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_current_context, None)
        else:
            app.dependency_overrides[get_current_context] = previous


@contextmanager
def _with_storage(storage):
    from app.api.v1.diagnostics.dependencies import get_diagnostics_storage

    app.dependency_overrides[get_diagnostics_storage] = lambda: storage
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_diagnostics_storage, None)


def _seed_diagnostics_data(db) -> None:
    scope = {"tenant_id": "test-tenant", "workspace_id": "test-workspace"}
    db.add_all(
        [
            Agent(id="agt_diag", name="Diagnostic agent", **scope),
            Workflow(id="wf_diag", name="Diagnostic workflow", **scope),
            Run(
                id="run_active",
                mode="agent",
                status="running",
                subject_kind="agent",
                subject_id="agt_diag",
                **scope,
            ),
            Run(
                id="run_failed",
                mode="workflow",
                status="failed",
                subject_kind="workflow",
                subject_id="wf_diag",
                **scope,
            ),
            ProductFeedback(
                id="fbk_diag",
                title="Diagnostic feedback",
                description="Open product feedback",
                category="bug",
                priority="high",
                status="open",
                created_by="test-user",
                updated_by="test-user",
                **scope,
            ),
            Agent(
                id="agt_diag_outside",
                tenant_id="test-tenant",
                workspace_id="other-workspace",
                name="Outside diagnostic agent",
            ),
        ]
    )
    db.commit()


def test_owner_gets_real_time_dependency_process_and_workspace_snapshot(client, db) -> None:
    _seed_diagnostics_data(db)

    with _with_storage(_AvailableStorage()):
        response = client.get("/api/v1/diagnostics")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["overall_status"] == "healthy"
    assert {item["name"]: item["status"] for item in payload["dependencies"]} == {
        "database": "healthy",
        "object_storage": "healthy",
    }
    assert payload["workspace"]["agents"] == 1
    assert payload["workspace"]["workflows"] == 1
    assert payload["workspace"]["active_runs"] == 1
    assert payload["workspace"]["failed_runs_24h"] == 1
    assert payload["workspace"]["open_feedback"] == 1
    assert payload["process"]["uptime_seconds"] >= 0
    assert payload["process"]["rss_bytes"] > 0
    assert payload["version"]
    assert payload["generated_at"]


def test_diagnostics_is_workspace_owner_only(client) -> None:
    viewer = RequestContext(
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="viewer-user",
        tenant_role="Viewer",
        workspace_role="Viewer",
    )

    with _as_context(viewer), _with_storage(_AvailableStorage()):
        response = client.get("/api/v1/diagnostics")

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_diagnostics_reports_probe_failure_without_hiding_the_snapshot(client) -> None:
    with _with_storage(_UnavailableStorage()):
        response = client.get("/api/v1/diagnostics")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["overall_status"] == "degraded"
    storage = next(item for item in payload["dependencies"] if item["name"] == "object_storage")
    assert storage["status"] == "unavailable"
    assert storage["message"] == "RuntimeError"
