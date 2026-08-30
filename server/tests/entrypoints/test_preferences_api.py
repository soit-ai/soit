"""Entrypoint contract for saved views and pins.

Both are personal: what one person keeps must never appear for another, and a
default only makes sense one at a time per screen.
"""

from fastapi import status


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_a_saved_view_round_trips(client):
    created = client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "Failed only", "query": "status=failed"},
        headers=_headers(),
    )
    assert created.status_code == status.HTTP_200_OK
    view = created.json()["data"]
    assert view["surface"] == "runs"
    assert view["query"] == "status=failed"
    assert view["is_default"] is False

    listed = client.get("/api/v1/me/views", params={"surface": "runs"}, headers=_headers())
    assert [row["name"] for row in listed.json()["data"]] == ["Failed only"]

    deleted = client.delete(f"/api/v1/me/views/{view['id']}", headers=_headers())
    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    assert client.get("/api/v1/me/views", headers=_headers()).json()["data"] == []


def test_saving_over_a_name_updates_that_view(client):
    """Saving over a name is how a filter gets edited, not an error."""
    first = client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "Recent", "query": "range=24h"},
        headers=_headers(),
    ).json()["data"]

    second = client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "Recent", "query": "range=7d"},
        headers=_headers(),
    ).json()["data"]

    assert second["id"] == first["id"]
    assert second["query"] == "range=7d"
    assert len(client.get("/api/v1/me/views", headers=_headers()).json()["data"]) == 1


def test_only_one_view_per_screen_is_the_default(client):
    client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "A", "query": "a=1", "is_default": True},
        headers=_headers(),
    )
    client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "B", "query": "b=1", "is_default": True},
        headers=_headers(),
    )

    views = client.get("/api/v1/me/views", params={"surface": "runs"}, headers=_headers())
    defaults = [row["name"] for row in views.json()["data"] if row["is_default"]]
    assert defaults == ["B"]


def test_a_view_for_another_screen_is_not_returned(client):
    client.post(
        "/api/v1/me/views",
        json={"surface": "runs", "name": "Runs view", "query": ""},
        headers=_headers(),
    )
    client.post(
        "/api/v1/me/views",
        json={"surface": "traces", "name": "Traces view", "query": ""},
        headers=_headers(),
    )

    runs = client.get("/api/v1/me/views", params={"surface": "runs"}, headers=_headers())
    assert [row["name"] for row in runs.json()["data"]] == ["Runs view"]
    everything = client.get("/api/v1/me/views", headers=_headers())
    assert len(everything.json()["data"]) == 2


def test_pinning_the_same_object_twice_changes_nothing(client):
    first = client.post(
        "/api/v1/me/pins",
        json={"object_type": "agent", "object_id": "agt_1", "label": "support-triage"},
        headers=_headers(),
    )
    assert first.status_code == status.HTTP_200_OK
    again = client.post(
        "/api/v1/me/pins",
        json={"object_type": "agent", "object_id": "agt_1"},
        headers=_headers(),
    )

    assert again.json()["data"]["id"] == first.json()["data"]["id"]
    # And the label captured the first time survives the second pin.
    assert again.json()["data"]["label"] == "support-triage"
    assert len(client.get("/api/v1/me/pins", headers=_headers()).json()["data"]) == 1


def test_unpinning_something_that_is_not_pinned_is_a_404(client):
    response = client.delete("/api/v1/me/pins/pin_missing", headers=_headers())

    assert response.status_code == status.HTTP_404_NOT_FOUND
