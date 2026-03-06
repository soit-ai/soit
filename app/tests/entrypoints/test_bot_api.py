"""test_bot_api

Entrypoint tests for Bot API contract.
"""

from fastapi import status


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_bot_version_publish_execute_and_observability_contract(client):
    create_resp = client.post(
        "/api/v1/bots",
        json={
            "name": "bot-api-contract",
            "description": "contract",
            "visibility": "private",
            "tags": ["api"],
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    bot = create_resp.json()["data"]
    bot_id = bot["id"]

    version_resp = client.post(
        f"/api/v1/bots/{bot_id}/versions",
        json={
            "system_prompt": "You are bot api test.",
            "model_ref": "model:openai:gpt-5.1",
            "tool_refs": ["tool:http:demo"],
            "triggers": {"webhook": {"secret_ref": "secret:webhook"}},
            "channels": {"slack": {"secret_ref": "secret:slack"}},
            "metadata_json": {"display_version": "v1.0.0"},
        },
        headers=_headers(),
    )
    assert version_resp.status_code == status.HTTP_201_CREATED
    version = version_resp.json()["data"]
    version_id = version["id"]
    assert version["status"] == "draft"
    assert version["display_version"] == "v1.0.0"
    assert version["triggers"]["webhook"]["secret_ref"] == "secret:webhook"

    update_resp = client.put(
        f"/api/v1/bots/{bot_id}/versions/{version_id}",
        json={
            "system_prompt": "You are updated.",
            "channels": {"email": {"enabled": True}},
        },
        headers=_headers(),
    )
    assert update_resp.status_code == status.HTTP_200_OK
    updated = update_resp.json()["data"]
    assert updated["status"] == "draft"
    assert updated["system_prompt"] == "You are updated."
    assert updated["channels"]["email"]["enabled"] is True

    publish_resp = client.post(
        f"/api/v1/bots/{bot_id}/publish",
        json={"version_id": version_id},
        headers=_headers(),
    )
    assert publish_resp.status_code == status.HTTP_200_OK
    published_bot = publish_resp.json()["data"]
    assert published_bot["current_version_id"] == version_id
    assert published_bot["published_version_id"] == version_id

    draft_for_execute_resp = client.post(
        f"/api/v1/bots/{bot_id}/versions",
        json={
            "system_prompt": "draft execute",
            "model_ref": "model:openai:gpt-5.1",
            "channels": {"slack": {"enabled": True}},
        },
        headers=_headers(),
    )
    assert draft_for_execute_resp.status_code == status.HTTP_201_CREATED
    draft_version_id = draft_for_execute_resp.json()["data"]["id"]

    execute_resp = client.post(
        f"/api/v1/bots/{bot_id}/execute",
        json={
            "version_id": draft_version_id,
            "messages": [{"role": "user", "content": "hello bot"}],
        },
        headers=_headers(),
    )
    assert execute_resp.status_code == status.HTTP_200_OK
    execute_data = execute_resp.json()["data"]
    assert execute_data["run_id"]
    assert isinstance(execute_data["output"], str)

    runs_resp = client.get(f"/api/v1/bots/{bot_id}/runs", headers=_headers())
    assert runs_resp.status_code == status.HTTP_200_OK
    runs_data = runs_resp.json()["data"]
    assert len(runs_data["items"]) >= 1
    assert "message_count" in runs_data["items"][0]

    run_id = execute_data["run_id"]
    run_detail_resp = client.get(f"/api/v1/bots/{bot_id}/runs/{run_id}", headers=_headers())
    assert run_detail_resp.status_code == status.HTTP_200_OK
    run_detail = run_detail_resp.json()["data"]
    assert any(item["type"] == "delivery" for item in run_detail["artifacts"])

    logs_resp = client.get(f"/api/v1/bots/{bot_id}/logs", headers=_headers())
    assert logs_resp.status_code == status.HTTP_200_OK
    logs_data = logs_resp.json()["data"]
    assert isinstance(logs_data["items"], list)

    metrics_resp = client.get(f"/api/v1/bots/{bot_id}/metrics?range_key=7d", headers=_headers())
    assert metrics_resp.status_code == status.HTTP_200_OK
    metrics_data = metrics_resp.json()["data"]
    assert metrics_data["runs_total"] >= 1
    assert "points" in metrics_data
    assert "usage_distribution" in metrics_data
    assert "resource_usage" in metrics_data

    webhook_execute_resp = client.post(
        f"/api/v1/bots/{bot_id}/execute/webhook",
        json={"event_payload": {"text": "ping from webhook"}},
        headers=_headers(),
    )
    assert webhook_execute_resp.status_code == status.HTTP_200_OK
    webhook_execute_data = webhook_execute_resp.json()["data"]
    assert webhook_execute_data["run_id"]
