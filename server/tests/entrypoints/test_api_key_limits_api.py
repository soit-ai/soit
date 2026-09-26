"""API keys carry limits that their owner or a workspace admin sets."""

from __future__ import annotations

import dataclasses

import pytest

from app.kernel.contracts.context import RequestContext
from app.main import app
from app.middleware.auth import get_current_context

LIMITS = {
    "rate_limit_per_minute": 30,
    "daily_request_quota": 1000,
    "daily_token_quota": 200_000,
    "ip_allowlist": ["203.0.113.7", "198.51.100.0/24", "198.51.100.0/24"],
    "allowed_models": ["model:openai-main:gpt-live", " model:openai-main:gpt-live "],
}


async def _create(async_client, **fields):
    body = {"name": "gateway", "scopes": ["write"], "expires_in_days": 30, **fields}
    return await async_client.post("/api/v1/api-keys", json=body)


def _as(ctx: RequestContext, **changes) -> None:
    other = dataclasses.replace(ctx, **changes)
    app.dependency_overrides[get_current_context] = lambda: other


@pytest.mark.asyncio
async def test_a_key_is_created_with_normalized_limits(async_client) -> None:
    response = await _create(async_client, **LIMITS)

    assert response.status_code == 200
    item = response.json()["data"]["item"]
    assert item["rate_limit_per_minute"] == 30
    assert item["daily_request_quota"] == 1000
    assert item["daily_token_quota"] == 200_000
    assert item["ip_allowlist"] == ["198.51.100.0/24", "203.0.113.7/32"]
    assert item["allowed_models"] == ["model:openai-main:gpt-live"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        {"ip_allowlist": ["not-a-range"]},
        {"ip_allowlist": []},
        {"allowed_models": ["  "]},
        {"rate_limit_per_minute": 0},
    ],
)
async def test_limits_that_cannot_work_are_refused(async_client, fields) -> None:
    response = await _create(async_client, **fields)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_the_owner_changes_and_clears_limits(async_client) -> None:
    key_id = (await _create(async_client, **LIMITS)).json()["data"]["item"]["id"]

    response = await async_client.patch(
        f"/api/v1/api-keys/{key_id}",
        json={"rate_limit_per_minute": 60, "allowed_models": None, "name": "renamed"},
    )

    assert response.status_code == 200
    item = response.json()["data"]
    assert item["name"] == "renamed"
    assert item["rate_limit_per_minute"] == 60
    assert item["allowed_models"] is None
    # Fields not sent are left as they were.
    assert item["daily_token_quota"] == 200_000
    assert item["ip_allowlist"] == ["198.51.100.0/24", "203.0.113.7/32"]


@pytest.mark.asyncio
async def test_another_developer_cannot_lift_a_keys_limits(async_client, ctx) -> None:
    key_id = (await _create(async_client, **LIMITS)).json()["data"]["item"]["id"]

    _as(ctx, user_id="another-dev", workspace_role="Dev")
    try:
        refused = await async_client.patch(
            f"/api/v1/api-keys/{key_id}", json={"daily_token_quota": None}
        )
        _as(ctx, user_id="workspace-admin", workspace_role="Admin")
        admitted = await async_client.patch(
            f"/api/v1/api-keys/{key_id}", json={"daily_token_quota": 1}
        )
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    assert refused.status_code == 403
    assert admitted.status_code == 200
    assert admitted.json()["data"]["daily_token_quota"] == 1


@pytest.mark.asyncio
async def test_rotation_keeps_the_limits(async_client) -> None:
    key_id = (await _create(async_client, **LIMITS)).json()["data"]["item"]["id"]

    rotated = await async_client.post(f"/api/v1/api-keys/{key_id}/rotate")

    assert rotated.status_code == 200
    item = rotated.json()["data"]["item"]
    assert item["id"] != key_id
    assert item["rate_limit_per_minute"] == 30
    assert item["ip_allowlist"] == ["198.51.100.0/24", "203.0.113.7/32"]
    assert item["allowed_models"] == ["model:openai-main:gpt-live"]


@pytest.mark.asyncio
async def test_a_key_can_keep_its_calls_out_of_run_text(async_client) -> None:
    created = await _create(async_client, content_capture="metadata_only")
    assert created.json()["data"]["item"]["content_capture"] == "metadata_only"

    # A key can only keep less than its workspace; "full" is the workspace's call.
    assert (await _create(async_client, content_capture="full")).status_code == 400

    key_id = created.json()["data"]["item"]["id"]
    cleared = await async_client.patch(f"/api/v1/api-keys/{key_id}", json={"content_capture": None})
    assert cleared.json()["data"]["content_capture"] is None


@pytest.mark.asyncio
async def test_a_revoked_key_cannot_be_changed(async_client) -> None:
    key_id = (await _create(async_client)).json()["data"]["item"]["id"]
    await async_client.post(f"/api/v1/api-keys/{key_id}/revoke")

    response = await async_client.patch(f"/api/v1/api-keys/{key_id}", json={"name": "x"})

    assert response.status_code == 400
