"""Sends a telemetry report to the configured endpoint."""

from __future__ import annotations

from typing import Any

import httpx

TIMEOUT_SECONDS = 10.0


class HttpTelemetrySink:
    """POSTs a report as JSON; any answer but 2xx is an error the sender logs."""

    def __init__(self, endpoint: str, *, timeout: float = TIMEOUT_SECONDS) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    async def send(self, report: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            response = await client.post(self.endpoint, json=report)
            response.raise_for_status()
