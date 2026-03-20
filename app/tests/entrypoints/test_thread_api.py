"""Entrypoint tests for runtime thread APIs."""

from fastapi import status


def test_thread_api_create_get_update_and_delete(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}

    create_response = client.post(
        "/api/v1/threads",
        json={
            "agent_id": "agent_demo",
            "title": "Response chat",
            "default_model_ref": "model:openai:gpt-5.1",
            "system_prompt": "Stay concise",
            "metadata_json": {"source": "responses.chat"},
        },
        headers=headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    payload = create_response.json()["data"]
    thread_id = payload["id"]
    assert payload["agent_id"] == "agent_demo"
    assert payload["title"] == "Response chat"
    assert payload["default_model_ref"] == "model:openai:gpt-5.1"
    assert payload["system_prompt"] == "Stay concise"
    assert payload["message_count"] == 0
    assert payload["metadata_json"]["source"] == "responses.chat"

    get_response = client.get(f"/api/v1/threads/{thread_id}", headers=headers)
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["data"]["thread"]["id"] == thread_id

    update_response = client.patch(
        f"/api/v1/threads/{thread_id}",
        json={"title": "Response chat renamed", "summary": "short summary"},
        headers=headers,
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["data"]["title"] == "Response chat renamed"
    assert update_response.json()["data"]["summary"] == "short summary"

    delete_response = client.delete(f"/api/v1/threads/{thread_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT


def test_legacy_chat_endpoints_are_offline(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}

    completions_response = client.post(
        "/api/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hello"}]},
        headers=headers,
    )
    assert completions_response.status_code == status.HTTP_404_NOT_FOUND

    stream_response = client.post(
        "/api/v1/chat/stream",
        json={"messages": [{"role": "user", "content": "hello"}], "stream": True},
        headers=headers,
    )
    assert stream_response.status_code == status.HTTP_404_NOT_FOUND
