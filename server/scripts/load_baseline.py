"""Measure a concurrency and latency baseline against a running SOIT stack.

Fires concurrent agent executions at a live API and reports latency
percentiles, throughput, and failure counts as machine-readable JSON.
The numbers describe the platform overhead of the governed execution
path (API, ledger, PostgreSQL); when the target runs with a mock model
(SOIT_TESTING=1) they deliberately exclude model latency.

Usage, from server/ against a stack on 127.0.0.1:9200:

    uv run python scripts/load_baseline.py \
        --base-url http://127.0.0.1:9200/api/v1 \
        --concurrency 10 --requests 100 --out baseline.json
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


async def _one_request(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    agent_id: str,
    index: int,
    latencies: list[float],
    errors: list[str],
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
            latencies.append(elapsed_ms)
        else:
            errors.append(f"{index}: HTTP {response.status_code}")
    except httpx.HTTPError as exc:
        errors.append(f"{index}: {type(exc).__name__}: {exc}")


async def run_baseline(
    *, base_url: str, concurrency: int, total_requests: int
) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:12]
    timeout = httpx.Timeout(120.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        headers = await _signup(client, suffix)
        agent_id = await _publish_agent(client, headers, suffix)

        latencies: list[float] = []
        errors: list[str] = []
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded(index: int) -> None:
            async with semaphore:
                await _one_request(client, headers, agent_id, index, latencies, errors)

        started = time.perf_counter()
        await asyncio.gather(*(bounded(index) for index in range(total_requests)))
        wall_seconds = time.perf_counter() - started

    ordered = sorted(latencies)
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "concurrency": concurrency,
        "requests": total_requests,
        "succeeded": len(latencies),
        "failed": len(errors),
        "errors": errors[:20],
        "wall_seconds": round(wall_seconds, 3),
        "throughput_rps": round(len(latencies) / wall_seconds, 2) if wall_seconds else 0,
        "latency_ms": {
            "p50": round(_percentile(ordered, 0.50), 1),
            "p95": round(_percentile(ordered, 0.95), 1),
            "p99": round(_percentile(ordered, 0.99), 1),
            "mean": round(statistics.fmean(ordered), 1) if ordered else 0.0,
            "max": round(ordered[-1], 1) if ordered else 0.0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:9200/api/v1")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--out", default=None, help="Write the JSON report here")
    args = parser.parse_args()

    report = asyncio.run(
        run_baseline(
            base_url=args.base_url,
            concurrency=args.concurrency,
            total_requests=args.requests,
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
