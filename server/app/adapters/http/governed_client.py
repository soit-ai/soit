"""HTTPX client construction with mandatory per-request egress authorization."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.kernel.contracts.context import RequestContext
from app.kernel.security.egress import GovernedEgressGuard

RequestHook = Callable[[httpx.Request], Awaitable[None]]


def governed_httpx_client(
    *,
    ctx: RequestContext,
    resource_ref: str,
    egress_guard: GovernedEgressGuard | None = None,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Create an HTTPX client that authorizes every request and redirect hop."""
    guard = egress_guard or GovernedEgressGuard()

    async def authorize_request(request: httpx.Request) -> None:
        await guard.authorize(ctx, resource_ref, str(request.url))

    event_hooks = dict(kwargs.pop("event_hooks", {}) or {})
    request_hooks: list[RequestHook] = list(event_hooks.get("request", []) or [])
    event_hooks["request"] = [authorize_request, *request_hooks]
    kwargs.setdefault("follow_redirects", False)
    return httpx.AsyncClient(event_hooks=event_hooks, **kwargs)
