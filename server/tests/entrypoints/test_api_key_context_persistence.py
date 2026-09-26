"""Work started with an API key can be stored and resumed.

Durable interactions store the caller's context in a JSON column. A context
authenticated by an API key carries the key's scopes, and stored as a raw
dataclass those could not be encoded, so every such request failed.
"""

from __future__ import annotations

import dataclasses
import json

import pytest
from fastapi import status
from sqlmodel import select

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.responses import ResponseInteraction
from app.main import app
from app.middleware.auth import get_current_context


@pytest.mark.asyncio
async def test_a_response_started_with_an_api_key_is_stored_and_runs(
    async_client, async_db, ctx: RequestContext
) -> None:
    keyed = dataclasses.replace(ctx, scopes=frozenset({"read", "write"}), api_key_id="key_ctx")
    app.dependency_overrides[get_current_context] = lambda: keyed
    headers = {"X-Workspace-Id": ctx.workspace_id}
    try:
        thread = await async_client.post("/api/v1/threads", json={"title": "keyed"}, headers=headers)
        assert thread.status_code == status.HTTP_201_CREATED
        async with async_client.stream(
            "POST",
            "/api/v1/responses",
            json={
                "threadId": thread.json()["data"]["id"],
                "runId": "interaction_keyed",
                "state": {},
                "messages": [{"id": "msg_keyed", "role": "user", "content": "hello"}],
                "tools": [],
                "context": [],
                "forwardedProps": {"soit": {"mode": "direct", "modelRef": "model:openai:gpt-5.1"}},
            },
            headers=headers,
        ) as response:
            assert response.status_code == status.HTTP_200_OK
            body = (await response.aread()).decode("utf-8")
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    events = [
        json.loads(line[6:])
        for line in body.splitlines()
        if line.startswith("data: ") and line[6:] != "[DONE]"
    ]
    assert events[-1]["type"] == "RUN_FINISHED"

    interaction = (
        await async_db.exec(
            select(ResponseInteraction).where(
                ResponseInteraction.interaction_id == "interaction_keyed"
            )
        )
    ).first()
    assert interaction is not None
    assert interaction.request_context_json["scopes"] == ["read", "write"]
    assert RequestContext.from_json(interaction.request_context_json) == keyed
