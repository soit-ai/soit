"""Entrypoint contract for saved views and pins.

Both are personal: what one person keeps must never appear for another, and a
default only makes sense one at a time per screen.
"""

import pytest
from fastapi import status


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


@pytest.mark.asyncio
async def test_a_saved_view_round_trips(async_client):
    created = await async_client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "Failed only", "query": "status=failed"},
        headers=_headers(),
    )
    assert created.status_code == status.HTTP_200_OK
    view = created.json()["data"]
    assert view["surface"] == "runs"
    assert view["query"] == "status=failed"
    assert view["is_default"] is False

    listed = await async_client.get("/api/v1/me/views", params={"surface": "runs"}, headers=_headers())
    assert [row["name"] for row in listed.json()["data"]] == ["Failed only"]

    deleted = await async_client.delete(f"/api/v1/me/views/{view['id']}", headers=_headers())
    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    assert (await async_client.get("/api/v1/me/views", headers=_headers())).json()["data"] == []


@pytest.mark.asyncio
async def test_saving_over_a_name_updates_that_view(async_client):
    """Saving over a name is how a filter gets edited, not an error."""
    first = (await async_client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "Recent", "query": "range=24h"},
        headers=_headers(),
    )).json()["data"]

    second = (await async_client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "Recent", "query": "range=7d"},
        headers=_headers(),
    )).json()["data"]

    assert second["id"] == first["id"]
    assert second["query"] == "range=7d"
    assert len((await async_client.get("/api/v1/me/views", headers=_headers())).json()["data"]) == 1


@pytest.mark.asyncio
async def test_only_one_view_per_screen_is_the_default(async_client):
    await async_client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "A", "query": "a=1", "is_default": True},
        headers=_headers(),
    )
    await async_client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "B", "query": "b=1", "is_default": True},
        headers=_headers(),
    )

    views = await async_client.get("/api/v1/me/views", params={"surface": "runs"}, headers=_headers())
    defaults = [row["name"] for row in views.json()["data"] if row["is_default"]]
    assert defaults == ["B"]


@pytest.mark.asyncio
async def test_a_view_for_another_screen_is_not_returned(async_client):
    await async_client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "Runs view", "query": ""},
        headers=_headers(),
    )
    await async_client.post(
        "/api/v1/me/views",
        json={"surface": "traces", "name": "Traces view", "query": ""},
        headers=_headers(),
    )

    runs = await async_client.get("/api/v1/me/views", params={"surface": "runs"}, headers=_headers())
    assert [row["name"] for row in runs.json()["data"]] == ["Runs view"]
    everything = await async_client.get("/api/v1/me/views", headers=_headers())
    assert len(everything.json()["data"]) == 2


@pytest.mark.asyncio
async def test_pinning_the_same_object_twice_changes_nothing(async_client):
    first = await async_client.post(
        "/api/v1/me/pins",
        json={"object_type": "agent", "object_id": "agt_1", "label": "support-triage"},
        headers=_headers(),
    )
    assert first.status_code == status.HTTP_200_OK
    again = await async_client.post(
        "/api/v1/me/pins",
        json={"object_type": "agent", "object_id": "agt_1"},
        headers=_headers(),
    )

    assert again.json()["data"]["id"] == first.json()["data"]["id"]
    # And the label captured the first time survives the second pin.
    assert again.json()["data"]["label"] == "support-triage"
    assert len((await async_client.get("/api/v1/me/pins", headers=_headers())).json()["data"]) == 1


@pytest.mark.asyncio
async def test_unpinning_something_that_is_not_pinned_is_a_404(async_client):
    response = await async_client.delete("/api/v1/me/pins/pin_missing", headers=_headers())

    assert response.status_code == status.HTTP_404_NOT_FOUND
