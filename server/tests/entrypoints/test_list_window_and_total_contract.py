"""Entrypoint contract for list counts and creation-time windows.

The console renders counts ("1,284 runs", "47 audits in 24h") next to lists it
only ever holds one page of. These assertions lock the two query parameters
those readouts depend on, so a later refactor cannot quietly drop them and send
the console back to hardcoded figures.
"""

from datetime import timedelta

import pytest
from fastapi import status

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.db.models.tasks import Task
from app.modules.identity.domain.models import ResourceGrant


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def _seed_runs(db, count: int) -> None:
    for index in range(count):
        db.add(
            Run(
                id=f"run_window_{index}",
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                user_id="test-user",
                trace_id="trace_window",
                mode="agent",
                kind="agent",
                subject_kind="agent",
                subject_id="agt_window",
                subject_version_id="agtv_window",
                status="succeeded",
                started_at=utc_now(),
            )
        )
    db.commit()


def test_runs_list_reports_a_total_only_when_asked(client, db):
    _seed_runs(db, 3)

    plain = client.get("/api/v1/runs", params={"page_size": 2}, headers=_headers())
    assert plain.status_code == status.HTTP_200_OK
    assert plain.json()["data"]["total"] is None

    counted = client.get(
        "/api/v1/runs",
        params={"page_size": 2, "with_total": "true"},
        headers=_headers(),
    )
    assert counted.status_code == status.HTTP_200_OK
    payload = counted.json()["data"]
    assert len(payload["items"]) == 2
    assert payload["total"] == 3


def test_runs_list_accepts_the_started_window(client, db):
    _seed_runs(db, 2)
    future = (utc_now() + timedelta(hours=1)).isoformat()

    response = client.get(
        "/api/v1/runs",
        params={"started_after": future, "with_total": "true"},
        headers=_headers(),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["total"] == 0


def test_audits_list_accepts_a_creation_window_and_total(client, db):
    now = utc_now()
    _seed_runs(db, 1)
    for age_hours in (1, 48):
        db.add(
            AuditEvent(
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                event_type="tool.call",
                resource_type="tool",
                resource_id="tool_window",
                run_id="run_window_0",
                operation="invoke",
                outcome="allow",
                created_at=now - timedelta(hours=age_hours),
            )
        )
    db.commit()

    response = client.get(
        "/api/v1/runs/audits",
        params={"since": (now - timedelta(hours=24)).isoformat(), "with_total": "true"},
        headers=_headers(),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["total"] == 1


def test_tasks_list_accepts_a_creation_window_and_total(client, db):
    now = utc_now()
    for index, age_hours in enumerate((2, 72)):
        db.add(
            Task(
                id=f"task_window_{index}",
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                task_type="agent.execute",
                status="queued",
                created_at=now - timedelta(hours=age_hours),
            )
        )
    db.commit()

    response = client.get(
        "/api/v1/tasks",
        params={"since": (now - timedelta(hours=24)).isoformat(), "with_total": "true"},
        headers=_headers(),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["total"] == 1


def test_a_malformed_window_is_rejected_rather_than_ignored(client):
    """A bad timestamp must fail loudly; silently ignoring it would show the
    wrong window's numbers as if they were the requested one.

    The app maps request validation to its own 400 envelope, so that is the
    contract here rather than FastAPI's default 422.
    """
    response = client.get(
        "/api/v1/runs/audits",
        params={"since": "last-tuesday"},
        headers=_headers(),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_run_window_summary_answers_the_overview_in_one_call(client, db):
    """Volume, pass rate and spend come back together so they cannot disagree."""
    _seed_runs(db, 2)
    db.add(
        Run(
            id="run_window_failed",
            tenant_id="test-tenant",
            workspace_id="test-workspace",
            user_id="test-user",
            trace_id="trace_window",
            mode="agent",
            kind="agent",
            subject_kind="agent",
            subject_id="agt_window",
            subject_version_id="agtv_window",
            status="failed",
            started_at=utc_now(),
        )
    )
    db.commit()

    response = client.get("/api/v1/runs/summary/window", headers=_headers())
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["total"] == 3
    assert payload["succeeded"] == 2
    assert payload["failed"] == 1
    assert payload["pass_rate"] == pytest.approx(2 / 3)
    assert payload["charges"]["entry_count"] == 0


def test_resource_grants_can_be_listed_for_the_whole_workspace(client, db):
    """The access surface reads every grant in one call, not one per object."""
    for index, resource_type in enumerate(("agent", "workflow")):
        db.add(
            ResourceGrant(
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                resource_type=resource_type,
                resource_id=f"res_{index}",
                user_id="test-user",
                actions=["read"],
            )
        )
    db.commit()

    everything = client.get("/api/v1/resource-grants", headers=_headers())
    assert everything.status_code == status.HTTP_200_OK
    assert len(everything.json()["data"]) == 2

    one_kind = client.get(
        "/api/v1/resource-grants",
        params={"resource_type": "agent"},
        headers=_headers(),
    )
    assert [row["resource_type"] for row in one_kind.json()["data"]] == ["agent"]

    named = client.get(
        "/api/v1/resource-grants",
        params={"resource_type": "agent", "resource_id": "res_0"},
        headers=_headers(),
    )
    assert [row["resource_id"] for row in named.json()["data"]] == ["res_0"]
