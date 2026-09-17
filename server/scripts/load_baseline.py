"""Measure a concurrency and latency baseline against a running SOIT stack.

Fires concurrent agent executions at a live API and reports latency
percentiles, throughput, and failure counts as machine-readable JSON.
The numbers describe the platform overhead of the governed execution
path (API, ledger, PostgreSQL); when the target runs with a mock model
(SOIT_TESTING=1) they deliberately exclude model latency unless the
target sets SOIT_TESTING_MODEL_LATENCY_MS.

Two modes, matching the two ways a stack can execute:

- ``inline`` (default): ``POST /agents/{id}/execute``; the request runs
  the agent and returns. Measures how many executions per second one API
  process can drive.
- ``worker``: ``POST /responses`` with an AG-UI run input; the request
  claims the interaction, the durable worker executes it, and the
  response tails the persisted events. This is the production shape.
  Measures how many executions can be in flight at once and how long a
  claim waits for a worker (``wait_ms``, claim to RUN_STARTED).

Usage, from server/ against a stack on 127.0.0.1:9200:

    uv run python scripts/load_baseline.py \
        --base-url http://127.0.0.1:9200/api/v1 \
        --concurrency 10 --requests 100 --out baseline.json

    uv run python scripts/load_baseline.py --mode worker \
        --concurrency 50 --requests 200 --out worker.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, round(fraction * (len(sorted_values) - 1))))
    return sorted_values[index]


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "p50": round(_percentile(ordered, 0.50), 1),
        "p95": round(_percentile(ordered, 0.95), 1),
        "p99": round(_percentile(ordered, 0.99), 1),
        "mean": round(statistics.fmean(ordered), 1) if ordered else 0.0,
        "max": round(ordered[-1], 1) if ordered else 0.0,
    }


async def _signup(client: httpx.AsyncClient, suffix: str) -> dict[str, str]:
    response = await client.post(
        "/register",
        params={"tenant_name": f"Load {suffix}"},
        json={
            "email": f"load-{suffix}@example.com",
            "name": "Load Baseline",
            "password": "LoadBaseline123!",
        },
    )
    response.raise_for_status()
    data = response.json()["data"]
    token = data.get("access_token")
    workspace_id = data.get("workspace_id")
    if not token or not workspace_id:
        raise RuntimeError(f"Registration did not return credentials: {data}")
    return {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": str(workspace_id),
    }


async def _publish_agent(
    client: httpx.AsyncClient, headers: dict[str, str], suffix: str
) -> str:
    agent = (
        await client.post(
            "/agents",
            headers=headers,
            json={
                "name": f"Load agent {suffix}",
                "description": "Load baseline agent",
                "visibility": "private",
            },
        )
    ).json()["data"]
    version = (
        await client.post(
            f"/agents/{agent['id']}/versions",
            headers=headers,
            json={
                "system_prompt": "Echo the request.",
                "bindings": {"model_ref": f"model:test:load-{suffix}"},
                "verify": False,
            },
        )
    ).json()["data"]
    publish = await client.post(
        f"/agents/{agent['id']}/publish",
        headers=headers,
        json={"version_id": version["id"]},
    )
    publish.raise_for_status()
    return agent["id"]


async def _create_thread(client: httpx.AsyncClient, headers: dict[str, str], agent_id: str) -> str:
    response = await client.post(
        "/threads",
        headers=headers,
        json={"agent_id": agent_id, "title": "Load baseline thread"},
    )
    response.raise_for_status()
    return str(response.json()["data"]["id"])


def _agui_run_input(*, thread_id: str, agent_id: str, run_id: str, content: str) -> dict[str, Any]:
    return {
        "threadId": thread_id,
        "runId": run_id,
        "state": {},
        "messages": [{"id": f"msg_{run_id}", "role": "user", "content": content}],
        "tools": [],
        "context": [],
        "forwardedProps": {"soit": {"mode": "agent", "agentId": agent_id}},
    }


class _Sample:
    """One request's outcome; ``wait_ms`` is only known in worker mode."""

    def __init__(self) -> None:
        self.latencies: list[float] = []
        self.waits: list[float] = []
        self.errors: list[str] = []


async def _one_inline_request(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    agent_id: str,
    index: int,
    sample: _Sample,
) -> None:
    started = time.perf_counter()
    try:
        response = await client.post(
            f"/agents/{agent_id}/execute",
            headers=headers,
            json={"input": f"load baseline request {index}"},
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if response.status_code == 200 and response.json().get("success"):
            sample.latencies.append(elapsed_ms)
        else:
            sample.errors.append(f"{index}: HTTP {response.status_code}")
    except httpx.HTTPError as exc:
        sample.errors.append(f"{index}: {type(exc).__name__}: {exc}")


async def _one_worker_request(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    agent_id: str,
    index: int,
    sample: _Sample,
) -> None:
    # The thread is part of the real flow but not of the execution path
    # being measured, so it is created before the clock starts.
    try:
        thread_id = await _create_thread(client, headers, agent_id)
    except httpx.HTTPError as exc:
        sample.errors.append(f"{index}: thread: {type(exc).__name__}: {exc}")
        return
    run_id = f"run_{uuid.uuid4().hex}"
    payload = _agui_run_input(
        thread_id=thread_id,
        agent_id=agent_id,
        run_id=run_id,
        content=f"load baseline request {index}",
    )
    started = time.perf_counter()
    wait_ms: float | None = None
    terminal: str | None = None
    last_event: str | None = None
    try:
        async with client.stream("POST", "/responses", headers=headers, json=payload) as response:
            if response.status_code not in (200, 201):
                body = (await response.aread()).decode("utf-8", "replace")[:200]
                sample.errors.append(f"{index}: HTTP {response.status_code} {body}")
                return
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                event_type = str(event.get("type") or "")
                last_event = event_type
                if event_type == "RUN_STARTED" and wait_ms is None:
                    wait_ms = (time.perf_counter() - started) * 1000
                elif event_type in {"RUN_FINISHED", "RUN_ERROR"}:
                    terminal = event_type
                    break
    except httpx.HTTPError as exc:
        sample.errors.append(f"{index}: {type(exc).__name__}: {exc} (run {run_id})")
        return
    elapsed_ms = (time.perf_counter() - started) * 1000
    if terminal == "RUN_FINISHED":
        sample.latencies.append(elapsed_ms)
        sample.waits.append(wait_ms if wait_ms is not None else elapsed_ms)
    else:
        # The run id lets the failure be looked up in response_interactions.
        sample.errors.append(
            f"{index}: stream ended with {terminal or 'no terminal event'} "
            f"after {last_event or 'nothing'} (run {run_id})"
        )


async def run_baseline(
    *, base_url: str, concurrency: int, total_requests: int, mode: str
) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:12]
    timeout = httpx.Timeout(300.0)
    one_request = _one_worker_request if mode == "worker" else _one_inline_request
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        headers = await _signup(client, suffix)
        agent_id = await _publish_agent(client, headers, suffix)

        sample = _Sample()
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded(index: int) -> None:
            async with semaphore:
                await one_request(client, headers, agent_id, index, sample)

        started = time.perf_counter()
        await asyncio.gather(*(bounded(index) for index in range(total_requests)))
        wall_seconds = time.perf_counter() - started

    succeeded = len(sample.latencies)
    report: dict[str, Any] = {
        "captured_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "mode": mode,
        "concurrency": concurrency,
        "requests": total_requests,
        "succeeded": succeeded,
        "failed": len(sample.errors),
        "errors": sample.errors[:20],
        "wall_seconds": round(wall_seconds, 3),
        "throughput_rps": round(succeeded / wall_seconds, 2) if wall_seconds else 0,
        "latency_ms": _summary(sample.latencies),
    }
    if mode == "worker":
        report["wait_ms"] = _summary(sample.waits)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:9200/api/v1")
    parser.add_argument("--mode", choices=("inline", "worker"), default="inline")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--out", default=None, help="Write the JSON report here")
    args = parser.parse_args()

    report = asyncio.run(
        run_baseline(
            base_url=args.base_url,
            concurrency=args.concurrency,
            total_requests=args.requests,
            mode=args.mode,
        )
    )
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
