"""Entrypoint contract for schedules.

The console's schedules screen was the one page with no server behind it. These
lock the shape it reads and the refusals that keep a broken schedule from being
saved in the first place.
"""

import pytest
from fastapi import status


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


async def _create(async_client, **overrides) -> dict:
    payload = {
        "name": "hourly-audit",
        "target_kind": "agent",
        "target_id": "agt_audit",
        "cron": "0 * * * *",
        "timezone": "UTC",
        "inputs": {"input": "run the audit"},
    }
    payload.update(overrides)
    response = await async_client.post("/api/v1/schedules", json=payload, headers=_headers())
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_a_schedule_round_trips_with_its_next_firing(async_client):
    created = await _create(async_client)

    assert created["cron"] == "0 * * * *"
    assert created["enabled"] is True
    # The screen shows when it next fires; that has to be computed on save.
    assert created["next_fire_at"]
    assert created["last_status"] is None

    listed = (await async_client.get("/api/v1/schedules", headers=_headers())).json()["data"]
    assert [row["id"] for row in listed] == [created["id"]]

    fetched = await async_client.get(f"/api/v1/schedules/{created['id']}", headers=_headers())
    assert fetched.json()["data"]["name"] == "hourly-audit"


@pytest.mark.asyncio
async def test_an_expression_that_cannot_fire_is_refused_on_save(async_client):
    """Better a red form now than a schedule that silently never runs."""
    response = await async_client.post(
        "/api/v1/schedules",
        json={
            "name": "broken",
            "target_kind": "agent",
            "target_id": "agt",
            "cron": "every tuesday",
        },
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_a_target_that_is_neither_an_agent_nor_a_workflow_is_refused(async_client):
    response = await async_client.post(
        "/api/v1/schedules",
        json={
            "name": "teapot",
            "target_kind": "teapot",
            "target_id": "t",
            "cron": "0 * * * *",
        },
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_pausing_removes_the_next_firing_and_resuming_restores_it(async_client):
    created = await _create(async_client, name="nightly", cron="0 2 * * *")

    paused = (await async_client.patch(
        f"/api/v1/schedules/{created['id']}",
        json={"enabled": False},
        headers=_headers(),
    )).json()["data"]
    assert paused["enabled"] is False
    # Showing a next firing for a paused schedule would promise something that
    # is not going to happen.
    assert paused["next_fire_at"] is None

    resumed = (await async_client.patch(
        f"/api/v1/schedules/{created['id']}",
        json={"enabled": True},
        headers=_headers(),
    )).json()["data"]
    assert resumed["next_fire_at"]


@pytest.mark.asyncio
async def test_previewing_an_expression_needs_no_schedule(async_client):
    """So somebody can check what they typed before committing to it."""
    response = await async_client.post(
        "/api/v1/schedules/preview",
        json={"cron": "0 9 * * 1", "timezone": "UTC", "count": 3},
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_200_OK
    fires = response.json()["data"]["fires_at"]
    assert len(fires) == 3
    assert fires == sorted(fires)


@pytest.mark.asyncio
async def test_previewing_something_unparseable_says_so(async_client):
    response = await async_client.post(
        "/api/v1/schedules/preview",
        json={"cron": "0 99 * * *"},
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_running_a_schedule_now_queues_work_without_moving_the_schedule(async_client):
    created = await _create(async_client, name="on-demand", cron="0 2 * * *")

    response = await async_client.post(f"/api/v1/schedules/{created['id']}/run", headers=_headers())

    assert response.status_code == status.HTTP_200_OK
    fired = response.json()["data"]
    assert fired["last_status"] == "started"
    assert fired["last_fired_at"]
    # Asking for a run now is not the same as moving the schedule.
    assert fired["next_fire_at"] == created["next_fire_at"]


@pytest.mark.asyncio
async def test_a_deleted_schedule_is_gone(async_client):
    created = await _create(async_client, name="temporary")

    deleted = await async_client.delete(f"/api/v1/schedules/{created['id']}", headers=_headers())
    assert deleted.status_code == status.HTTP_204_NO_CONTENT

    assert (
        (await async_client.get(f"/api/v1/schedules/{created['id']}", headers=_headers())).status_code
        == status.HTTP_404_NOT_FOUND
    )
