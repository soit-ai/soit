"""A gateway call's cost row keeps the provider's ids, and a repeated id is not an error.

Self-hosted OpenAI-compatible servers and caching proxies give two calls the
same id, so the ids are kept without a unique constraint: the second call is
answered and charged like the first.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlmodel import select

from app.kernel.ports.llm.interface import ChatStreamChunk
from app.kernel.runtime.db.models.runs import RunCostEntry
from app.wiring import get_container

MODEL = "model:test:chat"


class _RepeatingIdPort:
    """A provider that gives every stream the same ids, as a caching proxy would."""

    async def stream_chat(self, *args: Any, **kwargs: Any) -> AsyncIterator[ChatStreamChunk]:
        del args, kwargs
        yield ChatStreamChunk(delta="hi", model="test-chat", upstream_id="chatcmpl-42")
        yield ChatStreamChunk(
            done=True,
            tokens_prompt=3,
            tokens_completion=1,
            finish_reason="stop",
            upstream_request_id="req_repeat",
        )


class _SwapLLMPort:
    def __init__(self, port: Any) -> None:
        self.port = port

    def __enter__(self) -> None:
        container = get_container()
        self.original = container.get("llm_port")
        container.register_singleton("llm_port", self.port)

    def __exit__(self, *exc: object) -> None:
        get_container().register_singleton("llm_port", self.original)


@pytest.mark.asyncio
async def test_streamed_calls_keep_the_providers_ids_even_when_they_repeat(async_client, async_db) -> None:
    run_ids = []
    with _SwapLLMPort(_RepeatingIdPort()):
        for _ in range(2):
            response = await async_client.post(
                "/v1/chat/completions",
                json={"model": MODEL, "stream": True, "messages": [{"role": "user", "content": "hello"}]},
            )
            assert response.status_code == 200
            run_ids.append(response.headers["x-soit-run-id"])

    costs = (await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id.in_(run_ids)))).all()
    assert len(costs) == 2
    assert {(cost.upstream_id, cost.upstream_request_id) for cost in costs} == {("chatcmpl-42", "req_repeat")}

    listed = await async_client.get("/api/v1/runs/costs/entries", params={"run_id": run_ids[0]})
    [entry] = listed.json()["data"]["items"]
    assert (entry["upstream_id"], entry["upstream_request_id"]) == ("chatcmpl-42", "req_repeat")

    found = await async_client.get("/api/v1/runs/costs/entries", params={"upstream_request_id": "req_repeat"})
    assert {item["run_id"] for item in found.json()["data"]["items"]} == set(run_ids)
