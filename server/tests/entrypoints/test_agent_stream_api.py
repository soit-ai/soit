"""Entry-point tests for the deprecated Agent streaming SSE endpoint.

The route no longer executes anything itself: it claims a persisted response
interaction and tails it, so the durable worker owns execution. End-to-end
agent streaming behaviour is covered by the `/v1/responses` tests, which
exercise that same machinery.
"""

import pytest
from fastapi import status
from sqlmodel import select

from app.kernel.runtime.db.models.responses import ResponseInteraction
from app.modules.agent.application.schemas import AgentRunRequest
from app.settings.settings import settings

HEADERS = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


@pytest.fixture
def agent_id(client) -> str:
    create_resp = client.post(
        "/api/v1/agents",
        json={
            "name": "stream-agent",
            "description": "Stream test",
            "visibility": "private",
        },
        headers=HEADERS,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    return create_resp.json()["data"]["id"]


def test_agent_stream_route_is_marked_deprecated_in_the_schema(client):
    schema = client.get("/api/v1/openapi.json").json()
    route = schema["paths"]["/api/v1/agents/{agent_id}/stream"]["post"]

    assert route["deprecated"] is True


def test_agent_stream_refuses_to_run_without_the_durable_worker(
    client, agent_id, monkeypatch
):
    monkeypatch.setattr(settings, "response_interaction_worker_enabled", False)

    response = client.post(
        f"/api/v1/agents/{agent_id}/stream",
        json={"input": "hello"},
        headers=HEADERS,
    )

    # Claiming without a worker would leave the stream heartbeating forever, so
    # the route says so instead of hanging.
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_agent_stream_claims_a_persisted_interaction_for_the_worker(
    db, ctx, agent_id, monkeypatch
):
    monkeypatch.setattr(settings, "response_interaction_worker_enabled", True)
    from app.api.v1.agent.router import stream_agent
    from app.api.v1.responses.dependencies import get_response_projection_coordinator

    # Call the route directly: the returned body tails the claim until the
    # worker terminates it, so consuming it here would never finish.
    response = await stream_agent(
        agent_id,
        AgentRunRequest(input="hello"),
        ctx,
        get_response_projection_coordinator(ctx, db),
    )

    assert response.media_type == "text/event-stream"
    assert response.headers["Deprecation"] == "true"
    assert 'rel="successor-version"' in response.headers["Link"]

    claimed = list(
        db.execute(
            select(ResponseInteraction).where(ResponseInteraction.status == "queued")
        )
        .scalars()
        .all()
    )
    assert len(claimed) == 1
    interaction = claimed[0]
    # The worker executes agent mode from these fields alone.
    assert interaction.execution_json["mode"] == "agent"
    assert interaction.execution_json["agent_id"] == agent_id
    assert interaction.execution_json["agent_inputs"]["input"] == "hello"
    assert interaction.execution_json["assistant_message_id"]
    # An unbound response is what makes the worker execute the claim rather
    # than terminalize it as an orphan.
    assert interaction.response_id is None
    assert interaction.request_context_json["tenant_id"] == "test-tenant"
