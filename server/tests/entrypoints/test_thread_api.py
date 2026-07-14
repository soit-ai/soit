"""Entrypoint tests for runtime thread APIs."""

from fastapi import status

from app.kernel.runtime.threads.service import ThreadService


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


def test_thread_api_searches_titles_and_message_content(client, db, ctx):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    runtime = ThreadService(db, ctx)
    billing_thread = runtime.create_thread(agent_id="agent_demo", title="Billing escalation")
    runtime.append_message(
        thread_id=billing_thread.id,
        role="user",
        content="The enterprise ticket mentions an SSO outage in ACME.",
    )
    runtime.create_thread(agent_id="agent_demo", title="Product notes")

    title_response = client.get("/api/v1/threads?search=billing", headers=headers)
    assert title_response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in title_response.json()["data"]["items"]] == [billing_thread.id]

    message_response = client.get("/api/v1/threads?search=sso%20outage", headers=headers)
    assert message_response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in message_response.json()["data"]["items"]] == [billing_thread.id]


def test_thread_api_returns_tool_call_details_for_chat_history(client, db, ctx):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    runtime = ThreadService(db, ctx)
    thread = runtime.create_thread(agent_id="agent_demo", title="Tool call history")
    tool_calls = [
        {
            "tool_call_id": "call_ticket_lookup",
            "tool_name": "tool:test:ticket_lookup",
            "tool_type": "builtin",
            "status": "completed",
            "arguments_json": {"ticket_id": "TCK-DEMO-1"},
            "result_json": {"result": {"ticket_id": "TCK-DEMO-1", "account": "verified"}},
            "metadata_json": {"duration_ms": 8},
        },
        {
            "tool_call_id": "call_ticket_workflow",
            "tool_name": "wf:ticket-flow",
            "tool_type": "workflow",
            "status": "completed",
            "arguments_json": {"ticket_id": "TCK-DEMO-1", "priority": "high"},
            "result_json": {"result": {"workflow_run_id": "run_ticket_1"}},
            "metadata_json": {},
        },
    ]
    runtime.append_message(
        thread_id=thread.id,
        role="assistant",
        content="Verified account and opened the ticket workflow.",
        run_id="run_agent_1",
        metadata={
            "tool_calls": tool_calls,
            "tool_calls_count": len(tool_calls),
            "cost_total": 0.02,
        },
        tool_calls_json=tool_calls,
    )

    response = client.get(f"/api/v1/threads/{thread.id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    messages = response.json()["data"]["messages"]
    assistant_message = next(message for message in messages if message["role"] == "assistant")
    assert assistant_message["tool_calls_json"] == tool_calls
    assert assistant_message["metadata_json"]["tool_calls"] == tool_calls
    assert assistant_message["metadata_json"]["tool_calls_count"] == 2
    assert assistant_message["metadata_json"]["cost_total"] == 0.02
