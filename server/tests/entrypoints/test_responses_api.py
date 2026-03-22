"""Entry-point tests for the Responses API."""

import json

from fastapi import status


def test_responses_api_create_get_events_and_cancel(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}

    create_response = client.post(
        "/api/v1/responses",
        json={
            "model": "model:openai:gpt-5.1",
            "agent_id": "agent_test",
            "input": {
                "items": [
                    {"type": "input_text", "text": "hello"},
                ]
            },
            "metadata": {"source": "test"},
        },
        headers=headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    payload = create_response.json()["data"]
    assert payload["id"].startswith("resp_")
    assert payload["run_id"].startswith("run_")
    assert payload["status"] == "completed"
    assert payload["provider"] == "openai"
    assert payload["metadata_json"]["source"] == "test"
    assert payload["output_json"]["text"] == "hello"
    assert payload["usage_json"]["total_tokens"] >= 1

    response_id = payload["id"]

    get_response = client.get(f"/api/v1/responses/{response_id}", headers=headers)
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["data"]["id"] == response_id

    events_response = client.get(f"/api/v1/responses/{response_id}/events", headers=headers)
    assert events_response.status_code == status.HTTP_200_OK
    events_payload = events_response.json()["data"]
    assert len(events_payload["items"]) == 4
    assert events_payload["items"][0]["type"] == "response.created"
    assert events_payload["items"][1]["type"] == "response.input.added"
    assert events_payload["items"][2]["type"] == "response.output_text.completed"
    assert events_payload["items"][3]["type"] == "response.completed"

    cancel_response = client.post(f"/api/v1/responses/{response_id}/cancel", headers=headers)
    assert cancel_response.status_code == status.HTTP_200_OK
    cancel_payload = cancel_response.json()["data"]
    assert cancel_payload["action"] == "cancel"
    assert cancel_payload["response"]["status"] == "completed"

    events_after_cancel = client.get(f"/api/v1/responses/{response_id}/events", headers=headers)
    assert events_after_cancel.status_code == status.HTTP_200_OK
    event_types = [item["type"] for item in events_after_cancel.json()["data"]["items"]]
    assert event_types == [
        "response.created",
        "response.input.added",
        "response.output_text.completed",
        "response.completed",
    ]


def test_responses_api_stream_and_replay(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}

    with client.stream(
        "POST",
        "/api/v1/responses",
        json={
            "model": "model:openai:gpt-5.1",
            "input": {"items": [{"type": "input_text", "text": "stream me"}]},
            "stream": True,
        },
        headers=headers,
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        body = response.read().decode("utf-8")

    assert "event: response.created" in body
    assert "event: response.input.added" in body
    assert "event: response.output_text.delta" in body
    assert "event: response.output_text.completed" in body
    assert "event: response.completed" in body
    assert "[DONE]" in body

    response_id = None
    for raw_line in body.splitlines():
        if not raw_line.startswith("data: "):
            continue
        payload = raw_line[6:]
        if payload == "[DONE]":
            continue
        parsed = json.loads(payload)
        response_id = parsed.get("response_id") or response_id
        if response_id:
            break
    assert response_id is not None

    replay_response = client.get(f"/api/v1/responses/{response_id}/stream", headers=headers)
    assert replay_response.status_code == status.HTTP_200_OK
    replay_body = replay_response.text
    assert "event: response.created" in replay_body
    assert "event: response.output_text.delta" in replay_body
    assert "event: response.completed" in replay_body
    assert "[DONE]" in replay_body


def test_responses_api_run_timeline(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}

    create_response = client.post(
        "/api/v1/responses",
        json={
            "model": "model:openai:gpt-5.1",
            "input": {"items": [{"type": "input_text", "text": "timeline me"}]},
            "metadata": {"source": "timeline-test"},
        },
        headers=headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    payload = create_response.json()["data"]

    timeline_response = client.get(
        f"/api/v1/responses/by-run/{payload['run_id']}",
        headers=headers,
    )
    assert timeline_response.status_code == status.HTTP_200_OK
    timeline_payload = timeline_response.json()["data"]
    assert timeline_payload["run_id"] == payload["run_id"]
    assert len(timeline_payload["items"]) == 1
    item = timeline_payload["items"][0]
    assert item["response"]["id"] == payload["id"]
    assert [event["type"] for event in item["events"]] == [
        "response.created",
        "response.input.added",
        "response.output_text.completed",
        "response.completed",
    ]
