"""AG-UI agent mode through the real streaming executor.

Every other agent-mode test overrides the executor with a stub, which is how
``execute_agent_streaming`` could break without a red test: the durable
worker and the inline executor are its only callers, and neither is
exercised end to end elsewhere. This runs the published-agent path for real
on the in-memory model, with nothing overridden.
"""

from __future__ import annotations

import json

import pytest
from fastapi import status

HEADERS = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


async def _publish_agent(async_client) -> str:
    created = await async_client.post(
        "/api/v1/agents",
        json={"name": "Real executor agent", "description": "streams for real", "visibility": "private"},
        headers=HEADERS,
    )
    assert created.status_code == status.HTTP_201_CREATED
    agent_id = created.json()["data"]["id"]
    version = await async_client.post(
        f"/api/v1/agents/{agent_id}/versions",
        json={
            "system_prompt": "Echo the request.",
            "bindings": {"model_ref": "model:test:real-executor"},
            "verify": False,
        },
        headers=HEADERS,
    )
    assert version.status_code == status.HTTP_201_CREATED
    published = await async_client.post(
        f"/api/v1/agents/{agent_id}/publish",
        json={"version_id": version.json()["data"]["id"]},
        headers=HEADERS,
    )
    assert published.status_code == status.HTTP_200_OK
    return agent_id


@pytest.mark.asyncio
async def test_agent_mode_streams_a_real_execution_to_run_finished(async_client) -> None:
    agent_id = await _publish_agent(async_client)
    thread = await async_client.post(
        "/api/v1/threads",
        json={"title": "real executor", "agent_id": agent_id},
        headers=HEADERS,
    )
    assert thread.status_code == status.HTTP_201_CREATED
    thread_id = thread.json()["data"]["id"]

    payload = {
        "threadId": thread_id,
        "runId": "interaction_real_executor",
        "state": {},
        "messages": [{"id": "msg_real_executor", "role": "user", "content": "say hello"}],
        "tools": [],
        "context": [],
        "forwardedProps": {"soit": {"mode": "agent", "agentId": agent_id}},
    }
    async with async_client.stream("POST", "/api/v1/responses", json=payload, headers=HEADERS) as response:
        assert response.status_code == status.HTTP_200_OK
        body = (await response.aread()).decode("utf-8")

    events = [
        json.loads(line[6:])
        for line in body.splitlines()
        if line.startswith("data: ") and line[6:] != "[DONE]"
    ]
    event_types = [event["type"] for event in events]

    assert event_types[0] == "RUN_STARTED"
    assert "RUN_ERROR" not in event_types, events
    assert "TEXT_MESSAGE_CONTENT" in event_types
    assert event_types[-1] == "RUN_FINISHED"
    assert events[-1]["result"]["status"] == "succeeded"
